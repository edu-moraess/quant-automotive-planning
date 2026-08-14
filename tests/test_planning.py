import numpy as np
import pandas as pd

from config import PlanningAssumptions
from planning import build_scenario_table, decision_brief, solve_production_plan


def test_overtime_is_used_before_backlog_when_economically_preferable():
    assumptions = PlanningAssumptions(
        participation=0.08,
        regular_capacity=100,
        overtime_capacity=50,
        initial_inventory=0,
        production_cost=10,
        overtime_cost=20,
        inventory_cost=1,
        backlog_cost=1_000,
    )
    result = solve_production_plan(np.array([130]), assumptions)
    assert result["producao_regular"][0] == 100
    assert result["producao_extra"][0] == 30
    assert result["backlog"][0] == 0


def test_scenario_table_exposes_hypotheses_and_decision_brief():
    forecast = pd.DataFrame(
        {
            "data": pd.date_range("2026-01-01", periods=2, freq="MS"),
            "p10": [10.0, 10.0],
            "p25": [10.2, 10.2],
            "p50": [10.5, 10.5],
            "p75": [10.8, 10.8],
            "p90": [11.0, 11.0],
        }
    )
    assumptions = PlanningAssumptions(participation=0.001, regular_capacity=1_000, initial_inventory=0)
    result = build_scenario_table(forecast, assumptions)
    brief = decision_brief(result["scenarios"], assumptions)
    assert set(result["scenarios"]["Cenário"]) == {"Downside", "Base", "Upside", "Stress"}
    assert {"acao_recomendada", "risco_principal", "participacao_assumida_pct"}.issubset(brief)
