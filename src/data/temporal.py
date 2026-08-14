"""Regras de disponibilidade point-in-time e agregações mensais sem vazamento."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


class TemporalLeakageError(ValueError):
    """Indica que uma feature usa informação indisponível na data de corte."""


def enforce_point_in_time(
    frame: pd.DataFrame,
    *,
    available_column: str,
    as_of: pd.Timestamp,
) -> pd.DataFrame:
    """Retém somente linhas publicadas até a data de corte solicitada."""
    if frame.empty:
        return frame.copy()
    if available_column not in frame.columns:
        raise TemporalLeakageError(f"Coluna de disponibilidade ausente: {available_column}")
    result = frame.copy()
    result[available_column] = pd.to_datetime(result[available_column], errors="coerce")
    if result[available_column].isna().any():
        raise TemporalLeakageError("Há observações sem data de disponibilidade.")
    cutoff = _naive_timestamp(as_of)
    leaked = result[available_column].gt(cutoff)
    if leaked.any():
        result = result.loc[~leaked].copy()
    return result


def assert_no_future_availability(
    frame: pd.DataFrame,
    *,
    available_column: str,
    as_of: pd.Timestamp,
) -> None:
    """Valida que nenhuma observação remanescente excede a data de corte."""
    if frame.empty:
        return
    available = pd.to_datetime(frame[available_column], errors="coerce")
    cutoff = _naive_timestamp(as_of)
    if available.isna().any() or available.gt(cutoff).any():
        raise TemporalLeakageError("Feature contém dados ausentes ou disponíveis após a data de corte.")


def monthly_wide_features(
    frame: pd.DataFrame,
    *,
    date_column: str,
    available_column: str,
    feature_column: str,
    value_column: str,
    as_of: pd.Timestamp,
    aggregation: str,
) -> pd.DataFrame:
    """Agrega observações elegíveis em uma matriz mensal indexada por competência."""
    eligible = enforce_point_in_time(frame, available_column=available_column, as_of=as_of)
    if eligible.empty:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="mes"))
    prepared = eligible.copy()
    prepared[date_column] = pd.to_datetime(prepared[date_column], errors="coerce")
    prepared[value_column] = pd.to_numeric(prepared[value_column], errors="coerce")
    prepared = prepared.dropna(subset=[date_column, feature_column, value_column])
    prepared["mes"] = prepared[date_column].dt.to_period("M").dt.to_timestamp()
    grouped = prepared.groupby(["mes", feature_column], as_index=False)[value_column]
    if aggregation == "mean":
        monthly = grouped.mean()
    elif aggregation == "last":
        monthly = (
            prepared.sort_values(date_column)
            .groupby(["mes", feature_column], as_index=False)
            .last()[["mes", feature_column, value_column]]
        )
    else:
        raise ValueError(f"Agregação não suportada: {aggregation}")
    return monthly.pivot(index="mes", columns=feature_column, values=value_column).sort_index()


def add_lagged_changes(frame: pd.DataFrame, columns: Iterable[str], lags: Iterable[int] = (1, 3, 12)) -> pd.DataFrame:
    """Cria defasagens e variações percentuais usando somente meses anteriores."""
    result = frame.copy().sort_index()
    for column in columns:
        if column not in result.columns:
            continue
        for lag in lags:
            result[f"{column}_lag_{lag}m"] = result[column].shift(lag)
            result[f"{column}_var_{lag}m_pct"] = result[column].pct_change(lag) * 100
    return result


def _naive_timestamp(value: pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp
