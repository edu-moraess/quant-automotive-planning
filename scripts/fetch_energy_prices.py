"""Atualiza o snapshot de preços de energia a partir de séries públicas do FRED."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SERIES = {
    "GASREGW": "gasolina_usd_gal",
    "GASDESW": "diesel_usd_gal",
    "APU000072610": "eletricidade_usd_kwh",
}


def load_series(series_id: str, output_name: str) -> pd.DataFrame:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    data = pd.read_csv(url, parse_dates=["observation_date"])
    data = data.rename(columns={"observation_date": "data", series_id: output_name})
    data[output_name] = pd.to_numeric(data[output_name], errors="coerce")
    return data.set_index("data").resample("MS").mean().reset_index()


def main() -> None:
    series_frames = [load_series(series_id, output_name) for series_id, output_name in SERIES.items()]
    monthly = series_frames[0]
    for frame in series_frames[1:]:
        monthly = monthly.merge(frame, on="data", how="outer")
    monthly = monthly.sort_values("data").reset_index(drop=True)
    output = ROOT / "data" / "energy_price_snapshot.csv"
    monthly.to_csv(output, index=False, date_format="%Y-%m-%d")
    print(f"Snapshot atualizado: {output} | {len(monthly):,} meses | última data: {monthly['data'].max():%Y-%m-%d}")


if __name__ == "__main__":
    main()
