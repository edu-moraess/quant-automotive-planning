"""Cliente assíncrono da FRED API para séries macroeconômicas e automotivas."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

import httpx
import pandas as pd

from ..contracts import SourceName, SourcePayload, SourceRunStatus, SourceState, TimeWindow
from ..settings import FeatureSettings
from .base import BaseAPIClient, SourceUnavailableError

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


class FREDClient(BaseAPIClient):
    """Obtém observações FRED respeitando a data de corte do backtest."""

    source = SourceName.FRED

    def __init__(self, settings: FeatureSettings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(settings, transport=transport)

    async def fetch_series(
        self,
        series_id: str,
        feature_name: str,
        window: TimeWindow,
    ) -> SourcePayload:
        """Busca uma série e conserva somente valores publicados até `as_of`."""
        api_key = self.settings.secret_value("fred")
        if not api_key:
            return self._unavailable_payload("FRED_API_KEY ausente; usado fallback local quando existir.")

        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": window.start.strftime("%Y-%m-%d"),
            "observation_end": window.as_of.strftime("%Y-%m-%d"),
            "realtime_start": window.as_of.strftime("%Y-%m-%d"),
            "realtime_end": window.as_of.strftime("%Y-%m-%d"),
        }
        try:
            response = await self.get_json(FRED_OBSERVATIONS_URL, params=params)
        except SourceUnavailableError as error:
            return self._unavailable_payload(str(error))

        observations = response.payload.get("observations", [])
        frame = pd.DataFrame(observations)
        if frame.empty:
            return SourcePayload(
                frame=self._empty_frame(),
                status=SourceRunStatus(
                    source=self.source,
                    state=SourceState.DEGRADED,
                    rows=0,
                    latency_ms=response.latency_ms,
                    cache_hit=response.cache_hit,
                    message=f"{series_id}: nenhuma observação retornada.",
                ),
                metadata={"series_id": series_id, "feature_name": feature_name},
            )

        parsed = self._parse_observations(frame, series_id, feature_name, window)
        state = SourceState.CACHED if response.cache_hit else SourceState.FRESH
        status = SourceRunStatus(
            source=self.source,
            state=state,
            rows=len(parsed),
            latency_ms=response.latency_ms,
            coverage_start=parsed["data"].min() if not parsed.empty else None,
            coverage_end=parsed["data"].max() if not parsed.empty else None,
            cache_hit=response.cache_hit,
            message=f"{series_id}: {len(parsed)} observações elegíveis.",
        )
        return SourcePayload(
            frame=parsed, status=status, metadata={"series_id": series_id, "feature_name": feature_name}
        )

    async def fetch_many(self, series: Mapping[str, str], window: TimeWindow) -> SourcePayload:
        """Busca várias séries em paralelo e consolida seus estados operacionais."""
        payloads = await asyncio.gather(
            *(self.fetch_series(series_id, feature_name, window) for series_id, feature_name in series.items())
        )
        frames = [payload.frame for payload in payloads if not payload.frame.empty]
        combined = pd.concat(frames, ignore_index=True) if frames else self._empty_frame()
        statuses = [payload.status for payload in payloads]
        state = self._combined_state(statuses)
        status = SourceRunStatus(
            source=self.source,
            state=state,
            rows=len(combined),
            latency_ms=sum(item.latency_ms or 0 for item in statuses),
            coverage_start=combined["data"].min() if not combined.empty else None,
            coverage_end=combined["data"].max() if not combined.empty else None,
            cache_hit=bool(statuses) and all(item.cache_hit for item in statuses),
            message=f"{len(series)} séries solicitadas; {len(combined)} observações consolidadas.",
        )
        return SourcePayload(frame=combined, status=status, metadata={"series": dict(series), "components": statuses})

    @staticmethod
    def _parse_observations(
        frame: pd.DataFrame,
        series_id: str,
        feature_name: str,
        window: TimeWindow,
    ) -> pd.DataFrame:
        parsed = frame.copy()
        parsed["data"] = pd.to_datetime(parsed["date"], errors="coerce")
        parsed["valor"] = pd.to_numeric(parsed["value"], errors="coerce")
        parsed["disponivel_em"] = pd.to_datetime(parsed.get("realtime_start"), errors="coerce")
        parsed["disponivel_em"] = parsed["disponivel_em"].fillna(parsed["data"])
        parsed = parsed.loc[
            parsed["data"].notna()
            & parsed["valor"].notna()
            & parsed["data"].le(window.as_of)
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
