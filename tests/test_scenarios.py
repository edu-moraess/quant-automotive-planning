import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import PlanningAssumptions  # noqa: E402
from energy_intelligence import load_energy_prices  # noqa: E402
from scenario_engine import MarketShareSpec, ScenarioSpec, run_scenario_engine, run_sensitivity_engine  # noqa: E402
from scenarios import apply_demand_scenarios, energy_price_sensitivity  # noqa: E402
from vehicle_intelligence import load_vehicle_data  # noqa: E402


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


def _scenario_forecast() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "data": pd.date_range("2025-01-01", periods=6, freq="MS"),
            "p50": [12.0, 12.1, 12.2, 12.3, 12.4, 12.5],
        }
    )


def test_market_share_requires_explicit_status_and_ordered_quantiles():
    spec = MarketShareSpec(p10=0.06, p50=0.08, p90=0.10)
    assert spec.status == "assumed"
    assert spec.shifted(0.01).p50 == pytest.approx(0.09)
    with pytest.raises(ValueError, match="Quantis"):
        MarketShareSpec(p10=0.10, p50=0.08, p90=0.12)


def test_scenario_engine_keeps_deterministic_output_separate_from_simulation():
    assumptions = PlanningAssumptions(participation=0.08, regular_capacity=110_000, initial_inventory=15_000)
    scenarios = (
        ScenarioSpec("base", "Base", "central", shock={"demand_pct": 0.0}, probability=0.7),
        ScenarioSpec("stress", "Stress", "high", shock={"demand_pct": 0.2}, probability=0.3),
    )
    result = run_scenario_engine(_scenario_forecast(), assumptions, scenarios=scenarios)
    assert result["output_type"] == "deterministic_scenario"
    assert set(result["scenarios"]["scenario_id"]) == {"base", "stress"}
    assert result["market_share"]["status"] == "assumed"


def test_sensitivity_marks_unconnected_energy_and_interest_transmission():
    assumptions = PlanningAssumptions(participation=0.08, regular_capacity=110_000, initial_inventory=15_000)
    result = run_sensitivity_engine(_scenario_forecast(), assumptions)
    assert {"connected", "not_connected"}.issubset(set(result["transmission_status"]))
    assert (result.loc[result["transmission_status"] == "not_connected", "cost_total_delta"].abs() == 0).all()
