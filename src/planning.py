"""Otimização operacional e inteligência de decisão com hipóteses explícitas."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from config import PlanningAssumptions

try:
    import pulp
except ImportError:  # pragma: no cover
    pulp = None


def validate_assumptions(assumptions: PlanningAssumptions) -> None:
    numeric = asdict(assumptions)
    if assumptions.participation < 0 or assumptions.participation > 1:
        raise ValueError("Participação deve estar entre 0 e 1.")
    if any(value < 0 for value in numeric.values()):
        raise ValueError("Todas as hipóteses de planejamento devem ser não negativas.")


def demand_from_saar(saar_millions: pd.Series, participation: float) -> pd.Series:
    if not 0 <= participation <= 1:
        raise ValueError("Participação deve estar entre 0 e 1.")
    return (pd.to_numeric(saar_millions, errors="coerce") / 12 * 1_000_000 * participation).round().astype(int)


def solve_production_plan(
    demand: np.ndarray, assumptions: PlanningAssumptions, scenario_name: str = "Base"
) -> dict[str, Any]:
    """Minimiza custo operacional sob capacidade, estoque, backlog e segurança explicitados."""
    if pulp is None:
        raise RuntimeError("A dependência PuLP não está instalada.")
    validate_assumptions(assumptions)
    values = np.asarray(demand, dtype=float)
    if values.ndim != 1 or len(values) == 0 or np.any(values < 0) or not np.isfinite(values).all():
        raise ValueError("Demanda deve ser um vetor finito, não negativo e não vazio.")
    periods = list(range(len(values)))
    problem = pulp.LpProblem(f"Planejamento_{scenario_name}", pulp.LpMinimize)
    regular = pulp.LpVariable.dicts("producao_regular", periods, lowBound=0, upBound=assumptions.regular_capacity)
    overtime = pulp.LpVariable.dicts("producao_extra", periods, lowBound=0, upBound=assumptions.overtime_capacity)
    inventory = pulp.LpVariable.dicts("estoque", periods, lowBound=0)
    backlog = pulp.LpVariable.dicts("backlog", periods, lowBound=0)
    safety_shortfall = pulp.LpVariable.dicts("desvio_seguranca", periods, lowBound=0)
    active = (
        pulp.LpVariable.dicts("setup_ativo", periods, lowBound=0, upBound=1, cat="Binary")
        if assumptions.setup_cost > 0
        else None
    )
    objective = pulp.lpSum(
        assumptions.production_cost * regular[t]
        + assumptions.overtime_cost * overtime[t]
        + assumptions.inventory_cost * inventory[t]
        + assumptions.backlog_cost * backlog[t]
        + assumptions.safety_stock_penalty * safety_shortfall[t]
        + (assumptions.setup_cost * active[t] if active is not None else 0)
        for t in periods
    )
    problem += objective
    for period in periods:
        prior_inventory = assumptions.initial_inventory if period == 0 else inventory[period - 1]
        prior_backlog = 0 if period == 0 else backlog[period - 1]
        problem += (
            inventory[period] - backlog[period]
            == prior_inventory - prior_backlog + regular[period] + overtime[period] - float(values[period]),
            f"balanco_{period}",
        )
        problem += safety_shortfall[period] >= assumptions.safety_stock - inventory[period], f"seguranca_{period}"
        if active is not None:
            problem += (
                regular[period] + overtime[period]
                <= (assumptions.regular_capacity + assumptions.overtime_capacity) * active[period],
                f"setup_{period}",
            )
    status = problem.solve(pulp.PULP_CBC_CMD(msg=False))
    status_name = pulp.LpStatus[status]
    if status_name != "Optimal":
        raise RuntimeError(f"Otimização não encontrou solução ótima: {status_name}")
    regular_values = np.array([round(pulp.value(regular[t])) for t in periods], dtype=int)
    overtime_values = np.array([round(pulp.value(overtime[t])) for t in periods], dtype=int)
    inventory_values = np.array([round(pulp.value(inventory[t])) for t in periods], dtype=int)
    backlog_values = np.array([round(pulp.value(backlog[t])) for t in periods], dtype=int)
    safety_values = np.array([round(pulp.value(safety_shortfall[t])) for t in periods], dtype=int)
    return {
        "status": status_name,
        "producao_regular": regular_values.tolist(),
        "producao_extra": overtime_values.tolist(),
        "producao": (regular_values + overtime_values).tolist(),
        "estoque": inventory_values.tolist(),
        "backlog": backlog_values.tolist(),
        "desvio_seguranca": safety_values.tolist(),
        "custo_total": float(pulp.value(problem.objective)),
        "assumptions": asdict(assumptions),
    }


def build_scenario_table(
    forecast: pd.DataFrame,
    assumptions: PlanningAssumptions,
    demand_shocks: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Transforma quantis e choques declarados em soluções comparáveis de planejamento."""
    if "p50" not in forecast.columns:
        raise ValueError("Forecast deve conter p50.")
    shocks = demand_shocks or {"Downside": -0.10, "Base": 0.0, "Upside": 0.10, "Stress": 0.20}
    plan = forecast[["data", "p10", "p25", "p50", "p75", "p90"]].copy()
    base_demand = demand_from_saar(plan["p50"], assumptions.participation)
    base_solution = solve_production_plan(base_demand.to_numpy(), assumptions, "Base")
    plan["demanda_planejada_veiculos"] = base_demand
    plan["producao_regular"] = base_solution["producao_regular"]
    plan["producao_extra"] = base_solution["producao_extra"]
    plan["producao_recomendada"] = base_solution["producao"]
    plan["estoque_final"] = base_solution["estoque"]
    plan["demanda_pendente"] = base_solution["backlog"]
    plan["desvio_seguranca"] = base_solution["desvio_seguranca"]
    plan["utilizacao_regular_pct"] = plan["producao_regular"] / max(assumptions.regular_capacity, 1) * 100
    rows: list[dict[str, Any]] = []
    solutions: dict[str, dict[str, Any]] = {}
    for scenario, shock in shocks.items():
        if shock <= -1:
            raise ValueError("Choque de demanda deve ser maior que -100%.")
        demand = demand_from_saar(plan["p50"] * (1 + shock), assumptions.participation)
        solution = solve_production_plan(demand.to_numpy(), assumptions, scenario)
        solutions[scenario] = solution
        capacity_total = assumptions.regular_capacity + assumptions.overtime_capacity
        rows.append(
            {
                "Cenário": scenario,
                "Choque de demanda (%)": float(shock * 100),
                "Demanda total (veículos)": int(demand.sum()),
                "Produção regular (veículos)": int(sum(solution["producao_regular"])),
                "Produção extra (veículos)": int(sum(solution["producao_extra"])),
                "Produção total (veículos)": int(sum(solution["producao"])),
                "Utilização média (%)": float(np.mean(solution["producao"]) / max(capacity_total, 1) * 100),
                "Demanda pendente final": int(solution["backlog"][-1]),
                "Desvio acumulado de segurança": int(sum(solution["desvio_seguranca"])),
                "Custo total (US$)": float(solution["custo_total"]),
            }
        )
    return {
        "plan": plan,
        "base_solution": base_solution,
        "scenarios": pd.DataFrame(rows),
        "scenario_solutions": solutions,
    }


def build_sensitivity(
    forecast: pd.DataFrame,
    assumptions: PlanningAssumptions,
    capacity_factors: tuple[float, ...] = (0.8, 0.9, 1.0, 1.1, 1.2),
    participation_offsets: tuple[float, ...] = (-0.02, 0.0, 0.02),
) -> pd.DataFrame:
    """Mede backlog acumulado em grade de capacidade regular e participação assumida."""
    rows: list[dict[str, float]] = []
    for capacity_factor in capacity_factors:
        for offset in participation_offsets:
            scenario = PlanningAssumptions(
                participation=float(np.clip(assumptions.participation + offset, 0.01, 1.0)),
                regular_capacity=int(round(assumptions.regular_capacity * capacity_factor)),
                overtime_capacity=assumptions.overtime_capacity,
                initial_inventory=assumptions.initial_inventory,
                safety_stock=assumptions.safety_stock,
                production_cost=assumptions.production_cost,
                overtime_cost=assumptions.overtime_cost,
                inventory_cost=assumptions.inventory_cost,
                backlog_cost=assumptions.backlog_cost,
                safety_stock_penalty=assumptions.safety_stock_penalty,
                setup_cost=assumptions.setup_cost,
            )
            demand = demand_from_saar(forecast["p50"], scenario.participation)
            solution = solve_production_plan(demand.to_numpy(), scenario, f"sens_{capacity_factor}_{offset}")
            rows.append(
                {
                    "Capacidade mensal": scenario.regular_capacity,
                    "Participação de mercado": scenario.participation,
                    "Backlog acumulado": float(sum(solution["backlog"])),
                }
            )
    return pd.DataFrame(rows).pivot(
        index="Capacidade mensal", columns="Participação de mercado", values="Backlog acumulado"
    )


def decision_brief(scenarios: pd.DataFrame, assumptions: PlanningAssumptions) -> dict[str, str | float]:
    """Converte cenários em uma leitura operacional sem ocultar hipóteses."""
    base = scenarios.loc[scenarios["Cenário"].eq("Base")].iloc[0]
    stress = scenarios.loc[scenarios["Cenário"].eq("Stress")].iloc[0]
    if stress["Demanda pendente final"] > 0:
        risk = "O cenário Stress gera backlog; capacidade adicional, redução de participação assumida ou estoque inicial maior devem ser avaliados."
    else:
        risk = "Mesmo o cenário Stress é atendido com as hipóteses atuais de capacidade e custo."
    action = (
        "Preservar plano Base"
        if base["Demanda pendente final"] == 0
        else "Revisar capacidade e estoque de segurança antes de executar o plano Base"
    )
    return {
        "acao_recomendada": action,
        "risco_principal": risk,
        "capacidade_regular_assumida": assumptions.regular_capacity,
        "capacidade_extra_assumida": assumptions.overtime_capacity,
        "participacao_assumida_pct": assumptions.participation * 100,
    }
