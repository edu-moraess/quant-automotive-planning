from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox

ROOT = Path("/home/ubuntu/quant_automotivo_streamlit")
sys.path.insert(0, str(ROOT / "src"))

import analysis  # noqa: E402
import forecast_model as fm  # noqa: E402

LAGS = [1, 2, 3, 6, 9, 12]
N_FOLDS = 3
FOLD_SIZE = 6
LB_LAG = 3
LB_ALPHA = 0.05
VOL_WINDOW = 6


def joint_matrix() -> pd.DataFrame:
    base = fm.build_regression_matrix()
    matrix = base.drop(columns=[column for column in base.columns if column.startswith("y_lag")]).copy()
    for lag in LAGS:
        matrix[f"y_lag{lag}"] = matrix["y"].shift(lag)
    return matrix.dropna()


def split_folds(result: dict[str, Any]) -> tuple[list[np.ndarray], list[np.ndarray]]:
    actual = np.asarray(result["actuals"], dtype=float)
    predicted = np.asarray(result["predictions"], dtype=float)
    return [actual[i * FOLD_SIZE : (i + 1) * FOLD_SIZE] for i in range(N_FOLDS)], [
        predicted[i * FOLD_SIZE : (i + 1) * FOLD_SIZE] for i in range(N_FOLDS)
    ]


def prequential_intervals(
    actuals_by_fold: list[np.ndarray],
    predictions_by_fold: list[np.ndarray],
    *,
    volatility_conditioned: bool,
    window: int = VOL_WINDOW,
) -> dict[str, Any]:
    prior: list[np.ndarray] = []
    coverage_by_horizon: list[list[bool]] = [[] for _ in range(FOLD_SIZE)]
    pinball_by_horizon: list[list[float]] = [[] for _ in range(FOLD_SIZE)]
    scales: list[float] = []
    for actual, predicted in zip(actuals_by_fold, predictions_by_fold, strict=True):
        if prior:
            residuals = np.concatenate(prior)
            q10, median, q90 = np.quantile(residuals, [0.10, 0.50, 0.90])
            scale = 1.0
            if volatility_conditioned and len(residuals) >= 3:
                recent = residuals[-min(window, len(residuals)) :]
                recent_std = float(np.std(recent, ddof=1)) if len(recent) > 1 else 0.0
                global_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
                scale = recent_std / global_std if global_std > 1e-12 else 1.0
                scale = float(np.clip(scale, 0.5, 2.0))
            if volatility_conditioned:
                lower = median + (q10 - median) * scale
                upper = median + (q90 - median) * scale
            else:
                lower, upper = q10, q90
            lower_values = predicted + lower
            upper_values = predicted + upper
            covered = (actual >= lower_values) & (actual <= upper_values)
            for horizon, value in enumerate(covered):
                coverage_by_horizon[horizon].append(bool(value))
            for quantile, adjustment in ((0.10, lower), (0.50, median), (0.90, upper)):
                error = actual - (predicted + adjustment)
                loss = np.maximum(quantile * error, (quantile - 1) * error)
                for horizon, value in enumerate(loss):
                    pinball_by_horizon[horizon].append(float(value))
            scales.append(scale)
        prior.append(actual - predicted)
    covered = [value for values in coverage_by_horizon for value in values]
    losses = [value for values in pinball_by_horizon for value in values]
    return {
        "coverage_p10_p90": float(np.mean(covered)) if covered else np.nan,
        "pinball_loss_medio": float(np.mean(losses)) if losses else np.nan,
        "observacoes_avaliadas": len(covered),
        "dobras_avaliadas": len(actuals_by_fold) - 1,
        "coverage_by_horizon": [float(np.mean(values)) if values else np.nan for values in coverage_by_horizon],
        "pinball_by_horizon": [float(np.mean(values)) if values else np.nan for values in pinball_by_horizon],
        "scales_used": scales,
    }


def horizon_metrics(matrix: pd.DataFrame, result: dict[str, Any]) -> list[dict[str, float | int]]:
    actuals_by_fold, predictions_by_fold = split_folds(result)
    start_test = len(matrix) - N_FOLDS * FOLD_SIZE
    rows: list[dict[str, float | int]] = []
    for horizon in range(FOLD_SIZE):
        fold_rows = []
        for fold, (actual, predicted) in enumerate(zip(actuals_by_fold, predictions_by_fold, strict=True)):
            train_end = start_test + fold * FOLD_SIZE
            metrics = analysis.metricas(
                np.asarray([actual[horizon]]),
                np.asarray([predicted[horizon]]),
                matrix["y"].to_numpy(dtype=float)[:train_end],
            )
            fold_rows.append(metrics)
        rows.append(
            {
                "horizon": horizon + 1,
                "mae": float(np.mean([row["MAE (milhões SAAR)"] for row in fold_rows])),
                "rmse": float(np.mean([row["RMSE (milhões SAAR)"] for row in fold_rows])),
                "mape": float(np.mean([row["MAPE (%)"] for row in fold_rows])),
                "wape": float(np.mean([row["WAPE (%)"] for row in fold_rows])),
                "smape": float(np.mean([row["sMAPE (%)"] for row in fold_rows])),
                "mase": float(np.mean([row["MASE"] for row in fold_rows])),
            }
        )
    return rows


def evaluate(name: str, matrix: pd.DataFrame) -> dict[str, Any]:
    result = fm.walk_forward_ols(matrix, estimator="newey_west")
    actuals_by_fold, predictions_by_fold = split_folds(result)
    errors = np.asarray(result["oos_residuals"], dtype=float)
    lb = acorr_ljungbox(errors, lags=[LB_LAG], return_df=True)
    overall = analysis.metricas(
        result["actuals"], result["predictions"], matrix["y"].to_numpy(dtype=float)[: len(matrix) - 18]
    )
    fixed_interval = prequential_intervals(actuals_by_fold, predictions_by_fold, volatility_conditioned=False)
    volatility_interval = prequential_intervals(actuals_by_fold, predictions_by_fold, volatility_conditioned=True)
    return {
        "name": name,
        "lag_specification": [1] if name == "current" else LAGS,
        "n_matrix_rows": len(matrix),
        "regressors": result["regressores"],
        "overall_metrics": overall,
        "horizon_metrics": horizon_metrics(matrix, result),
        "fold_metrics": result["fold_metrics"],
        "ljung_box_oos_grouped": {
            "lag": LB_LAG,
            "stat": float(lb["lb_stat"].iloc[0]),
            "pvalue": float(lb["lb_pvalue"].iloc[0]),
            "n": len(errors),
            "accepted": bool(float(lb["lb_pvalue"].iloc[0]) >= LB_ALPHA),
        },
        "interval_fixed_prequential": fixed_interval,
        "interval_volatility_prequential": volatility_interval,
        "acceptance": {
            "ljung_box_oos_grouped": bool(float(lb["lb_pvalue"].iloc[0]) >= LB_ALPHA),
            "mape": bool(overall["MAPE (%)"] <= 2.87),
            "coverage_fixed": bool(fixed_interval["coverage_p10_p90"] >= 0.80),
            "coverage_volatility": bool(volatility_interval["coverage_p10_p90"] >= 0.80),
            "volatility_improves_coverage": bool(
                volatility_interval["coverage_p10_p90"] > fixed_interval["coverage_p10_p90"]
            ),
        },
    }


def main() -> None:
    current = fm.build_regression_matrix()
    joint = joint_matrix()
    payload = {
        "protocol": {
            "source": "feature store local com TOTALSA, CPIAUCSL e INDPRO reais",
            "folds": N_FOLDS,
            "fold_size_months": FOLD_SIZE,
            "lag_specification_joint": LAGS,
            "grouped_ljung_box_lag": LB_LAG,
            "grouped_ljung_box_alpha": LB_ALPHA,
            "volatility_window": VOL_WINDOW,
            "selection_excludes_in_sample_r2": True,
            "metrics": ["RMSE", "MAE", "MAPE", "WAPE", "sMAPE", "MASE", "coverage_p10_p90", "pinball_loss"],
        },
        "current": evaluate("current", current),
        "joint_lags": evaluate("joint_lags", joint),
    }
    output = ROOT / "data" / "model_artifacts" / "joint_lags_volatility_backtest.json"
    output.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.item() if hasattr(value, "item") else value,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.item() if hasattr(value, "item") else value,
        )
    )


if __name__ == "__main__":
    main()
