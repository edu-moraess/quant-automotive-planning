"""Cliente assíncrono da EIA Open Data API para custos de energia."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta

import httpx
import pandas as pd

from ..contracts import SourceName, SourcePayload, SourceRunStatus, SourceState, TimeWindow
from ..settings import FeatureSettings
from .base import BaseAPIClient, SourceUnavailableError

EIA_SERIES_URL = "https://api.eia.gov/v2/seriesid/{series_id}"


class EIAClient(BaseAPIClient):
    """Obtém preços de energia e registra a disponibilidade com lag explícito."""

    source = SourceName.EIA

    def __init__(self, settings: FeatureSettings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(settings, transport=transport)

    async def fetch_series(
        self,
        series_id: str,
        feature_name: str,
        window: TimeWindow,
        publication_lag_days: int,
    ) -> SourcePayload:
        """Busca uma série EIA e aplica o lag conservador de publicação informado."""
        api_key = self.settings.secret_value("eia")
        if not api_key:
            return self._unavailable_payload("EIA_API_KEY ausente; nenhuma consulta online realizada.")

        try:
            response = await self.get_json(
                EIA_SERIES_URL.format(series_id=series_id),
                params={"api_key": api_key, "length": 5_000},
            )
        except SourceUnavailableError as error:
            return self._unavailable_payload(str(error))

        records = response.payload.get("response", {}).get("data", [])
        frame = pd.DataFrame(records)
        parsed = self._parse_records(frame, series_id, feature_name, publication_lag_days, window)
        state = SourceState.CACHED if response.cache_hit else SourceState.FRESH
        if parsed.empty:
            state = SourceState.DEGRADED
        status = SourceRunStatus(
            source=self.source,
            state=state,
            rows=len(parsed),
            latency_ms=response.latency_ms,
            coverage_start=parsed["data"].min() if not parsed.empty else None,
            coverage_end=parsed["data"].max() if not parsed.empty else None,
            cache_hit=response.cache_hit,
            message=f"{series_id}: {len(parsed)} observações elegíveis após lag de publicação.",
        )
        return SourcePayload(
            frame=parsed,
            status=status,
            metadata={
                "series_id": series_id,
                "feature_name": feature_name,
                "publication_lag_days": publication_lag_days,
            },
        )

    async def fetch_many(
        self,
        series: Mapping[str, str],
        window: TimeWindow,
        publication_lags: Mapping[str, int],
    ) -> SourcePayload:
        """Busca o conjunto de energia e consolida cobertura e falhas parciais."""
        payloads = await asyncio.gather(
            *(
                self.fetch_series(
                    series_id,
                    feature_name,
                    window,
                    publication_lags.get(feature_name, 7),
                )
                for feature_name, series_id in series.items()
            )
        )
        frames = [payload.frame for payload in payloads if not payload.frame.empty]
        combined = pd.concat(frames, ignore_index=True) if frames else self._empty_frame()
        statuses = [payload.status for payload in payloads]
        state = self._combined_state(statuses)
        return SourcePayload(
            frame=combined,
            status=SourceRunStatus(
                source=self.source,
                state=state,
                rows=len(combined),
                latency_ms=sum(item.latency_ms or 0 for item in statuses),
                coverage_start=combined["data"].min() if not combined.empty else None,
                coverage_end=combined["data"].max() if not combined.empty else None,
                cache_hit=bool(statuses) and all(item.cache_hit for item in statuses),
                message=f"{len(series)} séries de energia solicitadas; {len(combined)} observações consolidadas.",
            ),
            metadata={"series": dict(series), "components": statuses},
        )

    @staticmethod
    def _parse_records(
        frame: pd.DataFrame,
        series_id: str,
        feature_name: str,
        publication_lag_days: int,
        window: TimeWindow,
    ) -> pd.DataFrame:
        if frame.empty:
            return EIAClient._empty_frame()
        parsed = frame.copy()
        parsed["data"] = pd.to_datetime(parsed.get("period"), errors="coerce")
        parsed["valor"] = pd.to_numeric(parsed.get("value"), errors="coerce")
        parsed["disponivel_em"] = parsed["data"] + timedelta(days=int(publication_lag_days))
        parsed = parsed.loc[
            parsed["data"].notna()
            & parsed["valor"].notna()
            & parsed["data"].ge(window.start)
            & parsed["disponivel_em"].le(window.as_of)
        ].copy()
        parsed["serie"] = series_id
        parsed["feature"] = feature_name
        return parsed[["data", "disponivel_em", "serie", "feature", "valor"]].sort_values("data").reset_index(drop=True)

    def _unavailable_payload(self, message: str) -> SourcePayload:
        return SourcePayload(
            frame=self._empty_frame(),
            status=SourceRunStatus(source=self.source, state=SourceState.UNAVAILABLE, rows=0, message=message),
        )

    @staticmethod
    def _empty_frame() -> pd.DataFrame:
        return pd.DataFrame(columns=["data", "disponivel_em", "serie", "feature", "valor"])

    @staticmethod
    def _combined_state(statuses: list[SourceRunStatus]) -> SourceState:
        if statuses and all(status.state == SourceState.UNAVAILABLE for status in statuses):
            return SourceState.UNAVAILABLE
        if any(status.state in {SourceState.UNAVAILABLE, SourceState.DEGRADED} for status in statuses):
            return SourceState.DEGRADED
        if statuses and all(status.state == SourceState.CACHED for status in statuses):
            return SourceState.CACHED
        return SourceState.FRESH
