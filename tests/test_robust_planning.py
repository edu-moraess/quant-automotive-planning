import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import PlanningAssumptions  # noqa: E402
from risk_engine import MonteCarloConfig  # noqa: E402
from robust_planning import (  # noqa: E402
    RobustPlanningConfig,
    integrate_risk_and_optimization,
    optimize_under_uncertainty,
)


def _assumptions() -> PlanningAssumptions:
    return PlanningAssumptions(
        participation=0.08,
        regular_capacity=110_000,
        overtime_capacity=10_000,
        initial_inventory=15_000,
        backlog_cost=45_000,
    )


def test_robust_planning_calls_pulp_on_sampled_paths():
    simulations = np.array(
        [
            [12.0, 12.0, 12.0],
            [12.5, 12.5, 12.5],
            [13.0, 13.0, 13.0],
            [14.0, 14.0, 14.0],
        ]
    )
    result = optimize_under_uncertainty(
        simulations,
        _assumptions(),
        config=RobustPlanningConfig(n_paths_to_optimize=20, seed=11),
    )
    assert result["metadata"]["optimization_status"] == "integrated_pulp_sampled_paths"
    assert len(result["summary"]) == 20
    assert set(result["summary"]["status"]) == {"Optimal"}
    assert set(result["representative_solutions"]) == {"P10", "P50", "P90"}
    assert result["metrics"]["VaR_95"] <= result["metrics"]["CVaR_95"]


def test_robust_planning_rejects_non_finite_paths():
    with pytest.raises(ValueError, match="NaN"):
        optimize_under_uncertainty(np.array([[1.0, np.nan]]), _assumptions())


def test_integrated_risk_and_optimization_exposes_both_layers():
    simulations = np.full((20, 2), 12.0)
    result = integrate_risk_and_optimization(
        simulations,
        _assumptions(),
        risk_config=MonteCarloConfig(n_simulations=100, seed=5),
        robust_config=RobustPlanningConfig(n_paths_to_optimize=5, seed=5),
    )
    assert result["integration_status"] == "risk_and_pulp_integrated"
    assert result["risk"].metadata["optimization_status"] == "not_integrated"
    assert result["robust_planning"]["metadata"]["optimization_status"] == "integrated_pulp_sampled_paths"
