"""Atualiza o snapshot de preços de energia com validação e proveniência."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import ENERGY_REFRESH_SOURCES, ENERGY_SNAPSHOT, SOURCES  # noqa: E402
from ingestion import fetch_monthly_fred_energy_series  # noqa: E402


def _fetch_energy_series(item: tuple[str, str]):
    series_id, output_name = item
    result = fetch_monthly_fred_energy_series(series_id, output_name, settings=ENERGY_REFRESH_SOURCES)
    return series_id, output_name, result


def main() -> None:
    started = perf_counter()
    series_items = list(SOURCES.fred_energy_series.items())
    with ThreadPoolExecutor(max_workers=len(series_items)) as executor:
        fetched = list(executor.map(_fetch_energy_series, series_items))

    frames: list[pd.DataFrame] = []
    provenance: dict[str, object] = {
        "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "refresh_policy": {
            "parallel_workers": len(series_items),
            "timeout_seconds": ENERGY_REFRESH_SOURCES.request_timeout_seconds,
            "max_attempts": ENERGY_REFRESH_SOURCES.max_attempts,
        },
        "series": {},
    }
    for series_id, output_name, result in fetched:
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
    provenance["duration_seconds"] = round(perf_counter() - started, 3)
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Snapshot atualizado: {ENERGY_SNAPSHOT} | {len(monthly):,} meses | última data: {monthly['data'].max():%Y-%m-%d} | "
        f"duração: {provenance['duration_seconds']:.3f}s"
    )


if __name__ == "__main__":
    main()
