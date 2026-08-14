"""Atualiza o snapshot de preços de energia com validação e proveniência."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import ENERGY_SNAPSHOT, SOURCES  # noqa: E402
from ingestion import fetch_monthly_fred_energy_series  # noqa: E402


def main() -> None:
    frames: list[pd.DataFrame] = []
    provenance: dict[str, object] = {"updated_at_utc": pd.Timestamp.utcnow().isoformat(), "series": {}}
    for series_id, output_name in SOURCES.fred_energy_series.items():
        result = fetch_monthly_fred_energy_series(series_id, output_name)
        frames.append(result.frame)
        provenance["series"][series_id] = {
            "output_column": output_name,
            "status": result.source_status,
            "source_url": result.source_url,
            "retrieved_at_utc": result.retrieved_at_utc,
            "rows": int(len(result.frame)),
            "start": result.frame["data"].min().strftime("%Y-%m-%d"),
            "end": result.frame["data"].max().strftime("%Y-%m-%d"),
        }
    monthly = frames[0]
    for frame in frames[1:]:
        monthly = monthly.merge(frame, on="data", how="outer", validate="one_to_one")
    monthly = monthly.sort_values("data").drop_duplicates("data").reset_index(drop=True)
    ENERGY_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(ENERGY_SNAPSHOT, index=False, date_format="%Y-%m-%d")
    provenance_path = ENERGY_SNAPSHOT.with_name("energy_price_provenance.json")
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Snapshot atualizado: {ENERGY_SNAPSHOT} | {len(monthly):,} meses | última data: {monthly['data'].max():%Y-%m-%d}"
    )


if __name__ == "__main__":
    main()
