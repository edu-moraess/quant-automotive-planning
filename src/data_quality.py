"""Perfis de qualidade e proveniência para fontes públicas rastreáveis."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from data.governance import assess_schema, compute_dataset_version, staleness


@dataclass(frozen=True)
class DatasetHealth:
    dataset: str
    source_status: str
    rows: int
    columns: int
    period_start: str | None
    period_end: str | None
    last_observation: str | None
    missing_rate_pct: float
    duplicate_rows: int
    invalid_rows: int
    outlier_rows: int
    frequency_gaps: int | None
    snapshot_path: str | None
    snapshot_sha256: str | None
    snapshot_modified_utc: str | None
    notes: str
    dataset_version: str | None = None
    schema_status: str = "not_checked"
    schema_missing_columns: tuple[str, ...] = ()
    schema_unexpected_columns: tuple[str, ...] = ()
    stale: bool | None = None
    staleness_days: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def snapshot_metadata(path: str | Path | None) -> dict[str, str | None]:
    if path is None:
        return {"snapshot_path": None, "snapshot_sha256": None, "snapshot_modified_utc": None}
    snapshot = Path(path)
    if not snapshot.exists():
        return {"snapshot_path": str(snapshot), "snapshot_sha256": None, "snapshot_modified_utc": None}
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    modified = datetime.fromtimestamp(snapshot.stat().st_mtime, tz=UTC).isoformat()
    return {"snapshot_path": str(snapshot), "snapshot_sha256": digest, "snapshot_modified_utc": modified}


def _valid_datetimes(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="coerce").dropna().sort_values().drop_duplicates().reset_index(drop=True)


def _monthly_gaps(dates: pd.Series) -> int | None:
    if len(dates) < 2:
        return None
    expected = pd.date_range(
        dates.min().to_period("M").to_timestamp(), dates.max().to_period("M").to_timestamp(), freq="MS"
    )
    observed = pd.DatetimeIndex(dates.dt.to_period("M").dt.to_timestamp())
    return int(len(expected.difference(observed)))


def _iqr_outliers(values: pd.Series) -> int:
    series = pd.to_numeric(values, errors="coerce").dropna()
    if len(series) < 8:
        return 0
    q1, q3 = series.quantile([0.25, 0.75])
    spread = q3 - q1
    if np.isclose(spread, 0):
        return 0
    return int(((series < q1 - 1.5 * spread) | (series > q3 + 1.5 * spread)).sum())


def profile_time_series(
    frame: pd.DataFrame,
    dataset: str,
    date_column: str,
    value_columns: Iterable[str],
    source_status: str,
    snapshot_path: str | Path | None,
    notes: str,
    *,
    expected_columns: Iterable[str] | None = None,
    max_staleness_days: float | None = None,
    as_of: object | None = None,
) -> DatasetHealth:
    if date_column not in frame.columns:
        raise ValueError(f"{dataset}: coluna temporal ausente: {date_column}")
    values = [column for column in value_columns if column in frame.columns]
    if not values:
        raise ValueError(f"{dataset}: nenhuma coluna de valor disponível.")
    schema = assess_schema(frame, [date_column, *value_columns], expected_columns=expected_columns)
    if schema.missing:
        raise ValueError(f"{dataset}: schema inválido; faltam {list(schema.missing)}")
    dates = _valid_datetimes(frame[date_column])
    missing = frame[[date_column, *values]].isna().sum().sum()
    total_cells = max(len(frame) * (len(values) + 1), 1)
    numeric = frame[values].apply(pd.to_numeric, errors="coerce")
    invalid_rows = int(numeric.isna().all(axis=1).sum())
    metadata = snapshot_metadata(snapshot_path)
    version = compute_dataset_version(frame, source=dataset, frequency="monthly")
    stale, staleness_days = staleness(
        dates.max() if not dates.empty else None,
        as_of=as_of,
        max_age_days=max_staleness_days if max_staleness_days is not None else float("inf"),
    )
    return DatasetHealth(
        dataset=dataset,
        source_status=source_status,
        rows=int(len(frame)),
        columns=int(len(frame.columns)),
        period_start=dates.min().strftime("%Y-%m-%d") if not dates.empty else None,
        period_end=dates.max().strftime("%Y-%m-%d") if not dates.empty else None,
        last_observation=dates.max().strftime("%Y-%m-%d") if not dates.empty else None,
        missing_rate_pct=float(missing / total_cells * 100),
        duplicate_rows=int(frame.duplicated().sum()),
        invalid_rows=invalid_rows,
        outlier_rows=int(sum(_iqr_outliers(numeric[column]) for column in values)),
        frequency_gaps=_monthly_gaps(dates),
        notes=notes,
        dataset_version=version,
        schema_status=schema.status,
        schema_missing_columns=schema.missing,
        schema_unexpected_columns=schema.unexpected,
        stale=stale,
        staleness_days=staleness_days,
        **metadata,
    )


def profile_vehicle_catalog(
    frame: pd.DataFrame,
    source_status: str,
    snapshot_path: str | Path | None,
    *,
    expected_columns: Iterable[str] | None = None,
    max_staleness_days: float | None = None,
    as_of: object | None = None,
) -> DatasetHealth:
    required = ["id", "year", "make", "model", "comb08"]
    missing_columns = [column for column in required if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"EPA: schema inválido; faltam {missing_columns}")
    core = frame[required].copy()
    core["year"] = pd.to_numeric(core["year"], errors="coerce")
    core["comb08"] = pd.to_numeric(core["comb08"], errors="coerce")
    invalid = (
        core["id"].isna()
        | core["year"].isna()
        | ~core["year"].between(1984, 2030)
        | core["make"].fillna("").astype(str).str.strip().eq("")
        | core["model"].fillna("").astype(str).str.strip().eq("")
        | core["comb08"].isna()
        | core["comb08"].le(0)
    )
    metadata = snapshot_metadata(snapshot_path)
    version = compute_dataset_version(frame, source="EPA vehicles", frequency="annual")
    stale, staleness_days = staleness(
        core["year"].max() if core["year"].notna().any() else None,
        as_of=as_of,
        max_age_days=max_staleness_days if max_staleness_days is not None else float("inf"),
    )
    schema = assess_schema(frame, required, expected_columns=expected_columns)
    return DatasetHealth(
        dataset="EPA vehicles",
        source_status=source_status,
        rows=int(len(frame)),
        columns=int(len(frame.columns)),
        period_start=str(int(core["year"].min())) if core["year"].notna().any() else None,
        period_end=str(int(core["year"].max())) if core["year"].notna().any() else None,
        last_observation=str(int(core["year"].max())) if core["year"].notna().any() else None,
        missing_rate_pct=float(core.isna().sum().sum() / max(core.size, 1) * 100),
        duplicate_rows=int(frame["id"].duplicated().sum()),
        invalid_rows=int(invalid.sum()),
        outlier_rows=_iqr_outliers(core["comb08"]),
        frequency_gaps=None,
        notes="Outliers usam IQR de `comb08`; eles são sinalizados, não removidos automaticamente.",
        dataset_version=version,
        schema_status=schema.status,
        schema_missing_columns=schema.missing,
        schema_unexpected_columns=schema.unexpected,
        stale=stale,
        staleness_days=staleness_days,
        **metadata,
    )


def health_table(health_items: Iterable[DatasetHealth]) -> pd.DataFrame:
    rows = [item.to_dict() for item in health_items]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)
