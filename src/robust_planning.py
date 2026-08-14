"""Integração entre caminhos Monte Carlo, risco e otimização PuLP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from config import PlanningAssumptions
from planning import solve_production_plan
from risk_engine import MonteCarloConfig, run_risk_engine


@dataclass(frozen=True)
class RobustPlanningConfig:
    """Parâmetros de amostragem e reprodutibilidade do planejamento robusto."""

    n_paths_to_optimize: int = 200
    seed: int = 42
    confidence_levels: tuple[float, ...] = (0.90, 0.95, 0.99)


def optimize_under_uncertainty(
    forecast_simulations: np.ndarray,
    assumptions: PlanningAssumptions,
    *,
    market_share: float | None = None,
    config: RobustPlanningConfig | None = None,
) -> dict[str, Any]:
    """Resolve o plano PuLP em caminhos Monte Carlo amostrados e agrega risco da política.

    Diferentemente do Risk Engine aproximado, esta função chama o solver de
    produção para cada caminho selecionado. O número de caminhos é limitado por
    configuração para manter a interface responsiva; portanto, o resultado é uma
    estimativa robusta amostrada, não uma solução estocástica ótima global.
    """
    settings = config or RobustPlanningConfig()
    simulations = _validate_simulations(forecast_simulations)
    if settings.n_paths_to_optimize < 1:
        raise ValueError("n_paths_to_optimize deve ser positivo.")
    share = float(market_share if market_share is not None else assumptions.participation)
    if not 0 < share <= 1:
        raise ValueError("market_share deve estar entre 0 e 1.")
    if any(not 0 < level < 1 for level in settings.confidence_levels):
        raise ValueError("confidence_levels deve conter níveis entre 0 e 1.")

    rng = np.random.default_rng(settings.seed)
    replace = simulations.shape[0] < settings.n_paths_to_optimize
    selected_indices = rng.choice(simulations.shape[0], size=settings.n_paths_to_optimize, replace=replace)
    rows: list[dict[str, float | int | str]] = []
    solutions: dict[int, dict[str, Any]] = {}
    for path_number, source_index in enumerate(selected_indices):
        demand = np.rint(np.maximum(simulations[source_index], 0.0) / 12.0 * 1_000_000.0 * share).astype(int)
        solution = solve_production_plan(demand, assumptions, f"MC_{path_number}")
        solutions[path_number] = solution
        capacity = max(assumptions.regular_capacity + assumptions.overtime_capacity, 1)
        rows.append(
            {
                "path": path_number,
                "source_simulation": int(source_index),
                "cost_total": float(solution["custo_total"]),
                "backlog_total": float(sum(solution["backlog"])),
                "backlog_final": float(solution["backlog"][-1]),
                "inventory_final": float(solution["estoque"][-1]),
                "production_total": float(sum(solution["producao"])),
                "utilization_max_pct": float(max(solution["producao"]) / capacity * 100),
                "status": solution["status"],
            }
        )
    summary = pd.DataFrame(rows)
    losses = summary["cost_total"].to_numpy(dtype=float)
    backlog = summary["backlog_final"].to_numpy(dtype=float)
    metrics: dict[str, float | int | str] = {
        "n_paths_optimized": int(len(summary)),
        "seed": int(settings.seed),
        "market_share": share,
        "optimization_status": "integrated_pulp_sampled_paths",
        "probability_backlog_final": float(np.mean(backlog > 0)),
        "expected_backlog_final": float(np.mean(backlog)),
        "expected_cost": float(np.mean(losses)),
        "capacity_at_risk_pct": float(np.quantile(summary["utilization_max_pct"], 0.95)),
    }
    for level in settings.confidence_levels:
        var = float(np.quantile(losses, level))
        tail = losses[losses >= var]
        metrics[f"VaR_{int(level * 100)}"] = var
        metrics[f"CVaR_{int(level * 100)}"] = float(np.mean(tail)) if len(tail) else var

    representative_solutions = {}
    for quantile, name in ((0.10, "P10"), (0.50, "P50"), (0.90, "P90")):
        saar = np.quantile(simulations, quantile, axis=0)
        demand = np.rint(np.maximum(saar, 0.0) / 12.0 * 1_000_000.0 * share).astype(int)
        representative_solutions[name] = solve_production_plan(demand, assumptions, f"Representative_{name}")

    return {
        "metrics": metrics,
        "summary": summary,
        "solutions": solutions,
        "representative_solutions": representative_solutions,
        "selected_indices": selected_indices.tolist(),
        "metadata": {
            "policy": "PuLP per sampled Monte Carlo path",
            "simulation_source": "forecast_simulations",
            "market_share_status": "assumed",
            "n_paths_available": int(simulations.shape[0]),
            "n_paths_optimized": int(len(summary)),
            "optimization_status": "integrated_pulp_sampled_paths",
        },
    }


def integrate_risk_and_optimization(
    forecast_simulations: np.ndarray,
    assumptions: PlanningAssumptions,
    *,
    market_share: float | None = None,
    risk_config: MonteCarloConfig | None = None,
    robust_config: RobustPlanningConfig | None = None,
) -> dict[str, Any]:
    """Executa risco aproximado e otimização PuLP amostrada sob o mesmo forecast."""
    risk = run_risk_engine(
        forecast_simulations,
        assumptions,
        market_share=market_share,
        config=risk_config,
    )
    robust = optimize_under_uncertainty(
        forecast_simulations,
        assumptions,
        market_share=market_share,
        config=robust_config,
    )
    return {
        "risk": risk,
        "robust_planning": robust,
        "integration_status": "risk_and_pulp_integrated",
        "comparison": {
            "risk_expected_backlog_units": risk.metrics["expected_backlog_units"],
            "pulp_expected_backlog_final": robust["metrics"]["expected_backlog_final"],
            "risk_optimization_status": robust["metadata"]["optimization_status"],
        },
    }


def _validate_simulations(simulations: np.ndarray) -> np.ndarray:
    values = np.asarray(simulations, dtype=float)
    if values.ndim != 2 or values.shape[0] < 1 or values.shape[1] < 1:
        raise ValueError("forecast_simulations deve ser uma matriz 2D não vazia.")
    if not np.isfinite(values).all():
        raise ValueError("forecast_simulations não pode conter NaN ou infinito.")
    return values
