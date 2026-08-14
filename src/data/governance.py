"""Contratos de governança para schema, versão de dataset e frescor temporal."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd


class SchemaContractError(ValueError):
    """Indica que uma tabela não atende ao schema mínimo esperado."""


@dataclass(frozen=True)
class SchemaAssessment:
    """Resultado determinístico da comparação entre schema esperado e observado."""

    required: tuple[str, ...]
    actual: tuple[str, ...]
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]

    @property
    def status(self) -> str:
        if self.missing:
            return "invalid"
        if self.unexpected:
            return "drift"
        return "ok"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "required": list(self.required),
            "actual": list(self.actual),
            "missing": list(self.missing),
            "unexpected": list(self.unexpected),
        }


def assess_schema(
    frame: pd.DataFrame,
    required_columns: Iterable[str],
    *,
    expected_columns: Iterable[str] | None = None,
) -> SchemaAssessment:
    """Compara as colunas observadas com o contrato mínimo ou estrito informado."""
    required = tuple(dict.fromkeys(required_columns))
    actual = tuple(str(column) for column in frame.columns)
    expected = tuple(dict.fromkeys(expected_columns or required))
    missing = tuple(column for column in required if column not in frame.columns)
    unexpected = tuple(column for column in actual if column not in expected)
    return SchemaAssessment(required=required, actual=actual, missing=missing, unexpected=unexpected)


def assert_schema(
    frame: pd.DataFrame,
    required_columns: Iterable[str],
    *,
    expected_columns: Iterable[str] | None = None,
    dataset: str = "dataset",
) -> SchemaAssessment:
    """Valida schema mínimo/estrito e falha explicitamente em coluna ausente."""
    assessment = assess_schema(frame, required_columns, expected_columns=expected_columns)
    if assessment.missing:
        raise SchemaContractError(f"{dataset}: colunas ausentes: {list(assessment.missing)}")
    return assessment


def compute_dataset_version(
    frame: pd.DataFrame,
    *,
    source: str,
    frequency: str,
    schema_version: str = "1",
) -> str:
    """Calcula uma versão determinística a partir de schema, origem e conteúdo da tabela."""
    columns = sorted(str(column) for column in frame.columns)
    normalized = frame.loc[:, columns].copy()
    for column in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[column]):
            normalized[column] = pd.to_datetime(normalized[column], errors="coerce").astype("string")
    payload = normalized.to_json(orient="split", date_format="iso", double_precision=15, force_ascii=False)
    descriptor = f"source={source}|frequency={frequency}|schema={schema_version}|columns={columns}|{payload}"
    return hashlib.sha256(descriptor.encode("utf-8")).hexdigest()


def staleness(
    last_observation: object,
    *,
    as_of: object | None = None,
    max_age_days: float,
) -> tuple[bool | None, float | None]:
    """Avalia frescor em dias sem converter ausência de data em frescor artificial."""
    if last_observation is None or pd.isna(last_observation):
        return None, None
    observed = pd.Timestamp(last_observation)
    cutoff = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp(datetime.now(UTC))
    if observed.tzinfo is not None:
        observed = observed.tz_convert("UTC").tz_localize(None)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_convert("UTC").tz_localize(None)
    age_days = max(float((cutoff - observed).total_seconds() / 86_400), 0.0)
    return age_days > max_age_days, age_days


def canonical_time_series(
    frame: pd.DataFrame,
    *,
    date_column: str,
    value_column: str,
    source: str,
    frequency: str,
    retrieved_at: object,
    dataset_version: str | None = None,
) -> pd.DataFrame:
    """Normaliza uma série longa para o contrato date/value/source/frequency/retrieved_at/version."""
    assert_schema(frame, [date_column, value_column], dataset=source)
    result = frame[[date_column, value_column]].copy()
    result = result.rename(columns={date_column: "date", value_column: "value"})
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    result["value"] = pd.to_numeric(result["value"], errors="coerce")
    result = result.dropna(subset=["date", "value"]).sort_values("date").reset_index(drop=True)
    result["source"] = source
    result["frequency"] = frequency
    result["retrieved_at"] = pd.Timestamp(retrieved_at)
    result["dataset_version"] = dataset_version or compute_dataset_version(
        result[["date", "value"]], source=source, frequency=frequency
    )
    return result
