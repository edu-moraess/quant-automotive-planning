import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import PlanningAssumptions  # noqa: E402
from risk_engine import MonteCarloConfig, run_risk_engine  # noqa: E402


def _assumptions() -> PlanningAssumptions:
    return PlanningAssumptions(
        participation=0.08,
        regular_capacity=110_000,
        overtime_capacity=0,
        initial_inventory=15_000,
        backlog_cost=45_000,
    )


def test_risk_engine_is_reproducible_and_reports_tail_metrics():
    simulations = np.array(
        [
            [12.0, 12.0, 12.0],
            [12.5, 12.5, 12.5],
            [13.0, 13.0, 13.0],
            [14.0, 14.0, 14.0],
        ]
    )
    config = MonteCarloConfig(n_simulations=500, seed=19, confidence_levels=(0.90, 0.95))
    first = run_risk_engine(simulations, _assumptions(), config=config)
    second = run_risk_engine(simulations, _assumptions(), config=config)
    assert np.array_equal(first.backlog_paths, second.backlog_paths)
    assert first.metrics["VaR_95"] <= first.metrics["CVaR_95"]
    assert first.metrics["n_simulations"] == 500
    assert first.metadata["optimization_status"] == "not_integrated"


def test_risk_engine_rejects_invalid_simulations():
    with pytest.raises(ValueError, match="matriz 2D"):
        run_risk_engine(np.array([1.0, 2.0]), _assumptions())


def test_risk_engine_exposes_backlog_probability_and_capacity_risk():
    simulations = np.full((200, 2), 20.0)
    result = run_risk_engine(simulations, _assumptions(), config=MonteCarloConfig(n_simulations=200, seed=7))
    assert 0 <= result.metrics["stockout_probability"] <= 1
    assert result.metrics["capacity_at_risk_units"] > 0
    assert {"metric", "value", "status", "source"}.issubset(result.risk_table.columns)
