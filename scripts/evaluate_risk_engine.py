"""Avalia o Risk Engine usando o snapshot FRED versionado do projeto."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analysis import run_full_analysis  # noqa: E402
from config import PlanningAssumptions  # noqa: E402
from risk_engine import MonteCarloConfig, run_risk_engine  # noqa: E402


def main() -> None:
    result = run_full_analysis(
        fallback_path=ROOT / "data" / "TOTALSA_snapshot.csv",
        n_folds=4,
        test_size=6,
        horizon=6,
        bootstrap_replicas=500,
        seed=42,
        allow_online=False,
    )
    assumptions = PlanningAssumptions(
        participation=result["parameters"]["participation"],
        regular_capacity=result["parameters"]["capacity"],
        overtime_capacity=result["parameters"]["overtime_capacity"],
        initial_inventory=result["parameters"]["initial_inventory"],
        backlog_cost=result["parameters"]["backlog_cost"],
    )
    risk = run_risk_engine(
        result["simulations"],
        assumptions,
        config=MonteCarloConfig(n_simulations=5_000, seed=42),
    )
    print(
        json.dumps(
            {
                "source_label": result["source_label"],
                "data_end": result["market_refresh"]["data_end"],
                "model": result["backtest"]["winner"],
                "risk_metrics": risk.metrics,
                "metadata": risk.metadata,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
