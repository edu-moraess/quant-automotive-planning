from pathlib import Path

import pandas as pd

from energy_intelligence import load_energy_prices
from scenarios import apply_demand_scenarios, energy_price_sensitivity
from vehicle_intelligence import load_vehicle_data


def test_demand_scenarios_are_explicit_and_non_negative():
    forecast = pd.DataFrame({"data": pd.date_range("2026-01-01", periods=2, freq="MS"), "p50": [10.0, 11.0]})
    scenarios = apply_demand_scenarios(forecast, {"Downside": -0.1, "Base": 0.0, "Stress": 0.2})
    assert set(scenarios["cenario"]) == {"Downside", "Base", "Stress"}
    assert scenarios["demanda_saar_milhoes"].ge(0).all()
    assert scenarios.loc[scenarios["cenario"].eq("Stress"), "demanda_saar_milhoes"].iloc[0] == 12.0


def test_energy_price_sensitivity_uses_real_snapshot():
    root = Path(__file__).resolve().parents[1]
    vehicles = load_vehicle_data(root / "data" / "EPA_vehicles_snapshot.csv").query("year >= 2025")
    prices = load_energy_prices(root / "data" / "energy_price_snapshot.csv")
    sensitivity = energy_price_sensitivity(vehicles, prices, shocks=(-0.1, 0.0, 0.1))
    gasoline = sensitivity.loc[sensitivity["fonte_energia"].eq("Gasolina")].sort_values("choque_preco_pct")
    assert len(gasoline) == 3
    assert gasoline["custo_mediano_100mi_usd"].is_monotonic_increasing
