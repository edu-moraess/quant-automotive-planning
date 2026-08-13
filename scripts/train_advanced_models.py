"""Treina e exporta os modelos avançados da plataforma a partir de dados versionados."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advanced_models import fit_econometric_energy_model, fit_efficiency_neural_model, save_advanced_results  # noqa: E402
from analysis import prepare_data  # noqa: E402
from energy_intelligence import load_energy_prices  # noqa: E402
from vehicle_intelligence import load_vehicle_data  # noqa: E402


def main() -> None:
    raw_market = pd.read_csv(ROOT / "data" / "TOTALSA_snapshot.csv")
    market, _ = prepare_data(raw_market)
    prices = load_energy_prices(ROOT / "data" / "energy_price_snapshot.csv")
    vehicles = load_vehicle_data(ROOT / "data" / "EPA_vehicles_snapshot.csv")
    econometric = fit_econometric_energy_model(market, prices, holdout_months=24)
    neural = fit_efficiency_neural_model(vehicles, cutoff_year=2024)
    save_advanced_results(ROOT / "data" / "advanced_models", econometric, neural)
    print("Modelos avançados treinados")
    print("Econometria:", econometric["metrics"])
    print("Rede neural:", neural["metrics"])


if __name__ == "__main__":
    main()
