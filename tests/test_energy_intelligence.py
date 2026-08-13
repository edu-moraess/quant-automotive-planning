from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from energy_intelligence import (  # noqa: E402
    add_energy_cost_estimate,
    energy_price_index,
    energy_summary,
    load_energy_prices,
    spearman_correlation_matrix,
    strongest_spearman_pairs,
)


def _prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "data": pd.to_datetime(["2026-01-01", "2026-02-01"]),
            "gasolina_usd_gal": [4.0, 4.2],
            "diesel_usd_gal": [5.0, 5.2],
            "eletricidade_usd_kwh": [0.2, 0.21],
        }
    )


def _vehicles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "make": ["A", "B", "C", "D"],
            "modelo_chave": ["A · One", "B · Two", "C · Three", "D · Four"],
            "fuelType1": ["Regular Gasoline", "Diesel", "Electricity", "Premium Gasoline or Electricity"],
            "powertrain": ["Combustão", "Diesel", "Elétrico a bateria", "Híbrido plug-in"],
            "comb08": [21.0, 26.0, 100.0, 45.0],
            "combE": [0.0, 0.0, 28.0, 0.0],
            "eficiencia_valida": [21.0, 26.0, 100.0, 45.0],
            "co2_valido": [420.0, 360.0, 0.0, 200.0],
            "custo_anual_valido": [3200.0, 2800.0, 900.0, 1800.0],
            "displ": [2.0, 3.0, np.nan, 1.8],
            "cylinders": [4.0, 6.0, np.nan, 4.0],
        }
    )


def test_energy_cost_per_100_miles_uses_correct_units():
    enriched = add_energy_cost_estimate(_vehicles(), _prices())
    gas = enriched.loc[enriched["make"] == "A", "custo_energia_100mi_usd"].iloc[0]
    diesel = enriched.loc[enriched["make"] == "B", "custo_energia_100mi_usd"].iloc[0]
    electric = enriched.loc[enriched["make"] == "C", "custo_energia_100mi_usd"].iloc[0]
    phev = enriched.loc[enriched["make"] == "D", "custo_energia_100mi_usd"].iloc[0]
    assert round(gas, 2) == 20.0
    assert round(diesel, 2) == 20.0
    assert round(electric, 2) == 5.88
    assert pd.isna(phev)


def test_price_index_and_energy_summary_are_structured():
    indexed = energy_price_index(_prices(), periods=2)
    assert set(indexed["energia"]) == {"Gasolina regular", "Diesel", "Eletricidade"}
    assert indexed.groupby("energia")["indice_base_100"].first().eq(100).all()
    enriched = add_energy_cost_estimate(_vehicles(), _prices())
    summary = energy_summary(enriched)
    assert {"Gasolina", "Diesel", "Eletricidade", "Híbrido plug-in"}.issubset(set(summary["fonte_energia"]))


def test_spearman_outputs_pair_counts_and_ranked_pairs():
    sample = pd.concat([_vehicles()] * 6, ignore_index=True)
    sample["id"] = range(1, len(sample) + 1)
    enriched = add_energy_cost_estimate(sample, _prices())
    correlations, counts = spearman_correlation_matrix(enriched)
    ranked = strongest_spearman_pairs(correlations, counts)
    assert correlations.shape == counts.shape
    assert not ranked.empty
    assert {"indicador_a", "indicador_b", "rho_spearman", "n"}.issubset(ranked.columns)


def test_energy_snapshot_contains_all_official_series():
    root = Path(__file__).resolve().parents[1]
    snapshot = load_energy_prices(root / "data" / "energy_price_snapshot.csv")
    assert {"data", "gasolina_usd_gal", "diesel_usd_gal", "eletricidade_usd_kwh"}.issubset(snapshot.columns)
    assert snapshot["gasolina_usd_gal"].notna().sum() > 300
    assert snapshot["diesel_usd_gal"].notna().sum() > 300
    assert snapshot["eletricidade_usd_kwh"].notna().sum() > 300
