"""Cliente público NHTSA para eventos de recall e reclamações por veículo."""

from __future__ import annotations

from collections.abc import Iterable

import httpx
import pandas as pd

from ..contracts import SourceName, SourcePayload, SourceRunStatus, SourceState, TimeWindow
from ..settings import FeatureSettings
from .base import BaseAPIClient, SourceUnavailableError

NHTSA_RECALLS_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"
NHTSA_COMPLAINTS_URL = "https://api.nhtsa.gov/complaints/complaintsByVehicle"


class NHTSAClient(BaseAPIClient):
    """Consulta eventos públicos de segurança sem armazenar texto desestruturado como feature."""

    source = SourceName.NHTSA

    def __init__(self, settings: FeatureSettings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(settings, transport=transport)

    async def fetch_recalls(self, make: str, model: str, model_year: int, window: TimeWindow) -> SourcePayload:
        """Obtém campanhas de recall com data de relatório elegível para a janela temporal."""
        return await self._fetch_vehicle_events(
            NHTSA_RECALLS_URL,
            event_type="recall",
            make=make,
            model=model,
            model_year=model_year,
            window=window,
        )

    async def fetch_complaints(self, make: str, model: str, model_year: int, window: TimeWindow) -> SourcePayload:
        """Obtém reclamações com data de recebimento elegível para a janela temporal."""
        return await self._fetch_vehicle_events(
            NHTSA_COMPLAINTS_URL,
            event_type="complaint",
            make=make,
            model=model,
            model_year=model_year,
            window=window,
        )

    async def _fetch_vehicle_events(
        self,
        url: str,
        *,
        event_type: str,
        make: str,
        model: str,
        model_year: int,
        window: TimeWindow,
    ) -> SourcePayload:
        try:
            response = await self.get_json(
                url,
                params={"make": make, "model": model, "modelYear": model_year},
            )
        except SourceUnavailableError as error:
            return self._unavailable_payload(str(error))
        records = response.payload.get("results", [])
        frame = self._parse_events(records, event_type, make, model, model_year, window)
        state = SourceState.CACHED if response.cache_hit else SourceState.FRESH
        if frame.empty:
            state = SourceState.DEGRADED
        return SourcePayload(
            frame=frame,
            status=SourceRunStatus(
                source=self.source,
                state=state,
                rows=len(frame),
                latency_ms=response.latency_ms,
                coverage_start=frame["disponivel_em"].min() if not frame.empty else None,
                coverage_end=frame["disponivel_em"].max() if not frame.empty else None,
                cache_hit=response.cache_hit,
                message=f"{event_type}: {len(frame)} eventos com data elegível.",
            ),
            metadata={"event_type": event_type, "make": make, "model": model, "model_year": model_year},
        )

    @staticmethod
    def _parse_events(
        records: Iterable[dict[str, object]],
        event_type: str,
        make: str,
        model: str,
        model_year: int,
        window: TimeWindow,
    ) -> pd.DataFrame:
        rows = []
        for record in records:
            date_value = (
                record.get("ReportReceivedDate")
                or record.get("dateComplaintFiled")
                or record.get("reportDate")
            )
            available_at = pd.to_datetime(date_value, errors="coerce")
            if pd.isna(available_at):
                continue
            if available_at.tzinfo is not None:
                available_at = available_at.tz_convert("UTC").tz_localize(None)
            if available_at < window.start or available_at > window.as_of:
                continue
            identifier = str(
                record.get("NHTSACampaignNumber")
                or record.get("odiNumber")
                or record.get("ODINumber")
                or f"{event_type}|{make}|{model}|{model_year}|{available_at.isoformat()}"
            )
            rows.append(
                {
                    "evento_id": identifier,
                    "disponivel_em": available_at,
                    "marca": make,
                    "modelo": model,
                    "ano_modelo": model_year,
                    "tipo_evento": event_type,
                }
            )
        return pd.DataFrame(
            rows, columns=["evento_id", "disponivel_em", "marca", "modelo", "ano_modelo", "tipo_evento"]
        )

    def _unavailable_payload(self, message: str) -> SourcePayload:
        return SourcePayload(
            frame=pd.DataFrame(columns=["evento_id", "disponivel_em", "marca", "modelo", "ano_modelo", "tipo_evento"]),
            status=SourceRunStatus(source=self.source, state=SourceState.UNAVAILABLE, rows=0, message=message),
        )
