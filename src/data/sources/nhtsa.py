"""Cliente público NHTSA para eventos de recall e reclamações por veículo."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import httpx
import pandas as pd

from ..contracts import NHTSATarget, SourceName, SourcePayload, SourceRunStatus, SourceState, TimeWindow
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

    async def fetch_target(self, target: NHTSATarget, window: TimeWindow) -> SourcePayload:
        """Consolida recalls e reclamações de um veículo monitorado."""
        recalls, complaints = await asyncio.gather(
            self.fetch_recalls(target.make, target.model, target.model_year, window),
            self.fetch_complaints(target.make, target.model, target.model_year, window),
        )
        frames = [payload.frame for payload in (recalls, complaints) if not payload.frame.empty]
        frame = pd.concat(frames, ignore_index=True) if frames else self._empty_frame()
        if not frame.empty:
            frame = (
                frame.drop_duplicates(["evento_id", "tipo_evento"]).sort_values("disponivel_em").reset_index(drop=True)
            )
        components = [recalls.status, complaints.status]
        return SourcePayload(
            frame=frame,
            status=SourceRunStatus(
                source=self.source,
                state=self._combined_state(components),
                rows=len(frame),
                latency_ms=sum(status.latency_ms or 0 for status in components),
                coverage_start=frame["disponivel_em"].min() if not frame.empty else None,
                coverage_end=frame["disponivel_em"].max() if not frame.empty else None,
                cache_hit=all(status.cache_hit for status in components),
                message=f"{target.entity_label}: {len(frame)} eventos de segurança elegíveis.",
            ),
            metadata={"target": target.model_dump(mode="json"), "components": components},
        )

    async def fetch_many(
        self, targets: Iterable[NHTSATarget], window: TimeWindow, concurrency: int = 3
    ) -> SourcePayload:
        """Consulta uma watchlist limitada sem sobrecarregar a API pública."""
        target_list = list(targets)
        if not target_list:
            return SourcePayload(
                frame=self._empty_frame(),
                status=SourceRunStatus(
                    source=self.source,
                    state=SourceState.DEGRADED,
                    rows=0,
                    message="Watchlist NHTSA vazia; nenhuma consulta realizada.",
                ),
            )
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_limited(target: NHTSATarget) -> SourcePayload:
            async with semaphore:
                return await self.fetch_target(target, window)

        payloads = await asyncio.gather(*(fetch_limited(target) for target in target_list))
        frames = [payload.frame for payload in payloads if not payload.frame.empty]
        frame = pd.concat(frames, ignore_index=True) if frames else self._empty_frame()
        if not frame.empty:
            frame = (
                frame.drop_duplicates(["evento_id", "tipo_evento"]).sort_values("disponivel_em").reset_index(drop=True)
            )
        statuses = [payload.status for payload in payloads]
        return SourcePayload(
            frame=frame,
            status=SourceRunStatus(
                source=self.source,
                state=self._combined_state(statuses),
                rows=len(frame),
                latency_ms=sum(status.latency_ms or 0 for status in statuses),
                coverage_start=frame["disponivel_em"].min() if not frame.empty else None,
                coverage_end=frame["disponivel_em"].max() if not frame.empty else None,
                cache_hit=bool(statuses) and all(status.cache_hit for status in statuses),
                message=f"Watchlist NHTSA: {len(target_list)} veículos; {len(frame)} eventos elegíveis.",
            ),
            metadata={"targets": [target.model_dump(mode="json") for target in target_list], "components": statuses},
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
                record.get("ReportReceivedDate") or record.get("dateComplaintFiled") or record.get("reportDate")
            )
            available_at = NHTSAClient._parse_event_date(date_value, event_type)
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

    @staticmethod
    def _parse_event_date(value: object, event_type: str) -> pd.Timestamp:
        """Normaliza os formatos distintos de data retornados por recalls e reclamações."""
        preferred_format = "%d/%m/%Y" if event_type == "recall" else "%m/%d/%Y"
        parsed = pd.to_datetime(value, format=preferred_format, errors="coerce")
        return parsed if not pd.isna(parsed) else pd.to_datetime(value, errors="coerce")

    def _unavailable_payload(self, message: str) -> SourcePayload:
        return SourcePayload(
            frame=self._empty_frame(),
            status=SourceRunStatus(source=self.source, state=SourceState.UNAVAILABLE, rows=0, message=message),
        )

    @staticmethod
    def _empty_frame() -> pd.DataFrame:
        return pd.DataFrame(columns=["evento_id", "disponivel_em", "marca", "modelo", "ano_modelo", "tipo_evento"])

    @staticmethod
    def _combined_state(statuses: list[SourceRunStatus]) -> SourceState:
        if statuses and all(status.state == SourceState.UNAVAILABLE for status in statuses):
            return SourceState.UNAVAILABLE
        if any(status.state in {SourceState.UNAVAILABLE, SourceState.DEGRADED} for status in statuses):
            return SourceState.DEGRADED
        if statuses and all(status.state == SourceState.CACHED for status in statuses):
            return SourceState.CACHED
        return SourceState.FRESH
