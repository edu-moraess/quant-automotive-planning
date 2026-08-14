"""Gera artefato versionável de saúde e proveniência dos datasets locais."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import ENERGY_SNAPSHOT, EPA_SNAPSHOT, MARKET_SNAPSHOT  # noqa: E402
from data_quality import health_table, profile_time_series, profile_vehicle_catalog  # noqa: E402


def main() -> None:
    market = pd.read_csv(MARKET_SNAPSHOT)
    vehicles = pd.read_csv(EPA_SNAPSHOT, low_memory=False)
    energy = pd.read_csv(ENERGY_SNAPSHOT)
    health_items = [
        profile_time_series(
            market,
            dataset="FRED TOTALSA",
            date_column="observation_date",
            value_columns=["TOTALSA"],
            source_status="SNAPSHOT",
            snapshot_path=MARKET_SNAPSHOT,
            notes="Mercado agregado de veículos leves; snapshot local usado como fallback reprodutível.",
        ),
        profile_vehicle_catalog(vehicles, source_status="SNAPSHOT", snapshot_path=EPA_SNAPSHOT),
        profile_time_series(
            energy,
            dataset="Energia FRED/EIA/BLS",
            date_column="data",
            value_columns=["gasolina_usd_gal", "diesel_usd_gal", "eletricidade_usd_kwh"],
            source_status="SNAPSHOT",
            snapshot_path=ENERGY_SNAPSHOT,
            notes="Cobertura histórica varia por série; ausências são preservadas e não imputadas.",
        ),
    ]
    table = health_table(health_items)
    output_json = ROOT / "data" / "data_health.json"
    output_csv = ROOT / "data" / "data_health.csv"
    json_table = table.astype(object).where(pd.notna(table), None)
    output_json.write_text(
        json.dumps(json_table.to_dict(orient="records"), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    table.to_csv(output_csv, index=False)
    print(f"Data health atualizado: {output_json}")


if __name__ == "__main__":
    main()
