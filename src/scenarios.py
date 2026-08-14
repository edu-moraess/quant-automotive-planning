"""Cenários explícitos de demanda e energia para análise de decisão."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from energy_intelligence import add_energy_cost_estimate

DEFAULT_SHOCKS = {
    "Downside": -0.10,
    "Base": 0.00,
    "Upside": 0.10,
    "Stress": 0.20,
}


def apply_demand_scenarios(forecast: pd.DataFrame, shocks: dict[str, float] = DEFAULT_SHOCKS) -> pd.DataFrame:
    """Aplica choques declarados à trajetória P50 sem alterar o forecast base silenciosamente."""
    if "p50" not in forecast.columns:
        raise ValueError("Forecast deve conter a coluna p50 para cenários de demanda.")
    rows: list[pd.DataFrame] = []
    for scenario, shock in shocks.items():
        frame = forecast[["data", "p50"]].copy()
        frame["cenario"] = scenario
        frame["choque_demanda_pct"] = float(shock * 100)
        frame["demanda_saar_milhoes"] = np.maximum(frame["p50"] * (1 + shock), 0)
        rows.append(frame.drop(columns="p50"))
    return pd.concat(rows, ignore_index=True)


def energy_price_sensitivity(
    vehicles: pd.DataFrame,
    prices: pd.DataFrame,
    shocks: Iterable[float] = (-0.20, 0.0, 0.20),
) -> pd.DataFrame:
    """Calcula custo mediano por 100 milhas sob choques proporcionais e explícitos de energia."""
    rows: list[dict[str, float | str]] = []
    for shock in shocks:
        if shock <= -1:
            raise ValueError("Choque de energia deve ser maior que -100%.")
        shocked = prices.copy()
        price_columns = ["gasolina_usd_gal", "diesel_usd_gal", "eletricidade_usd_kwh"]
        shocked[price_columns] = shocked[price_columns] * (1 + shock)
        enriched = add_energy_cost_estimate(vehicles, shocked)
        grouped = enriched.groupby("fonte_energia", as_index=False)["custo_energia_100mi_usd"].median().dropna()
        for row in grouped.itertuples(index=False):
            rows.append(
                {
                    "choque_preco_pct": float(shock * 100),
                    "fonte_energia": row.fonte_energia,
                    "custo_mediano_100mi_usd": float(row.custo_energia_100mi_usd),
                }
            )
    return pd.DataFrame(rows).sort_values(["fonte_energia", "choque_preco_pct"]).reset_index(drop=True)
