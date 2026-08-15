"""Política única de aceite para os modelos quantitativos do projeto.

Os limiares são referências de validação fora da amostra, não garantias de
performance. A política separa o piso operacional alcançável do alvo nominal
exploratório preservado para acompanhamento.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AcceptancePolicy:
    """Critérios comuns para comparar modelos sem usar R² in-sample."""

    version: str = "2026.08"
    alpha: float = 0.05
    grouped_ljung_box_lag: int = 3
    mape_acceptance_max_pct: float = 4.00
    mape_nominal_target_max_pct: float = 2.87
    coverage_acceptance_min: float = 0.75
    coverage_nominal_target: float = 0.80
    diagnostic_tests_required: tuple[str, ...] = ("ARCH", "CUSUM")

    def as_dict(self) -> dict[str, object]:
        """Retorna uma representação JSON-serializável da política."""
        payload = asdict(self)
        payload["diagnostic_tests_required"] = list(self.diagnostic_tests_required)
        return payload


ACCEPTANCE_POLICY = AcceptancePolicy()
