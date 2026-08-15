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
from acceptance_policy import ACCEPTANCE_POLICY  # noqa: E402

N_FOLDS = 4
FOLD_SIZE = 6
LAGS = [1, 12]
BIAS_WINDOW = 6
LB_LAGS = [ACCEPTANCE_POLICY.grouped_ljung_box_lag, 6, 12]


def load_market() -> pd.DataFrame:
    raw = pd.read_csv(ROOT / "data" / "TOTALSA_snapshot.csv")
    data, _ = analysis.prepare_data(raw)
    return data


def expanding_one_step_residuals(train: pd.DataFrame) -> np.ndarray:
    """Estima erros one-step usando somente observações anteriores a cada data."""
    min_history = max(LAGS) + 1
    errors: list[float] = []
    for target_index in range(min_history, len(train)):
        history = train.iloc[:target_index].reset_index(drop=True)
        prediction = float(analysis.prever_regressao_defasagens(history, 1)[0])
        actual = float(train["vendas_saar_milhoes"].iloc[target_index])
        errors.append(actual - prediction)
    return np.asarray(errors, dtype=float)


def fit_error_ar1(errors: np.ndarray) -> dict[str, float]:
    if len(errors) < 3:
        return {"intercept": 0.0, "phi": 0.0, "n": float(len(errors))}
    x = np.column_stack([np.ones(len(errors) - 1), errors[:-1]])
    intercept, phi = np.linalg.lstsq(x, errors[1:], rcond=None)[0]
    return {"intercept": float(intercept), "phi": float(phi), "n": float(len(errors))}


def apply_error_ar1(base: np.ndarray, train_errors: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    params = fit_error_ar1(train_errors)
    previous = float(train_errors[-1]) if len(train_errors) else 0.0
    corrections: list[float] = []
    for _ in range(len(base)):
        correction = params["intercept"] + params["phi"] * previous
        corrections.append(correction)
        previous = correction
    correction_array = np.asarray(corrections, dtype=float)
    return base + correction_array, {**params, "corrections": corrections}


def apply_recent_bias(base: np.ndarray, train_errors: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    window = train_errors[-BIAS_WINDOW:] if len(train_errors) else np.asarray([0.0])
    bias = float(np.mean(window))
    return base + bias, {"window": int(len(window)), "bias": bias}


def grouped_ljung_box(errors: np.ndarray) -> dict[str, dict[str, float]]:
    table = acorr_ljungbox(errors, lags=LB_LAGS, return_df=True)
    return {
        str(lag): {
            "statistic": float(table.loc[lag, "lb_stat"]),
            "pvalue": float(table.loc[lag, "lb_pvalue"]),
        }
        for lag in LB_LAGS
    }


def fold_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    train_target: np.ndarray,
) -> dict[str, float]:
    metrics = analysis.metricas(actual, predicted, train_target)
    return {
        "mape": float(metrics["MAPE (%)"]),
        "mae": float(metrics["MAE (milhões SAAR)"]),
        "rmse": float(metrics["RMSE (milhões SAAR)"]),
        "wape": float(metrics["WAPE (%)"]),
        "smape": float(metrics["sMAPE (%)"]),
        "mase": float(metrics["MASE"]),
    }


def evaluate_method(data: pd.DataFrame, method: str) -> dict[str, Any]:
    fold_details: list[dict[str, Any]] = []
    actuals_by_fold: list[np.ndarray] = []
    predictions_by_fold: list[np.ndarray] = []
    fold_slices = analysis.construir_dobras(data, N_FOLDS, FOLD_SIZE)
    for fold_number, (train_slice, test_slice) in enumerate(fold_slices, start=1):
        train = data.iloc[train_slice].reset_index(drop=True)
        test = data.iloc[test_slice].reset_index(drop=True)
        base = analysis.prever_regressao_defasagens(train, len(test))
        train_errors = expanding_one_step_residuals(train)
        if method == "baseline_current":
            prediction = base
            correction_metadata: dict[str, Any] = {"corrections": [0.0] * len(base)}
        elif method == "error_ar1":
            prediction, correction_metadata = apply_error_ar1(base, train_errors)
        elif method == "bias_recent6":
            prediction, correction_metadata = apply_recent_bias(base, train_errors)
        else:
            raise ValueError(f"Método desconhecido: {method}")
        actual = test["vendas_saar_milhoes"].to_numpy(dtype=float)
        metrics = fold_metrics(actual, prediction, train["vendas_saar_milhoes"].to_numpy(dtype=float))
        fold_details.append(
            {
                "fold": fold_number,
                "periodo_oos": f"{test['data'].min():%m/%Y}–{test['data'].max():%m/%Y}",
                **metrics,
                "mean_oos_error": float(np.mean(actual - prediction)),
                "oos_errors": [float(value) for value in actual - prediction],
                "train_error_count": int(len(train_errors)),
                "train_error_mean": float(np.mean(train_errors)) if len(train_errors) else 0.0,
                "train_error_std": float(np.std(train_errors, ddof=1)) if len(train_errors) > 1 else 0.0,
                "correction": correction_metadata,
            }
        )
        actuals_by_fold.append(actual)
        predictions_by_fold.append(prediction)
    errors = np.concatenate(
        [actual - prediction for actual, prediction in zip(actuals_by_fold, predictions_by_fold, strict=True)]
    )
    metrics_by_fold = [
        {key: row[key] for key in ["mape", "mae", "rmse", "wape", "smape", "mase"]} for row in fold_details
    ]
    overall = {key: float(np.mean([row[key] for row in metrics_by_fold])) for key in metrics_by_fold[0]}
    fixed_intervals = analysis.prequential_interval_quality(actuals_by_fold, predictions_by_fold)
    lb = grouped_ljung_box(errors)
    return {
        "method": method,
        "lags": LAGS,
        "n_folds": N_FOLDS,
        "fold_size_months": FOLD_SIZE,
        "overall_metrics": overall,
        "fold_metrics": fold_details,
        "ljung_box_oos_grouped": lb,
        "prequential_interval_fixed": fixed_intervals,
        "n_oos_residuals": int(len(errors)),
        "oos_mean_error": float(np.mean(errors)),
        "acceptance": {
            "ljung_box_primary": lb[str(ACCEPTANCE_POLICY.grouped_ljung_box_lag)]["pvalue"] >= ACCEPTANCE_POLICY.alpha,
            "mape_floor": overall["mape"] <= ACCEPTANCE_POLICY.mape_acceptance_max_pct,
            "coverage_floor": fixed_intervals["coverage_p10_p90"] >= ACCEPTANCE_POLICY.coverage_acceptance_min,
            "mape_nominal": overall["mape"] <= ACCEPTANCE_POLICY.mape_nominal_target_max_pct,
            "coverage_nominal": fixed_intervals["coverage_p10_p90"] >= ACCEPTANCE_POLICY.coverage_nominal_target,
        },
    }


def compare_to_baseline(results: list[dict[str, Any]]) -> None:
    baseline = next(row for row in results if row["method"] == "baseline_current")
    for row in results:
        metrics = row["overall_metrics"]
        base_metrics = baseline["overall_metrics"]
        row["delta_vs_baseline"] = {
            "mape_pp": metrics["mape"] - base_metrics["mape"],
            "rmse": metrics["rmse"] - base_metrics["rmse"],
            "mae": metrics["mae"] - base_metrics["mae"],
            "wape_pp": metrics["wape"] - base_metrics["wape"],
            "smape_pp": metrics["smape"] - base_metrics["smape"],
            "mase": metrics["mase"] - base_metrics["mase"],
            "coverage_pp": (
                row["prequential_interval_fixed"]["coverage_p10_p90"]
                - baseline["prequential_interval_fixed"]["coverage_p10_p90"]
            ),
            "pinball": (
                row["prequential_interval_fixed"]["pinball_loss_medio"]
                - baseline["prequential_interval_fixed"]["pinball_loss_medio"]
            ),
            "ljung_box_lag3_pvalue": (
                row["ljung_box_oos_grouped"]["3"]["pvalue"] - baseline["ljung_box_oos_grouped"]["3"]["pvalue"]
            ),
            "ljung_box_lag12_pvalue": (
                row["ljung_box_oos_grouped"]["12"]["pvalue"] - baseline["ljung_box_oos_grouped"]["12"]["pvalue"]
            ),
        }


def main() -> None:
    data = load_market()
    methods = ["baseline_current", "error_ar1", "bias_recent6"]
    results = [evaluate_method(data, method) for method in methods]
    compare_to_baseline(results)
    payload = {
        "protocol": {
            "source": "data/TOTALSA_snapshot.csv real versionado",
            "n_folds": N_FOLDS,
            "fold_size_months": FOLD_SIZE,
            "base_specification": "Ridge alpha=1 com lag_1, lag_12, tendência e dummies mensais",
            "correction_methods": {
                "error_ar1": "AR(1) dos erros one-step expansivos estimados apenas no treino de cada dobra",
                "bias_recent6": "correção aditiva pela média dos seis erros one-step mais recentes do treino",
            },
            "no_future_information": True,
            "metrics": ["MAPE", "RMSE", "WAPE", "sMAPE", "MASE", "Ljung-Box agrupado", "coverage", "Pinball Loss"],
            "acceptance_policy": ACCEPTANCE_POLICY.as_dict(),
        },
        "decision": {
            "forecast_operational_changed": False,
            "promotion_allowed_in_stage": False,
            "selection_rule": "comparar contra baseline sem R2 in-sample; exigir melhora conjunta sem piora material de erro ou cobertura",
        },
        "methods": results,
    }
    output = ROOT / "data" / "model_artifacts" / "operational_medium_range_correction_backtest.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
