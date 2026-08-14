from pathlib import Path

import numpy as np
import pandas as pd

from analysis import compute_diagnostics, make_forecast, metricas, prepare_data, run_backtest


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
