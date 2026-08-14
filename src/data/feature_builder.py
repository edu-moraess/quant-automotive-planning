"""Orquestra a construção de features gratuitas para demanda automotiva."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd

from config import MARKET_SNAPSHOT

from .contracts import FeatureBuildResult, SourceName, SourceRunStatus, SourceState, TimeWindow
from .feature_store import FeatureStore
from .settings import FeatureSettings, FeatureSourceConfig
from .sources.eia import EIAClient
from .sources.fred import FREDClient
from .sources.news import NewsAPIClient
from .temporal import add_lagged_changes, assert_no_future_availability, monthly_wide_features


class FeatureBuilder:
    """Constrói features de mercado e evento sem depender da futura base comercial de vendas."""

    _EIA_PUBLICATION_LAGS = {
        "gasoline_regular": 7,
        "diesel": 7,
        "electricity_residential": 45,
    }

    def __init__(
        self,
        settings: FeatureSettings,
        source_config: FeatureSourceConfig,
        *,
        store: FeatureStore | None = None,
        market_snapshot: Path = MARKET_SNAPSHOT,
    ) -> None:
        self.settings = settings
        self.source_config = source_config
        self.store = store or FeatureStore(settings.feature_store_dir)
        self.market_snapshot = market_snapshot

    async def build(
        self,
        window: TimeWindow,
        *,
        sources: set[SourceName] | None = None,
    ) -> FeatureBuildResult:
        """Executa fontes selecionadas, preservando snapshots de fontes não solicitadas."""
        selected = sources or {SourceName.FRED, SourceName.EIA, SourceName.NEWS}
        async with (
            FREDClient(self.settings) as fred,
            EIAClient(self.settings) as eia,
            NewsAPIClient(self.settings) as news,
        ):
            fred_task = (
                fred.fetch_many(self.source_config.fred_series, window)
                if SourceName.FRED in selected
                else self._skipped_payload(SourceName.FRED, FREDClient._empty_frame())
            )
            eia_task = (
                eia.fetch_many(self.source_config.eia_series, window, self._EIA_PUBLICATION_LAGS)
                if SourceName.EIA in selected
                else self._skipped_payload(SourceName.EIA, EIAClient._empty_frame())
            )
            news_task = (
                news.fetch_many(self.source_config.news_queries, window)
                if SourceName.NEWS in selected
                else self._skipped_payload(SourceName.NEWS, NewsAPIClient._empty_frame())
            )
            resolved = await asyncio.gather(
                self._resolve_payload(fred_task),
                self._resolve_payload(eia_task),
                self._resolve_payload(news_task),
            )
        fred_payload, eia_payload, news_payload = resolved

        if SourceName.FRED in selected:
            fred_frame, fred_status = self._with_total_sa_fallback(fred_payload.frame, fred_payload.status, window)
        else:
            fred_frame, fred_status = fred_payload.frame, fred_payload.status
        market_features = self._build_market_features(fred_frame, eia_payload.frame, window)
        event_features = self._build_event_features(news_payload.frame, window)
        statuses = [
            payload.status for payload in (fred_payload, eia_payload, news_payload) if payload.status.source in selected
        ]
        if SourceName.FRED in selected:
            statuses = [fred_status if status.source == SourceName.FRED else status for status in statuses]
        builder_status = SourceRunStatus(
            source=SourceName.FEATURE_BUILDER,
            state=self._builder_state(statuses),
            rows=len(market_features) + len(event_features),
            coverage_start=market_features.index.min() if not market_features.empty else None,
            coverage_end=market_features.index.max() if not market_features.empty else None,
            message="Features mensais construídas sem usar textos brutos nem observações futuras.",
        )
        statuses.append(builder_status)
        self._persist(
            fred_frame if SourceName.FRED in selected else pd.DataFrame(),
            eia_payload.frame if SourceName.EIA in selected else pd.DataFrame(),
            news_payload.frame if SourceName.NEWS in selected else pd.DataFrame(),
            market_features if {SourceName.FRED, SourceName.EIA}.intersection(selected) else pd.DataFrame(),
            event_features if SourceName.NEWS in selected else pd.DataFrame(),
            statuses,
        )
        return FeatureBuildResult(
            market_features=market_features,
            event_features=event_features,
            statuses=statuses,
            as_of=window.as_of,
        )

    @staticmethod
    async def _resolve_payload(value: object):
        """Aguarda corrotinas de fonte e devolve payloads já disponíveis em atualizações parciais."""
        if asyncio.iscoroutine(value):
            return await value
        return value

    @staticmethod
    def _skipped_payload(source: SourceName, frame: pd.DataFrame):
        """Representa uma fonte preservada para evitar sobrescrita no manifesto parcial."""
        from .contracts import SourcePayload

        return SourcePayload(
            frame=frame,
            status=SourceRunStatus(
                source=source,
                state=SourceState.CACHED,
                rows=0,
                cache_hit=True,
                message="Fonte não solicitada nesta execução parcial.",
            ),
        )

    def _with_total_sa_fallback(
        self,
        online_frame: pd.DataFrame,
        status: SourceRunStatus,
        window: TimeWindow,
    ) -> tuple[pd.DataFrame, SourceRunStatus]:
        has_total_sa = (
            not online_frame.loc[online_frame["serie"].eq("TOTALSA")].empty if not online_frame.empty else False
        )
        if has_total_sa or not self.market_snapshot.exists():
            return online_frame, status
        snapshot = pd.read_csv(self.market_snapshot)
        date_column = "DATE" if "DATE" in snapshot.columns else snapshot.columns[0]
        value_column = "TOTALSA" if "TOTALSA" in snapshot.columns else snapshot.columns[1]
        fallback = pd.DataFrame(
            {
                "data": pd.to_datetime(snapshot[date_column], errors="coerce"),
                "disponivel_em": pd.to_datetime(snapshot[date_column], errors="coerce"),
                "serie": "TOTALSA",
                "feature": "vendas_saar_milhoes",
                "valor": pd.to_numeric(snapshot[value_column], errors="coerce"),
            }
        ).dropna()
        fallback = fallback.loc[(fallback["data"] >= window.start) & (fallback["data"] <= window.as_of)].copy()
        merged = fallback if online_frame.empty else pd.concat([online_frame, fallback], ignore_index=True)
        message = "TOTALSA carregada do snapshot local; macro online indisponível ou sem chave."
        return merged, status.model_copy(
            update={
                "state": SourceState.DEGRADED,
                "rows": len(merged),
                "coverage_start": merged["data"].min() if not merged.empty else None,
                "coverage_end": merged["data"].max() if not merged.empty else None,
                "message": message,
            }
        )

    @staticmethod
    def _build_market_features(fred: pd.DataFrame, eia: pd.DataFrame, window: TimeWindow) -> pd.DataFrame:
        macro = monthly_wide_features(
            fred,
            date_column="data",
            available_column="disponivel_em",
            feature_column="feature",
            value_column="valor",
            as_of=window.as_of,
            aggregation="last",
        )
        energy = monthly_wide_features(
            eia,
            date_column="data",
            available_column="disponivel_em",
            feature_column="feature",
            value_column="valor",
            as_of=window.as_of,
            aggregation="mean",
        )
        market = macro.join(energy, how="outer").sort_index()
        if {"gasoline_regular", "electricity_residential"}.issubset(market.columns):
            market["diferencial_gasolina_eletricidade"] = market["gasoline_regular"] - market["electricity_residential"]
        if {"gasoline_regular", "diesel"}.issubset(market.columns):
            market["diferencial_gasolina_diesel"] = market["gasoline_regular"] - market["diesel"]
        market = add_lagged_changes(market, market.columns)
        market.index.name = "mes"
        return market

    @staticmethod
    def _build_event_features(news: pd.DataFrame, window: TimeWindow) -> pd.DataFrame:
        if news.empty:
            return pd.DataFrame(index=pd.MultiIndex.from_arrays([[], [], []], names=["mes", "marca", "modelo"]))
        assert_no_future_availability(news, available_column="disponivel_em", as_of=window.as_of)
        prepared = news.copy()
        prepared["mes"] = pd.to_datetime(prepared["publicado_em"]).dt.to_period("M").dt.to_timestamp()
        prepared["marca"] = prepared["marca"].fillna("MERCADO")
        prepared["modelo"] = prepared["modelo"].fillna("__all__")
        index_columns = ["mes", "marca", "modelo"]
        totals = prepared.groupby(index_columns, as_index=False).agg(
            cobertura_midia=("article_id", "nunique"),
            sentimento_medio=("sentimento", "mean"),
        )
        themes = (
            prepared.groupby([*index_columns, "tema"], as_index=False)["article_id"]
            .nunique()
            .pivot(index=index_columns, columns="tema", values="article_id")
            .fillna(0)
            .add_prefix("noticias_")
            .reset_index()
        )
        result = totals.merge(themes, on=index_columns, how="left")
        theme_columns = [column for column in result.columns if column.startswith("noticias_")]
        result["intensidade_tematica"] = result[theme_columns].sum(axis=1) if theme_columns else 0
        return result.set_index(index_columns).sort_index()

    def _persist(
        self,
        fred: pd.DataFrame,
        eia: pd.DataFrame,
        news: pd.DataFrame,
        market_features: pd.DataFrame,
        event_features: pd.DataFrame,
        statuses: list[SourceRunStatus],
    ) -> None:
        self.store.write(
            SourceName.FRED,
            fred,
            date_column="data",
            dedupe_columns=("data", "serie", "disponivel_em"),
        )
        self.store.write(
            SourceName.EIA,
            eia,
            date_column="data",
            dedupe_columns=("data", "serie", "disponivel_em"),
        )
        self.store.write(
            SourceName.NEWS,
            news,
            date_column="publicado_em",
            dedupe_columns=("article_id",),
            entity_columns=("marca", "modelo"),
        )
        market_frame = market_features.reset_index()
        self.store.write(
            SourceName.FEATURE_BUILDER,
            market_frame,
            date_column="mes",
            dedupe_columns=("mes",),
        )
        if not event_features.empty:
            events = event_features.reset_index()
            self.store.write(
                SourceName.FEATURE_BUILDER,
                events,
                date_column="mes",
                dedupe_columns=("mes", "marca", "modelo"),
                entity_columns=("marca", "modelo"),
            )
        self.store.record_statuses(statuses)

    @staticmethod
    def _builder_state(statuses: list[SourceRunStatus]) -> SourceState:
        if all(status.state == SourceState.UNAVAILABLE for status in statuses):
            return SourceState.DEGRADED
        if any(status.state in {SourceState.UNAVAILABLE, SourceState.DEGRADED} for status in statuses):
            return SourceState.DEGRADED
        if all(status.state == SourceState.CACHED for status in statuses):
            return SourceState.CACHED
        return SourceState.FRESH
