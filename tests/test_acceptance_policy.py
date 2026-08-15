from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from acceptance_policy import ACCEPTANCE_POLICY


def test_acceptance_policy_separates_floor_from_nominal_targets():
    assert ACCEPTANCE_POLICY.grouped_ljung_box_lag == 3
    assert ACCEPTANCE_POLICY.alpha == 0.05
    assert ACCEPTANCE_POLICY.mape_acceptance_max_pct == 4.00
    assert ACCEPTANCE_POLICY.mape_nominal_target_max_pct == 2.87
    assert ACCEPTANCE_POLICY.coverage_acceptance_min == 0.75
    assert ACCEPTANCE_POLICY.coverage_nominal_target == 0.80
    assert ACCEPTANCE_POLICY.diagnostic_tests_required == ("ARCH", "CUSUM")
    assert ACCEPTANCE_POLICY.tail_metrics_required == (
        "VaR_95",
        "CVaR_95",
        "stockout_probability",
        "expected_backlog_units",
    )
    assert ACCEPTANCE_POLICY.tail_preservation_direction == "not_below_baseline"


def test_acceptance_policy_serializes_without_tuple_specifics():
    payload = ACCEPTANCE_POLICY.as_dict()
    assert payload["version"] == "2026.08"
    assert payload["diagnostic_tests_required"] == ["ARCH", "CUSUM"]
    assert payload["tail_metrics_required"] == [
        "VaR_95",
        "CVaR_95",
        "stockout_probability",
        "expected_backlog_units",
    ]
    assert payload["tail_preservation_direction"] == "not_below_baseline"
