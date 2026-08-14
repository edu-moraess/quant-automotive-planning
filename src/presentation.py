"""Formata datas e horários para a interface."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

MISSING_DISPLAY = "—"


def _as_timestamp(value: object) -> pd.Timestamp | None:
    """Converte um valor em data sem falhar quando ele está vazio."""
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    return None if pd.isna(timestamp) else timestamp


def fmt_month_display(value: object) -> str:
    """Mostra uma competência mensal como MM/AAAA."""
    timestamp = _as_timestamp(value)
    return MISSING_DISPLAY if timestamp is None else timestamp.strftime("%m/%Y")


def fmt_date_display(value: object) -> str:
    """Mostra uma data como DD/MM/AAAA."""
    timestamp = _as_timestamp(value)
    return MISSING_DISPLAY if timestamp is None else timestamp.strftime("%d/%m/%Y")


def fmt_datetime_utc_display(value: object) -> str:
    """Mostra um horário em UTC para auditoria."""
    timestamp = _as_timestamp(value)
    if timestamp is None:
        return MISSING_DISPLAY
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.strftime("%d/%m/%Y %H:%M UTC")


def format_temporal_display(
    frame: pd.DataFrame,
    *,
    monthly_columns: Iterable[str] = (),
    daily_columns: Iterable[str] = (),
    utc_columns: Iterable[str] = (),
) -> pd.DataFrame:
    """Cria uma cópia da tabela com as datas no formato de exibição."""
    display = frame.copy()
    for column in monthly_columns:
        if column in display:
            display[column] = display[column].map(fmt_month_display)
    for column in daily_columns:
        if column in display:
            display[column] = display[column].map(fmt_date_display)
    for column in utc_columns:
        if column in display:
            display[column] = display[column].map(fmt_datetime_utc_display)
    return display
