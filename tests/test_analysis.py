import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis import (  # noqa: E402
    construir_dobras,
    converter_demanda_veiculos,
    metricas,
    prepare_data,
    resolver_plano_producao,
)


def test_prepare_data_creates_operational_columns_and_quality_metrics():
    raw = pd.DataFrame(
        {
            "observation_date": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "TOTALSA": [12.0, 12.5, 13.0],
        }
    )
    data, quality = prepare_data(raw)
    assert list(data["mes"]) == [1, 2, 3]
    assert "variacao_anual_pct" in data.columns
    assert quality["duplicidades_brutas"] == 0
    assert quality["observacoes"] == 3


def test_metricas_returns_zero_for_perfect_prediction():
    values = np.array([10.0, 12.0, 14.0])
    metrics = metricas(values, values)
    assert metrics["MAE (milhões SAAR)"] == 0
    assert metrics["RMSE (milhões SAAR)"] == 0
    assert metrics["MAPE (%)"] == 0


def test_walk_forward_folds_are_temporally_ordered_and_non_overlapping():
    data = pd.DataFrame({"data": pd.date_range("2015-01-01", periods=48, freq="MS")})
    folds = construir_dobras(data, n_dobras=4, tamanho_dobra=6)
    for train_slice, test_slice in folds:
        assert train_slice.stop <= test_slice.start
        assert test_slice.stop - test_slice.start == 6
    assert folds[-1][1].stop == len(data)


def test_converter_demanda_uses_market_share_and_monthly_saar():
    scenario = pd.Series([12.0])
    result = converter_demanda_veiculos(scenario, participation=0.10)
    assert int(result.iloc[0]) == 100_000


def test_production_plan_respects_capacity_and_balance():
    demand = np.array([100, 150, 80])
    result = resolver_plano_producao(
        demand, capacidade=120, estoque_inicial=0, custo_producao=1, custo_estoque=1, custo_ruptura=100
    )
    assert result["status"] == "Optimal"
    assert max(result["producao"]) <= 120
    for index, demand_value in enumerate(demand):
        previous_inventory = 0 if index == 0 else result["estoque"][index - 1]
        previous_backlog = 0 if index == 0 else result["backlog"][index - 1]
        lhs = result["estoque"][index] - result["backlog"][index]
        rhs = previous_inventory - previous_backlog + result["producao"][index] - demand_value
        assert lhs == rhs


def test_prepare_data_rejects_empty_market_series():
    with pytest.raises(ValueError, match="DataFrame não vazio"):
        prepare_data(pd.DataFrame(columns=["observation_date", "TOTALSA"]))


def test_metricas_rejects_non_finite_predictions():
    with pytest.raises(ValueError, match="não podem conter NaN"):
        metricas(np.array([10.0, 12.0]), np.array([10.0, np.nan]))
