"""Camada de decisão derivada de métricas quantitativas, sem linguagem prescritiva oculta."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DecisionThresholds:
    """Limiares declarados para transformar métricas em sinais operacionais."""

    max_stockout_probability: float = 0.20
    max_backlog_probability: float = 0.20
    max_mape_pct: float = 5.0
    min_coverage_p10_p90: float = 0.70
    max_capacity_utilization_pct: float = 95.0


@dataclass(frozen=True)
class DecisionSignal:
    """Sinal auditável, sempre ligado a uma métrica e a um limiar."""

    signal_id: str
    label: str
    status: str
    value: float | None
    threshold: float | None
    unit: str
    evidence: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "label": self.label,
            "status": self.status,
            "value": self.value,
            "threshold": self.threshold,
            "unit": self.unit,
            "evidence": self.evidence,
            "source": self.source,
        }


def build_decision_intelligence(
    *,
    forecast_metrics: dict[str, Any] | None = None,
    risk_metrics: dict[str, Any] | None = None,
    robust_metrics: dict[str, Any] | None = None,
    scenario_table: pd.DataFrame | None = None,
    assumptions: dict[str, Any] | None = None,
    thresholds: DecisionThresholds | None = None,
) -> dict[str, Any]:
    """Produz sinais, confiança e ações condicionais a partir das saídas quantitativas."""
    limits = thresholds or DecisionThresholds()
    forecast = forecast_metrics or {}
    risk = risk_metrics or {}
    robust = robust_metrics or {}
    assumed = assumptions or {}
    signals = [
        _threshold_signal(
            "forecast_mape",
            "Erro fora da amostra",
            _number(forecast.get("mape_pct", forecast.get("MAPE"))),
            limits.max_mape_pct,
            "percentual",
            "menor ou igual ao limiar é favorável",
            "forecast_walk_forward",
            lower_is_better=True,
        ),
        _threshold_signal(
            "interval_coverage",
            "Cobertura P10–P90",
            _number(forecast.get("coverage_p10_p90")),
            limits.min_coverage_p10_p90,
            "proporção",
            "maior ou igual ao limiar é favorável",
            "forecast_residuals_oos",
            lower_is_better=False,
        ),
        _threshold_signal(
            "stockout_probability",
            "Probabilidade de stockout",
            _number(risk.get("stockout_probability")),
            limits.max_stockout_probability,
            "proporção",
            "menor ou igual ao limiar é favorável",
            "risk_engine_monte_carlo",
            lower_is_better=True,
        ),
        _threshold_signal(
            "backlog_probability",
            "Probabilidade de backlog final",
            _number(robust.get("probability_backlog_final")),
            limits.max_backlog_probability,
            "proporção",
            "menor ou igual ao limiar é favorável",
            "robust_planning_pulp_sampled_paths",
            lower_is_better=True,
        ),
        _threshold_signal(
            "capacity_at_risk",
            "Utilização no percentil de risco",
            _number(robust.get("capacity_at_risk_pct")),
            limits.max_capacity_utilization_pct,
            "% capacidade",
            "menor ou igual ao limiar é favorável",
            "robust_planning_pulp_sampled_paths",
            lower_is_better=True,
        ),
    ]
    valid_signals = [signal for signal in signals if signal.value is not None]
    red = [signal for signal in valid_signals if signal.status == "red"]
    amber = [signal for signal in valid_signals if signal.status == "amber"]
    if red:
        decision_status = "red"
        decision_label = "Revisar capacidade, estoque ou hipóteses antes de executar"
    elif amber:
        decision_status = "amber"
        decision_label = "Executar somente com monitoramento e gatilhos definidos"
    elif valid_signals:
        decision_status = "green"
        decision_label = "Preservar plano dentro das hipóteses validadas"
    else:
        decision_status = "unavailable"
        decision_label = "Decisão indisponível: métricas quantitativas não foram fornecidas"

    actions = _conditional_actions(decision_status, red, amber, assumed, risk, robust)
    limitations = _limitations(assumed, risk, robust, scenario_table)
    confidence = _confidence(valid_signals, red, amber, forecast, risk, robust)
    return {
        "decision_status": decision_status,
        "decision_label": decision_label,
        "confidence": confidence,
        "signals": pd.DataFrame([signal.to_dict() for signal in signals]),
        "actions": actions,
        "limitations": limitations,
        "evidence": {
            "forecast_metrics": forecast,
            "risk_metrics": risk,
            "robust_metrics": robust,
            "scenario_rows": int(len(scenario_table)) if scenario_table is not None else 0,
        },
        "thresholds": limits.__dict__,
    }


def _threshold_signal(
    signal_id: str,
    label: str,
    value: float | None,
    threshold: float,
    unit: str,
    evidence: str,
    source: str,
    *,
    lower_is_better: bool,
) -> DecisionSignal:
    if value is None or not np.isfinite(value):
        return DecisionSignal(signal_id, label, "unavailable", None, threshold, unit, "métrica ausente", source)
    gap = (value - threshold) if lower_is_better else (threshold - value)
    if lower_is_better:
        status = "green" if value <= threshold else "red" if value > threshold * 1.25 else "amber"
    else:
        status = "green" if value >= threshold else "red" if value < threshold * 0.75 else "amber"
    signal_evidence = f"{evidence}; valor={value:.4f}; limiar={threshold:.4f}; gap={gap:.4f}"
    return DecisionSignal(signal_id, label, status, float(value), threshold, unit, signal_evidence, source)


def _conditional_actions(
    status: str,
    red: list[DecisionSignal],
    amber: list[DecisionSignal],
    assumptions: dict[str, Any],
    risk: dict[str, Any],
    robust: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if red:
        actions.append(
            {
                "priority": "high",
                "action": "revisar capacidade e estoque de segurança",
                "trigger": [signal.signal_id for signal in red],
                "basis": "métrica acima do limiar declarado",
            }
        )
    if amber:
        actions.append(
            {
                "priority": "medium",
                "action": "monitorar semanalmente os sinais amber e reestimar após atualização das fontes",
                "trigger": [signal.signal_id for signal in amber],
                "basis": "métrica próxima do limiar declarado",
            }
        )
    if status == "green":
        actions.append(
            {
                "priority": "normal",
                "action": "preservar plano base dentro das hipóteses atuais",
                "trigger": ["qualquer sinal red", "mudança de origem ou staleness"],
                "basis": "sinais observados dentro dos limites",
            }
        )
    if assumptions.get("market_share_status", "assumed") != "observed":
        actions.append(
            {
                "priority": "disclosure",
                "action": "revisar a hipótese de market share antes de decisão comercial",
                "trigger": ["market_share_status != observed"],
                "basis": "market share não observado no dataset público",
            }
        )
    if risk.get("optimization_status") == "not_integrated" or robust.get("optimization_status") == "not_integrated":
        actions.append(
            {
                "priority": "disclosure",
                "action": "interpretar risco como estimativa e não como solução ótima estocástica",
                "trigger": ["optimization_status"],
                "basis": "camada de risco ainda não integrada ao solver em uma única métrica",
            }
        )
    return actions


def _limitations(
    assumptions: dict[str, Any],
    risk: dict[str, Any],
    robust: dict[str, Any],
    scenario_table: pd.DataFrame | None,
) -> list[str]:
    limitations = [
        "FRED TOTALSA representa mercado agregado e não vendas por marca ou modelo.",
        "Market share permanece hipótese quando o status não é observed.",
        "Cenários e probabilidades só são interpretados como assumidos quando não há distribuição observada.",
    ]
    if risk.get("simulation_source") not in {None, "forecast_simulations"}:
        limitations.append("A origem das simulações não corresponde ao contrato esperado de forecast.")
    if robust.get("optimization_status") != "integrated_pulp_sampled_paths":
        limitations.append("Não há otimização PuLP por caminhos amostrados registrada na saída.")
    if scenario_table is None or scenario_table.empty:
        limitations.append("Não foi fornecida tabela de cenários para comparação operacional.")
    return limitations


def _confidence(
    valid: list[DecisionSignal],
    red: list[DecisionSignal],
    amber: list[DecisionSignal],
    forecast: dict[str, Any],
    risk: dict[str, Any],
    robust: dict[str, Any],
) -> dict[str, Any]:
    if not valid:
        return {"level": "unavailable", "score": None, "basis": "sem métricas quantitativas"}
    score = max(0.0, min(1.0, (len(valid) - len(red) - 0.5 * len(amber)) / len(valid)))
    level = "high" if score >= 0.75 else "medium" if score >= 0.50 else "low"
    basis = {
        "signals_available": len(valid),
        "signals_red": len(red),
        "signals_amber": len(amber),
        "forecast_available": bool(forecast),
        "risk_available": bool(risk),
        "robust_planning_available": bool(robust),
    }
    return {"level": level, "score": score, "basis": basis}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None
