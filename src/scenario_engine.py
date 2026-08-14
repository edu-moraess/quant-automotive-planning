"""Cenários, market share e sensibilidade operacional com hipóteses explícitas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from config import PlanningAssumptions
from planning import demand_from_saar, solve_production_plan


@dataclass(frozen=True)
class MarketShareSpec:
    """Parâmetro de participação com rótulo de proveniência e quantis opcionais."""

    p50: float = 0.08
    p10: float | None = None
    p90: float | None = None
    status: str = "assumed"
    source: str = "planning_assumption"

    def __post_init__(self) -> None:
        values = [self.p10, self.p50, self.p90]
        if not 0 < self.p50 <= 1:
            raise ValueError("p50 de market share deve estar entre 0 e 1.")
        if self.p10 is not None and not 0 < self.p10 <= 1:
            raise ValueError("p10 de market share deve estar entre 0 e 1.")
        if self.p90 is not None and not 0 < self.p90 <= 1:
            raise ValueError("p90 de market share deve estar entre 0 e 1.")
        present = [value for value in values if value is not None]
        if present != sorted(present):
            raise ValueError("Quantis de market share devem respeitar p10 ≤ p50 ≤ p90.")
        if self.status not in {"observed", "estimated", "assumed", "scenario-driven"}:
            raise ValueError("Status deve ser observed, estimated, assumed ou scenario-driven.")

    def quantiles(self) -> dict[str, float]:
        return {
            "p10": float(self.p10 if self.p10 is not None else self.p50),
            "p50": float(self.p50),
            "p90": float(self.p90 if self.p90 is not None else self.p50),
        }

    def shifted(self, delta_pp: float) -> MarketShareSpec:
        """Aplica choque em pontos percentuais mantendo o valor no domínio válido."""
        delta = float(delta_pp)
        values = self.quantiles()
        return MarketShareSpec(
            p10=float(np.clip(values["p10"] + delta, 1e-6, 1.0)),
            p50=float(np.clip(values["p50"] + delta, 1e-6, 1.0)),
            p90=float(np.clip(values["p90"] + delta, 1e-6, 1.0)),
            status="scenario-driven",
            source=f"{self.source}; choque={delta_pp:+.4f}",
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.quantiles(), "status": self.status, "source": self.source}


@dataclass(frozen=True)
class ScenarioSpec:
    """Objeto determinístico de cenário, separado de qualquer simulação."""

    scenario_id: str
    name: str
    description: str
    drivers: dict[str, float] = field(default_factory=dict)
    shock: dict[str, float] = field(default_factory=dict)
    probability: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.scenario_id or not self.name:
            raise ValueError("Cenário precisa de scenario_id e name.")
        if self.probability is not None and not 0 <= self.probability <= 1:
            raise ValueError("Probabilidade do cenário deve estar entre 0 e 1.")


def default_scenarios() -> tuple[ScenarioSpec, ...]:
    """Retorna cenários determinísticos com probabilidades assumidas explicitamente."""
    return (
        ScenarioSpec(
            "downside",
            "Downside",
            "Demanda abaixo do caso base",
            shock={"demand_pct": -0.10},
            probability=0.20,
            metadata={"probability_status": "assumed"},
        ),
        ScenarioSpec(
            "base",
            "Base",
            "Trajetória central sem choque declarado",
            shock={"demand_pct": 0.0},
            probability=0.50,
            metadata={"probability_status": "assumed"},
        ),
        ScenarioSpec(
            "upside",
            "Upside",
            "Demanda acima do caso base",
            shock={"demand_pct": 0.10},
            probability=0.20,
            metadata={"probability_status": "assumed"},
        ),
        ScenarioSpec(
            "stress",
            "Stress",
            "Demanda elevada com capacidade reduzida e crédito mais caro",
            drivers={"juros_bps": 100.0, "combustivel_pct": 0.20},
            shock={"demand_pct": 0.20, "capacity_pct": -0.10},
            probability=0.10,
            metadata={"probability_status": "assumed", "transmission_status": "partial"},
        ),
    )


def validate_scenarios(scenarios: tuple[ScenarioSpec, ...] | list[ScenarioSpec]) -> None:
    """Valida ids únicos e probabilidades quando o conjunto for probabilístico."""
    items = list(scenarios)
    ids = [item.scenario_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario_id deve ser único.")
    probabilities = [item.probability for item in items]
    if all(value is not None for value in probabilities) and not np.isclose(sum(probabilities), 1.0):
        raise ValueError("Probabilidades dos cenários devem somar 1 quando informadas.")


def scenario_demand(
    forecast: pd.DataFrame,
    scenario: ScenarioSpec,
    market_share: MarketShareSpec,
) -> pd.DataFrame:
    """Propaga um cenário determinístico para demanda e market share."""
    required = {"data", "p50"}
    if not required.issubset(forecast.columns):
        raise ValueError(f"Forecast precisa conter {sorted(required)}.")
    demand_shock = float(scenario.shock.get("demand_pct", 0.0))
    share = market_share.shifted(float(scenario.shock.get("market_share_delta_pp", 0.0)))
    result = forecast[["data", "p50"]].copy()
    result["scenario_id"] = scenario.scenario_id
    result["scenario_name"] = scenario.name
    result["scenario_probability"] = scenario.probability
    result["demand_shock_pct"] = demand_shock * 100
    result["market_share"] = share.p50
    result["market_share_status"] = share.status
    result["demand_saar_millions"] = np.maximum(result["p50"] * (1 + demand_shock), 0.0)
    result["demand_units"] = demand_from_saar(result["demand_saar_millions"], share.p50)
    return result


def run_scenario_engine(
    forecast: pd.DataFrame,
    assumptions: PlanningAssumptions,
    *,
    market_share: MarketShareSpec | None = None,
    scenarios: tuple[ScenarioSpec, ...] | list[ScenarioSpec] | None = None,
) -> dict[str, Any]:
    """Executa cenários determinísticos e o PL operacional sem misturar simulação."""
    share = market_share or MarketShareSpec(p50=assumptions.participation)
    specs = tuple(scenarios or default_scenarios())
    validate_scenarios(specs)
    rows: list[dict[str, Any]] = []
    solutions: dict[str, dict[str, Any]] = {}
    paths: dict[str, pd.DataFrame] = {}
    for scenario in specs:
        path = scenario_demand(forecast, scenario, share)
        capacity_factor = 1 + float(scenario.shock.get("capacity_pct", 0.0))
        scenario_assumptions = PlanningAssumptions(
            **{
                **assumptions.__dict__,
                "participation": float(path["market_share"].iloc[0]),
                "regular_capacity": max(0, int(round(assumptions.regular_capacity * capacity_factor))),
            }
        )
        solution = solve_production_plan(path["demand_units"].to_numpy(), scenario_assumptions, scenario.name)
        solutions[scenario.scenario_id] = solution
        paths[scenario.scenario_id] = path
        capacity = max(scenario_assumptions.regular_capacity + scenario_assumptions.overtime_capacity, 1)
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "Cenário": scenario.name,
                "Probabilidade assumida": scenario.probability,
                "Demanda total (veículos)": int(path["demand_units"].sum()),
                "Produção total (veículos)": int(sum(solution["producao"])),
                "Produção extra (veículos)": int(sum(solution["producao_extra"])),
                "Estoque final": int(solution["estoque"][-1]),
                "Backlog final": int(solution["backlog"][-1]),
                "Utilização média (%)": float(np.mean(solution["producao"]) / capacity * 100),
                "Custo total (US$)": float(solution["custo_total"]),
                "market_share_status": share.status,
                "transmission_status": scenario.metadata.get("transmission_status", "demand_only"),
            }
        )
    return {
        "scenarios": pd.DataFrame(rows),
        "scenario_specs": specs,
        "solutions": solutions,
        "paths": paths,
        "market_share": share.to_dict(),
        "output_type": "deterministic_scenario",
    }


def run_sensitivity_engine(
    forecast: pd.DataFrame,
    assumptions: PlanningAssumptions,
    *,
    market_share: MarketShareSpec | None = None,
) -> pd.DataFrame:
    """Mede impactos de choques operacionais e identifica drivers ainda não transmitidos."""
    base_share = market_share or MarketShareSpec(p50=assumptions.participation)
    base_spec = ScenarioSpec("base", "Base", "Referência", shock={"demand_pct": 0.0})
    base_path = scenario_demand(forecast, base_spec, base_share)
    base_solution = solve_production_plan(base_path["demand_units"].to_numpy(), assumptions, "Sensitivity_Base")
    base_metrics = _solution_metrics(base_solution, assumptions)
    shock_grid = {
        "demand_pct": (-0.10, 0.10),
        "market_share_delta_pp": (-0.01, 0.01),
        "fuel_price_pct": (-0.20, 0.20),
        "interest_bps": (100.0,),
        "capacity_pct": (-0.10, 0.10),
    }
    rows: list[dict[str, Any]] = []
    for driver, shocks in shock_grid.items():
        for shock in shocks:
            transmitted = driver in {"demand_pct", "market_share_delta_pp", "capacity_pct"}
            scenario = ScenarioSpec(
                scenario_id=f"sensitivity_{driver}_{shock}",
                name=f"Sensitivity {driver} {shock:+.4f}",
                description="Choque unitário para análise de sensibilidade",
                shock={driver: float(shock)},
                metadata={"transmission_status": "connected" if transmitted else "not_connected"},
            )
            path = scenario_demand(forecast, scenario, base_share)
            capacity_factor = 1 + float(scenario.shock.get("capacity_pct", 0.0))
            shocked_assumptions = PlanningAssumptions(
                **{
                    **assumptions.__dict__,
                    "regular_capacity": max(0, int(round(assumptions.regular_capacity * capacity_factor))),
                }
            )
            solution = solve_production_plan(path["demand_units"].to_numpy(), shocked_assumptions, scenario.name)
            metrics = _solution_metrics(solution, shocked_assumptions)
            rows.append(
                {
                    "driver": driver,
                    "shock": float(shock),
                    "transmission_status": "connected" if transmitted else "not_connected",
                    **{f"{key}_delta": metrics[key] - base_metrics[key] for key in base_metrics},
                }
            )
    return pd.DataFrame(rows)


def _solution_metrics(solution: dict[str, Any], assumptions: PlanningAssumptions) -> dict[str, float]:
    capacity = max(assumptions.regular_capacity + assumptions.overtime_capacity, 1)
    return {
        "production_total": float(sum(solution["producao"])),
        "inventory_final": float(solution["estoque"][-1]),
        "backlog_final": float(solution["backlog"][-1]),
        "overtime_total": float(sum(solution["producao_extra"])),
        "cost_total": float(solution["custo_total"]),
        "utilization_avg": float(np.mean(solution["producao"]) / capacity * 100),
        "backlog_flag": float(solution["backlog"][-1] > 0),
    }
