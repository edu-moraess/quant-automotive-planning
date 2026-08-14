import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presentation import (
    fmt_date_display,
    fmt_datetime_utc_display,
    fmt_month_display,
    format_temporal_display,
)


def test_monthly_date_display_has_no_midnight_component():
    assert fmt_month_display(pd.Timestamp("2026-01-01 00:00:00")) == "01/2026"


def test_daily_date_display_has_no_midnight_component():
    assert fmt_date_display(pd.Timestamp("2026-08-14 00:00:00")) == "14/08/2026"


def test_utc_timestamp_preserves_meaningful_time():
    assert fmt_datetime_utc_display(pd.Timestamp("2026-08-14 09:30:00")) == "14/08/2026 09:30 UTC"


def test_temporal_display_copy_keeps_source_timestamp_dtype_for_calculations():
    source = pd.DataFrame(
        {
            "competencia": [pd.Timestamp("2026-01-01")],
            "inicio": [pd.Timestamp("2026-08-14")],
            "atualizado_em": [pd.Timestamp("2026-08-14T09:30:00+00:00")],
        }
    )

    display = format_temporal_display(
        source,
        monthly_columns=["competencia"],
        daily_columns=["inicio"],
        utc_columns=["atualizado_em"],
    )

    assert pd.api.types.is_datetime64_any_dtype(source["competencia"])
    assert pd.api.types.is_datetime64_any_dtype(source["inicio"])
    assert pd.api.types.is_datetime64_any_dtype(source["atualizado_em"])
    assert display.loc[0, "competencia"] == "01/2026"
    assert display.loc[0, "inicio"] == "14/08/2026"
    assert display.loc[0, "atualizado_em"] == "14/08/2026 09:30 UTC"


def test_missing_temporal_values_use_placeholder():
    assert fmt_month_display(pd.NaT) == "—"
    assert fmt_date_display(None) == "—"
    assert fmt_datetime_utc_display(pd.NaT) == "—"
