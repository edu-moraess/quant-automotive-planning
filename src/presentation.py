"""Funções de apresentação para datas e timestamps da interface.

A camada de modelagem conserva timestamps nativos. Estas funções são usadas somente
em cópias destinadas a tabelas, downloads e textos de interface.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

MISSING_DISPLAY = "—"


def _as_timestamp(value: object) -> pd.Timestamp | None:
    """Converte valores temporais para ``Timestamp`` sem elevar valores ausentes."""
    if value is None or pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    return None if pd.isna(timestamp) else timestamp


def fmt_month_display(value: object) -> str:
    """Formata uma competência mensal como ``MM/AAAA`` para a camada visual."""
    timestamp = _as_timestamp(value)
    return MISSING_DISPLAY if timestamp is None else timestamp.strftime("%m/%Y")


def fmt_date_display(value: object) -> str:
    """Formata uma data diária sem significado de horário como ``DD/MM/AAAA``."""
    timestamp = _as_timestamp(value)
    return MISSING_DISPLAY if timestamp is None else timestamp.strftime("%d/%m/%Y")


def fmt_datetime_utc_display(value: object) -> str:
    """Formata timestamp real em UTC como ``DD/MM/AAAA HH:MM UTC``."""
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
    """Retorna cópia visual de ``frame`` com as colunas temporais solicitadas em texto.

    A função não modifica o DataFrame recebido. Dessa forma, joins, resampling,
    forecast e gráficos continuam operando sobre os tipos temporais originais.
    """
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
