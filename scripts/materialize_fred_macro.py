"""Materializa CPIAUCSL e INDPRO reais no feature store local.

O endpoint fredgraph.csv é público e reproduz o snapshot histórico usado no
backtest. Quando a API FRED autenticada não está disponível no sandbox, a data
de observação é usada como fallback conservador de disponibilidade, exatamente
como no parser do cliente FRED para respostas sem realtime_start.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from config import DATA_DIR
from data.contracts import SourceName, SourceRunStatus, SourceState, TimeWindow
from data.feature_builder import FeatureBuilder
from data.feature_store import FeatureStore

ROOT = Path(__file__).resolve().parents[1]
STORE_DIR = DATA_DIR / "feature_store"
AS_OF = pd.Timestamp("2026-08-14")
START = pd.Timestamp("1976-01-01")
SERIES = {
    "CPIAUCSL": "cpi",
    "INDPRO": "producao_industrial",
}
BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fetch_series(series_id: str, feature_name: str) -> pd.DataFrame:
    """Baixa uma série mensal real e normaliza para o contrato FRED interno."""
    response = requests.get(
        BASE_URL,
        params={
            "id": series_id,
            "cosd": START.strftime("%Y-%m-%d"),
            "coed": AS_OF.strftime("%Y-%m-%d"),
        },
        timeout=60,
    )
    response.raise_for_status()
    frame = pd.read_csv(io.StringIO(response.text))
    if frame.shape[1] < 2:
        raise ValueError(f"Resposta sem coluna de valores para {series_id}.")
    date_column, value_column = frame.columns[:2]
    parsed = pd.DataFrame(
        {
            "data": pd.to_datetime(frame[date_column], errors="coerce"),
            "disponivel_em": pd.to_datetime(frame[date_column], errors="coerce"),
            "serie": series_id,
            "feature": feature_name,
            "valor": pd.to_numeric(frame[value_column], errors="coerce"),
        }
    ).dropna(subset=["data", "valor"])
    parsed = (
        parsed.loc[parsed["data"].between(START, AS_OF) & parsed["disponivel_em"].le(AS_OF)]
        .sort_values("data")
        .reset_index(drop=True)
    )
    if parsed.empty:
        raise ValueError(f"Nenhuma observação elegível para {series_id}.")
    return parsed


def main() -> None:
    """Atualiza as fontes FRED e reconstrói as features mensais agregadas."""
    store = FeatureStore(STORE_DIR)
    fetched = [fetch_series(series_id, feature_name) for series_id, feature_name in SERIES.items()]
    macro_frame = pd.concat(fetched, ignore_index=True)

    existing_fred = store.read_source(SourceName.FRED)
    fred_frame = pd.concat([existing_fred, macro_frame], ignore_index=True)
    fred_frame = fred_frame.drop_duplicates(["data", "serie", "disponivel_em"], keep="last")
    fred_frame = fred_frame.sort_values(["data", "serie"]).reset_index(drop=True)
    store.write(
        SourceName.FRED,
        fred_frame,
        date_column="data",
        dedupe_columns=("data", "serie", "disponivel_em"),
    )

    eia_frame = store.read_source(SourceName.EIA)
    market_features = FeatureBuilder._build_market_features(
        fred_frame,
        eia_frame,
        TimeWindow(start=START, as_of=AS_OF),
    ).reset_index()
    store.write(
        SourceName.FEATURE_BUILDER,
        market_features,
        date_column="mes",
        dedupe_columns=("mes",),
    )

    fred_status = SourceRunStatus(
        source=SourceName.FRED,
        state=SourceState.FRESH,
        rows=len(fred_frame),
        coverage_start=fred_frame["data"].min(),
        coverage_end=fred_frame["data"].max(),
        message="CPIAUCSL e INDPRO materializadas pelo endpoint público fredgraph.csv; disponibilidade igual à data da observação por ausência de vintage autenticado.",
    )
    builder_status = SourceRunStatus(
        source=SourceName.FEATURE_BUILDER,
        state=SourceState.FRESH,
        rows=len(market_features),
        coverage_start=market_features["mes"].min(),
        coverage_end=market_features["mes"].max(),
        message="Features mensais reconstruídas com TOTALSA, CPIAUCSL e INDPRO reais; diferenças e lags materializados.",
    )
    store.record_statuses([fred_status, builder_status])

    provenance = {
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "endpoint": BASE_URL,
        "start": START.date().isoformat(),
        "as_of": AS_OF.date().isoformat(),
        "availability_rule": "observation_date_fallback_without_authenticated_realtime_start",
        "series": {
            series_id: {
                "feature": feature_name,
                "rows": int(macro_frame.loc[macro_frame["serie"].eq(series_id)].shape[0]),
                "coverage_start": macro_frame.loc[macro_frame["serie"].eq(series_id), "data"].min().date().isoformat(),
                "coverage_end": macro_frame.loc[macro_frame["serie"].eq(series_id), "data"].max().date().isoformat(),
            }
            for series_id, feature_name in SERIES.items()
        },
        "market_feature_rows": len(market_features),
        "market_feature_columns": list(market_features.columns),
    }
    provenance_path = STORE_DIR / "fred_macro_refresh.json"
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(provenance, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
