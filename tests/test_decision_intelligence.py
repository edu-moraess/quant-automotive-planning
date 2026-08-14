import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from decision_intelligence import DecisionThresholds, build_decision_intelligence  # noqa: E402


def test_decision_intelligence_returns_green_only_from_quantitative_evidence():
    result = build_decision_intelligence(
        forecast_metrics={"mape_pct": 3.0, "coverage_p10_p90": 0.85},
        risk_metrics={"stockout_probability": 0.10, "simulation_source": "forecast_simulations"},
        robust_metrics={"probability_backlog_final": 0.08, "capacity_at_risk_pct": 85.0},
        scenario_table=pd.DataFrame({"scenario_id": ["base"]}),
        assumptions={"market_share_status": "assumed"},
    )
    assert result["decision_status"] == "green"
    assert result["confidence"]["level"] == "high"
    assert any(action["priority"] == "disclosure" for action in result["actions"])
    assert set(result["signals"]["status"]) == {"green"}


def test_decision_intelligence_red_signal_creates_conditional_review_action():
    result = build_decision_intelligence(
        forecast_metrics={"mape_pct": 8.0, "coverage_p10_p90": 0.80},
        risk_metrics={"stockout_probability": 0.65},
        robust_metrics={"probability_backlog_final": 0.60, "capacity_at_risk_pct": 110.0},
        thresholds=DecisionThresholds(max_mape_pct=5.0),
    )
    assert result["decision_status"] == "red"
    assert result["confidence"]["level"] == "low"
    assert any(action["priority"] == "high" for action in result["actions"])
    assert any("capacidade" in action["action"] for action in result["actions"])


def test_decision_intelligence_abstains_without_metrics():
    result = build_decision_intelligence()
    assert result["decision_status"] == "unavailable"
    assert result["confidence"]["level"] == "unavailable"
    assert any("Não foi fornecida" in limitation for limitation in result["limitations"])
