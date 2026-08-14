import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis import (
    compute_diagnostics,
    make_forecast,
    metricas,
    prepare_data,
    prequential_interval_quality,
    run_backtest,
)
from forecast_engine import (
    PRIMARY_MODEL,
    aggregate_horizon_metrics,
    build_model_registry,
    select_model_by_evidence,
    walk_forward_by_horizon,
)


def _market_data() -> pd.DataFrame:
    root = Path(__file__).resolve().parents[1]
    raw = pd.read_csv(root / "data" / "TOTALSA_snapshot.csv")
    data, _ = prepare_data(raw)
    return data


def test_metrics_include_scale_and_percentage_measures():
    metrics = metricas(np.array([10.0, 12.0]), np.array([9.0, 13.0]), insample=np.array([8.0, 9.0, 10.0]))
    assert {"MAE (milhões SAAR)", "RMSE (milhões SAAR)", "MAPE (%)", "sMAPE (%)", "WAPE (%)", "MASE"}.issubset(metrics)
    assert metrics["MAE (milhões SAAR)"] == 1.0
    assert metrics["WAPE (%)"] > 0


def test_diagnostics_include_kpss_and_stl():
    diagnostics = compute_diagnostics(_market_data())
    assert {"adf_level", "adf_diff", "kpss_level", "stl", "acf", "pacf"}.issubset(diagnostics)
    assert not diagnostics["stl"].empty


def test_backtest_and_probabilistic_forecast_expose_quantiles():
    data = _market_data()
    backtest = run_backtest(data, n_dobras=2, tamanho_dobra=3)
    forecast, simulations = make_forecast(data, backtest, horizon=4, bootstrap_replicas=200, seed=11)
    assert "AutoReg sazonal" in set(backtest["results"]["modelo"])
    assert {"p10", "p25", "p50", "p75", "p90", "cenario_base"}.issubset(forecast.columns)
    assert np.all(forecast["p10"] <= forecast["p50"])
    assert np.all(forecast["p50"] <= forecast["p90"])
    assert simulations.shape == (200, 4)
    assert backtest["interval_quality"]["pinball_loss_medio"] >= 0
    assert backtest["prequential_interval_quality"]["observacoes_avaliadas"] == 3
    assert 0 <= backtest["prequential_interval_quality"]["coverage_p10_p90"] <= 1


def test_prequential_calibration_does_not_use_future_fold_residuals():
    actuals = [np.array([0.0, 0.0]), np.array([10.0, 10.0])]
    predictions = [np.array([0.0, 0.0]), np.array([0.0, 0.0])]
    quality = prequential_interval_quality(actuals, predictions)
    assert quality["observacoes_avaliadas"] == 2
    assert quality["dobras_avaliadas"] == 1
    assert quality["coverage_p10_p90"] == 0.0
    assert quality["pinball_loss_medio"] >= 0


def test_probabilistic_forecast_is_reproducible_and_non_negative():
    data = _market_data()
    backtest = run_backtest(data, n_dobras=2, tamanho_dobra=3)
    first_forecast, first_simulations = make_forecast(data, backtest, horizon=4, bootstrap_replicas=100, seed=17)
    second_forecast, second_simulations = make_forecast(data, backtest, horizon=4, bootstrap_replicas=100, seed=17)
    assert np.array_equal(first_simulations, second_simulations)
    assert np.all(first_simulations >= 0)
    assert np.all(first_forecast["p10"] <= first_forecast["p50"])
    assert np.all(first_forecast["p50"] <= first_forecast["p90"])


def test_modular_forecast_registry_keeps_lagged_regression_as_primary():
    registry = build_model_registry()
    assert set(registry) == {PRIMARY_MODEL, "Seasonal Naive", "Holt-Winters", "AutoReg"}
    assert registry[PRIMARY_MODEL].diagnostics()["role"] == "primary"


def test_walk_forward_by_horizon_returns_model_horizon_contract():
    results = walk_forward_by_horizon(_market_data(), horizons=(1, 3), n_origins=2)
    assert {"model", "origin", "horizon", "RMSE", "MAE", "WAPE", "sMAPE", "MASE", "MAPE", "Bias"}.issubset(
        results.columns
    )
    summary = aggregate_horizon_metrics(results)
    assert set(summary["horizon"]) == {1, 3}
    assert (summary["valid_origins"] == 2).all()


def test_selection_prefers_primary_inside_mape_tolerance():
    summary = pd.DataFrame(
        {
            "model": [PRIMARY_MODEL, "Holt-Winters"],
            "MAPE": [3.00, 2.95],
            "RMSE": [1.0, 0.9],
        }
    )
    assert select_model_by_evidence(summary, tolerance_mape_pp=0.10) == PRIMARY_MODEL
