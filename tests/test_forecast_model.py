from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data.contracts import TimeWindow
from data.feature_builder import FeatureBuilder
from forecast_model import build_regression_matrix, save_performance_v2, walk_forward_ols


def test_feature_builder_materializes_macro_differences_and_lags():
    dates = pd.date_range("2024-01-01", periods=7, freq="MS")
    fred = pd.DataFrame(
        {
            "data": dates,
            "disponivel_em": dates,
            "serie": ["CPIAUCSL"] * len(dates),
            "feature": ["cpi"] * len(dates),
            "valor": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
        }
    )
    market = FeatureBuilder._build_market_features(
        fred,
        pd.DataFrame(),
        TimeWindow(start="2024-01-01", as_of="2024-07-31"),
    )

    assert {"cpi", "CPI_diff", "CPI_diff_lag1", "CPI_diff_lag3"}.issubset(market.columns)
    assert market.loc[pd.Timestamp("2024-03-01"), "CPI_diff_lag1"] == market.loc[pd.Timestamp("2024-02-01"), "CPI_diff"]
    assert market.loc[pd.Timestamp("2024-05-01"), "CPI_diff_lag3"] == market.loc[pd.Timestamp("2024-02-01"), "CPI_diff"]


def test_walk_forward_supports_newey_west_and_glsar_contracts():
    matrix = build_regression_matrix()
    newey = walk_forward_ols(matrix, estimator="newey_west")
    glsar = walk_forward_ols(matrix, estimator="glsar")

    assert newey["estimador"] == "newey_west"
    assert glsar["estimador"] == "glsar"
    for result in (newey, glsar):
        assert len(result["fold_metrics"]) == 3
        assert result["mape_medio"] >= 0
        assert 0 <= result["coverage_p10_p90"] <= 1


def test_performance_artifact_describes_effective_regressors_and_app_role(tmp_path):
    matrix = build_regression_matrix()
    metrics = walk_forward_ols(matrix, estimator="newey_west")
    path = save_performance_v2(metrics, tmp_path / "model_performance_v2.json")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["regressores"] == [
        "y_lag1",
        "X_CPI_diff_lag1",
        "X_CPI_diff_lag3",
        "X_PRODIND_diff_lag2",
    ]
    assert payload["papel_no_app"] == "diagnostico_de_drivers"
    assert payload["nao_alimenta_forecast_principal"] is True
    assert payload["descricao"] == "Regressores usados: y_lag1, X_CPI_diff_lag1, X_CPI_diff_lag3, X_PRODIND_diff_lag2."
    assert "FEDFUNDS" not in payload["descricao"]
    assert payload["candidatos_avaliados_e_nao_selecionados"] == []
    assert payload["drivers_configurados_mas_ausentes_na_matriz"]
    assert payload["status_operacional"] == "nao_aprovado"
    assert set(payload["criterios_aceite_reprovados"]) == {"durbin_watson", "mape"}
