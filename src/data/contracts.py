"""Contratos tipados para ingestão, disponibilidade temporal e features automotivas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceName(StrEnum):
    """Identifica a origem de uma tabela persistida no feature store."""

    FRED = "fred"
    EIA = "eia"
    NEWS = "news"
    EPA = "epa"
    NHTSA = "nhtsa"
    FEATURE_BUILDER = "feature_builder"


class SourceState(StrEnum):
    """Representa o resultado operacional de uma atualização de fonte."""

    FRESH = "fresh"
    CACHED = "cached"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


class TimeWindow(BaseModel):
    """Define a janela de observação disponível para uma execução point-in-time."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    start: pd.Timestamp
    as_of: pd.Timestamp

    @field_validator("start", "as_of", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: object) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("UTC").tz_localize(None)
        return timestamp

    @field_validator("as_of")
    @classmethod
    def validate_window(cls, value: pd.Timestamp, info: Any) -> pd.Timestamp:
        start = info.data.get("start")
        if start is not None and value < start:
            raise ValueError("A data de corte não pode anteceder o início da janela.")
        return value

    @property
    def month_start(self) -> pd.Timestamp:
        """Retorna o início do primeiro mês elegível."""
        return self.start.to_period("M").to_timestamp()

    @property
    def month_end(self) -> pd.Timestamp:
        """Retorna o início do último mês elegível."""
        return self.as_of.to_period("M").to_timestamp()


class NewsQuery(BaseModel):
    """Configura uma busca rastreável de evento automotivo."""

    model_config = ConfigDict(frozen=True)

    query_id: str = Field(min_length=3, max_length=80)
    query: str = Field(min_length=3)
    brand: str | None = None
    model: str | None = None
    theme: str = Field(min_length=3, max_length=40)
    language: str = "en"


class SourceRunStatus(BaseModel):
    """Resume cobertura, latência e disponibilidade de uma execução de fonte."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    source: SourceName
    state: SourceState
    rows: int = Field(ge=0)
    requested_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: float | None = Field(default=None, ge=0)
    coverage_start: pd.Timestamp | None = None
    coverage_end: pd.Timestamp | None = None
    cache_hit: bool = False
    message: str | None = None

    @field_validator("coverage_start", "coverage_end", mode="before")
    @classmethod
    def normalize_optional_timestamp(cls, value: object) -> pd.Timestamp | None:
        if value is None or pd.isna(value):
            return None
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("UTC").tz_localize(None)
        return timestamp

    def to_display_row(self) -> dict[str, object]:
        """Converte o status em uma linha compacta para a interface."""
        return {
            "Fonte": self.source.value.upper(),
            "Status": self.state.value,
            "Linhas": self.rows,
            "Cobertura": self._coverage_label(),
            "Latência (ms)": None if self.latency_ms is None else round(self.latency_ms),
            "Cache": "sim" if self.cache_hit else "não",
            "Mensagem": self.message or "—",
        }

    def _coverage_label(self) -> str:
        if self.coverage_start is None or self.coverage_end is None:
            return "—"
        return f"{self.coverage_start:%Y-%m} a {self.coverage_end:%Y-%m}"


class SourcePayload(BaseModel):
    """Empacota dados tabulares e metadados operacionais de uma origem."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    frame: pd.DataFrame
    status: SourceRunStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeatureBuildResult(BaseModel):
    """Representa a saída final de uma execução do construtor de features."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    market_features: pd.DataFrame
    event_features: pd.DataFrame
    statuses: list[SourceRunStatus]
    as_of: pd.Timestamp

    @field_validator("as_of", mode="before")
    @classmethod
    def normalize_as_of(cls, value: object) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("UTC").tz_localize(None)
        return timestamp
