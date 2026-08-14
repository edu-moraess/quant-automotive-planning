"""Cliente local da EPA para atributos técnicos de configurações automotivas."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import EPA_SNAPSHOT
from vehicle_intelligence import load_vehicle_data

from ..contracts import SourceName, SourcePayload, SourceRunStatus, SourceState


class EPAClient:
    """Expõe o catálogo EPA validado como uma fonte técnica sem dependência de segredo."""

    source = SourceName.EPA

    def __init__(self, snapshot_path: Path = EPA_SNAPSHOT) -> None:
        self.snapshot_path = snapshot_path

    def load_catalog(self) -> SourcePayload:
        """Carrega o snapshot local e seleciona atributos úteis para demanda por produto."""
        if not self.snapshot_path.exists():
            return SourcePayload(
                frame=self._empty_frame(),
                status=SourceRunStatus(
                    source=self.source,
                    state=SourceState.UNAVAILABLE,
                    rows=0,
                    message=f"Snapshot EPA ausente: {self.snapshot_path.name}.",
                ),
            )
        catalog = load_vehicle_data(self.snapshot_path)
        columns = [
            column
            for column in [
                "id",
                "year",
                "make",
                "model",
                "VClass",
                "fuelType1",
                "powertrain",
                "comb08",
                "co2TailpipeGpm",
                "range",
                "cylinders",
                "displ",
                "drive",
                "trany",
            ]
            if column in catalog.columns
        ]
        frame = catalog[columns].copy()
        frame["ano_modelo"] = pd.to_numeric(frame.get("year"), errors="coerce")
        return SourcePayload(
            frame=frame,
            status=SourceRunStatus(
                source=self.source,
                state=SourceState.CACHED,
                rows=len(frame),
                coverage_start=pd.Timestamp(frame["ano_modelo"].min(), 1, 1)
                if frame["ano_modelo"].notna().any()
                else None,
                coverage_end=pd.Timestamp(frame["ano_modelo"].max(), 1, 1)
                if frame["ano_modelo"].notna().any()
                else None,
                cache_hit=True,
                message="Catálogo EPA carregado do snapshot técnico validado.",
            ),
            metadata={"snapshot_path": str(self.snapshot_path)},
        )

    @staticmethod
    def _empty_frame() -> pd.DataFrame:
        return pd.DataFrame()
