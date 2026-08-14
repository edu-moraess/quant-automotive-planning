"""Monte Carlo operacional e métricas de risco para decisões de capacidade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from config import PlanningAssumptions


@dataclass(frozen=True)
class MonteCarloConfig:
    """Parâmetros reprodutíveis da simulação de risco."""

    n_simulations: int = 5_000
    seed: int = 42
    confidence_levels: tuple[float, ...] = (0.90, 0.95, 0.99)
    backlog_threshold_units: int = 0


@dataclass(frozen=True)
class RiskResult:
    """Saída do Risk Engine com caminhos operacionais e métricas agregadas."""

    metrics: dict[str, float | int | str]
    risk_table: pd.DataFrame
    backlog_paths: np.ndarray
    inventory_paths: np.ndarray
    loss_distribution: np.ndarray
    metadata: dict[str, Any]


def run_risk_engine(
    forecast_simulations: np.ndarray,
    assumptions: PlanningAssumptions,
    *,
    market_share: float | None = None,
    config: MonteCarloConfig | None = None,
) -> RiskResult:
    """Propaga simulações de forecast para risco de backlog sob regra de capacidade declarada.

    A política nesta fase é deliberadamente transparente: cada caminho utiliza a
    capacidade regular mais a capacidade extra como limite mensal e atende primeiro
    o backlog acumulado. A integração com o solver PuLP será feita na etapa de
    integração operacional, sem chamar esta aproximação de plano ótimo.
    """
    settings = config or MonteCarloConfig()
    simulations = _validate_simulations(forecast_simulations)
    if settings.n_simulations < 100:
        raise ValueError("n_simulations deve ser pelo menos 100 para métricas de cauda.")
    if not settings.confidence_levels or any(not 0 < level < 1 for level in settings.confidence_levels):
        raise ValueError("confidence_levels deve conter níveis entre 0 e 1.")
    share = float(market_share if market_share is not None else assumptions.participation)
    if not 0 < share <= 1:
        raise ValueError("market_share deve estar entre 0 e 1.")

    rng = np.random.default_rng(settings.seed)
    if simulations.shape[0] >= settings.n_simulations:
        selected = rng.choice(simulations.shape[0], size=settings.n_simulations, replace=False)
    else:
        selected = rng.choice(simulations.shape[0], size=settings.n_simulations, replace=True)
    saar_paths = simulations[selected]
    demand_paths = np.rint(np.maximum(saar_paths, 0.0) / 12.0 * 1_000_000.0 * share).astype(int)
    backlog_paths, inventory_paths = _capacity_policy_paths(
        demand_paths,
        capacity=max(0, int(assumptions.regular_capacity + assumptions.overtime_capacity)),
        initial_inventory=max(0, int(assumptions.initial_inventory)),
    )
    total_backlog = backlog_paths.sum(axis=1).astype(float)
    loss_distribution = total_backlog * float(assumptions.backlog_cost)
    capacity_required = demand_paths.max(axis=1).astype(float)
    metrics: dict[str, float | int | str] = {
        "n_simulations": int(settings.n_simulations),
        "horizon_months": int(demand_paths.shape[1]),
        "seed": int(settings.seed),
        "market_share": share,
        "policy": "full_capacity_backlog_first",
        "stockout_probability": float(np.mean(backlog_paths.max(axis=1) > 0)),
        "backlog_threshold_probability": float(np.mean(total_backlog > settings.backlog_threshold_units)),
        "expected_backlog_units": float(np.mean(total_backlog)),
        "p95_capacity_required_units": float(np.quantile(capacity_required, 0.95)),
        "capacity_at_risk_units": float(np.quantile(capacity_required, 0.95)),
        "expected_loss": float(np.mean(loss_distribution)),
    }
    for level in settings.confidence_levels:
        var = float(np.quantile(loss_distribution, level))
        tail = loss_distribution[loss_distribution >= var]
        metrics[f"VaR_{int(level * 100)}"] = var
        metrics[f"CVaR_{int(level * 100)}"] = float(np.mean(tail)) if len(tail) else var

    risk_table = pd.DataFrame(
        [
            {"metric": key, "value": value, "status": "estimated", "source": "monte_carlo_forecast_paths"}
            for key, value in metrics.items()
            if key not in {"seed", "policy"}
        ]
    )
    metadata = {
        "simulation_source": "forecast_simulations",
        "simulation_policy": "full_capacity_backlog_first",
        "random_seed": settings.seed,
        "n_simulations": settings.n_simulations,
        "confidence_levels": list(settings.confidence_levels),
        "market_share_status": "assumed",
        "optimization_status": "not_integrated",
        "created_at_utc": pd.Timestamp.utcnow().isoformat(),
    }
    return RiskResult(metrics, risk_table, backlog_paths, inventory_paths, loss_distribution, metadata)


def _validate_simulations(simulations: np.ndarray) -> np.ndarray:
    values = np.asarray(simulations, dtype=float)
    if values.ndim != 2 or values.shape[0] < 1 or values.shape[1] < 1:
        raise ValueError("forecast_simulations deve ser uma matriz 2D não vazia.")
    if not np.isfinite(values).all():
        raise ValueError("forecast_simulations não pode conter NaN ou infinito.")
    return values


def _capacity_policy_paths(
    demand_paths: np.ndarray,
    *,
    capacity: int,
    initial_inventory: int,
) -> tuple[np.ndarray, np.ndarray]:
    if capacity < 0 or initial_inventory < 0:
        raise ValueError("Capacidade e estoque inicial não podem ser negativos.")
    n_simulations, horizon = demand_paths.shape
    backlog_paths = np.zeros((n_simulations, horizon), dtype=int)
    inventory_paths = np.zeros((n_simulations, horizon), dtype=int)
    for simulation in range(n_simulations):
        backlog = 0
        inventory = initial_inventory
        for month in range(horizon):
            gross_demand = backlog + int(demand_paths[simulation, month])
            available = inventory + capacity
            served = min(available, gross_demand)
            backlog = gross_demand - served
            inventory = available - served
            backlog_paths[simulation, month] = backlog
            inventory_paths[simulation, month] = inventory
    return backlog_paths, inventory_paths
