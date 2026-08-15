from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from statsmodels.stats.diagnostic import acorr_ljungbox, breaks_cusumolsresid, het_arch
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.stattools import acf, pacf

ROOT = Path("/home/ubuntu/quant_automotivo_streamlit")
sys.path.insert(0, str(ROOT / "src"))

import analysis  # noqa: E402

N_FOLDS = 4
FOLD_SIZE = 6
LB_LAGS = [6, 12]
ARCH_LAGS = [4, 12]
LB_ALPHA = 0.05
LAG_SPECS = {
    "current_lag1_lag12": [1, 12],
    "lag1_only": [1],
    "joint_1_2_3_6_9_12": [1, 2, 3, 6, 9, 12],
    "joint_1_2_3_6_12": [1, 2, 3, 6, 12],
    "lag1_lag6_lag12": [1, 6, 12],
    "lag1_lag3_lag6_lag12": [1, 3, 6, 12],
}


def load_market() -> pd.DataFrame:
    raw = pd.read_csv(ROOT / "data" / "TOTALSA_snapshot.csv")
    data, _ = analysis.prepare_data(raw)
    return data


def build_features(data: pd.DataFrame, lags: list[int]) -> tuple[pd.DataFrame, list[str]]:
    features = data.copy()
    columns = []
    for lag in lags:
        column = f"lag_{lag}"
        features[column] = features["vendas_saar_milhoes"].shift(lag)
        columns.append(column)
    features["tendencia"] = np.arange(len(features))
    dummies = pd.get_dummies(features["mes"], prefix="mes", drop_first=True).astype(float)
    for month in range(2, 13):
        column = f"mes_{month}"
        if column not in dummies.columns:
            dummies[column] = 0.0
    features = pd.concat([features, dummies], axis=1)
    columns.extend(["tendencia", *[f"mes_{month}" for month in range(2, 13)]])
    return features, columns


def fit_predict_fold(train: pd.DataFrame, test: pd.DataFrame, lags: list[int]) -> dict[str, Any]:
    train_features, columns = build_features(train, lags)
    usable = train_features.dropna(subset=[*columns, "vendas_saar_milhoes"])
    model = Ridge(alpha=analysis.FORECAST_DEFAULTS.ridge_alpha).fit(usable[columns], usable["vendas_saar_milhoes"])
    train_prediction = model.predict(usable[columns])
    train_residuals = usable["vendas_saar_milhoes"].to_numpy(dtype=float) - train_prediction
    history = train[["data", "vendas_saar_milhoes", "mes"]].copy()
    predictions: list[float] = []
    for _ in range(len(test)):
        next_date = history["data"].max() + pd.offsets.MonthBegin(1)
        row: dict[str, float] = {f"lag_{lag}": float(history["vendas_saar_milhoes"].iloc[-lag]) for lag in lags}
        row["tendencia"] = float(len(history))
        row.update({f"mes_{month}": float(next_date.month == month) for month in range(2, 13)})
        prediction = float(model.predict(pd.DataFrame([row])[columns])[0])
        predictions.append(prediction)
        history = pd.concat(
            [
                history,
                pd.DataFrame({"data": [next_date], "vendas_saar_milhoes": [prediction], "mes": [next_date.month]}),
            ],
            ignore_index=True,
        )
    actual = test["vendas_saar_milhoes"].to_numpy(dtype=float)
    predicted = np.asarray(predictions, dtype=float)
    return {
        "actual": actual,
        "predicted": predicted,
        "oos_errors": actual - predicted,
        "train_residuals": train_residuals,
        "train_end": str(train["data"].max()),
        "test_start": str(test["data"].min()),
        "test_end": str(test["data"].max()),
        "n_train_residuals": len(train_residuals),
        "n_features": len(columns),
    }


def safe_acf(values: np.ndarray, n_lags: int) -> list[float]:
    return [float(value) for value in acf(values, nlags=min(n_lags, len(values) - 1), fft=False)]


def safe_pacf(values: np.ndarray, n_lags: int) -> list[float]:
    return [float(value) for value in pacf(values, nlags=min(n_lags, max(1, len(values) // 2 - 1)), method="ywm")]


def ljung_box(values: np.ndarray, lags: list[int]) -> dict[str, dict[str, float | None]]:
    valid_lags = [lag for lag in lags if lag < len(values)]
    if not valid_lags:
        return {}
    table = acorr_ljungbox(values, lags=valid_lags, return_df=True)
    return {
        str(lag): {
            "statistic": float(table.loc[lag, "lb_stat"]),
            "pvalue": float(table.loc[lag, "lb_pvalue"]),
        }
        for lag in valid_lags
    }


def arch_test(values: np.ndarray, lags: list[int]) -> dict[str, dict[str, float | None]]:
    output: dict[str, dict[str, float | None]] = {}
    for lag in lags:
        try:
            statistic, pvalue, _, _ = het_arch(values, nlags=lag)
            output[str(lag)] = {"statistic": float(statistic), "pvalue": float(pvalue)}
        except Exception:
            output[str(lag)] = {"statistic": None, "pvalue": None}
    return output


def cusum(values: np.ndarray, n_features: int) -> dict[str, float | None]:
    try:
        statistic, pvalue, critical = breaks_cusumolsresid(values, ddof=n_features + 1)
        return {
            "statistic": float(statistic),
            "pvalue": float(pvalue),
            "critical_5pct": float(critical[1][1]) if len(critical) > 1 else None,
        }
    except Exception:
        return {"statistic": None, "pvalue": None, "critical_5pct": None}


def horizon_metrics(matrix: pd.DataFrame, folds: list[dict[str, Any]]) -> list[dict[str, float | int]]:
    start_test = len(matrix) - N_FOLDS * FOLD_SIZE
    rows: list[dict[str, float | int]] = []
    for horizon in range(FOLD_SIZE):
        per_fold: list[dict[str, float]] = []
        for fold, result in enumerate(folds):
            train_end = start_test + fold * FOLD_SIZE
            per_fold.append(
                analysis.metricas(
                    result["actual"][horizon : horizon + 1],
                    result["predicted"][horizon : horizon + 1],
                    matrix["vendas_saar_milhoes"].to_numpy(dtype=float)[:train_end],
                )
            )
        rows.append(
            {
                "horizon": horizon + 1,
                "mae": float(np.mean([row["MAE (milhões SAAR)"] for row in per_fold])),
                "rmse": float(np.mean([row["RMSE (milhões SAAR)"] for row in per_fold])),
                "mape": float(np.mean([row["MAPE (%)"] for row in per_fold])),
                "wape": float(np.mean([row["WAPE (%)"] for row in per_fold])),
                "smape": float(np.mean([row["sMAPE (%)"] for row in per_fold])),
                "mase": float(np.mean([row["MASE"] for row in per_fold])),
            }
        )
    return rows


def diagnose_spec(data: pd.DataFrame, lag_name: str, lags: list[int]) -> dict[str, Any]:
    folds: list[dict[str, Any]] = []
    fold_slices = analysis.construir_dobras(data, N_FOLDS, FOLD_SIZE)
    for fold_number, (train_slice, test_slice) in enumerate(fold_slices, start=1):
        train = data.iloc[train_slice].reset_index(drop=True)
        test = data.iloc[test_slice].reset_index(drop=True)
        result = fit_predict_fold(train, test, lags)
        oos = result["oos_errors"]
        train_residuals = result["train_residuals"]
        fold_metrics = analysis.metricas(result["actual"], result["predicted"], train["vendas_saar_milhoes"].to_numpy())
        folds.append(
            {
                "fold": fold_number,
                "periodo_oos": f"{test['data'].min():%m/%Y}–{test['data'].max():%m/%Y}",
                "train_end": result["train_end"],
                "test_start": result["test_start"],
                "test_end": result["test_end"],
                "mape": fold_metrics["MAPE (%)"],
                "mae": fold_metrics["MAE (milhões SAAR)"],
                "rmse": fold_metrics["RMSE (milhões SAAR)"],
                "wape": fold_metrics["WAPE (%)"],
                "smape": fold_metrics["sMAPE (%)"],
                "mase": fold_metrics["MASE"],
                "dw_oos": float(durbin_watson(oos)),
                "dw_oos_centered": float(durbin_watson(oos - np.mean(oos))),
                "mean_oos_error": float(np.mean(oos)),
                "acf_oos": safe_acf(oos, 3),
                "pacf_oos": safe_pacf(oos, 2),
                "ljung_box_oos": ljung_box(oos, [3]),
                "train_residual_acf": safe_acf(train_residuals, 12),
                "train_residual_pacf": safe_pacf(train_residuals, 12),
                "ljung_box_train": ljung_box(train_residuals, LB_LAGS),
                "arch_train": arch_test(train_residuals, ARCH_LAGS),
                "cusum_train_proxy": cusum(train_residuals, result["n_features"]),
                "n_train_residuals": result["n_train_residuals"],
                "oos_errors": [float(value) for value in oos],
            }
        )
    # Recover actuals and predictions through a second deterministic pass for the prequential interval score.
    actuals_by_fold: list[np.ndarray] = []
    predictions_by_fold: list[np.ndarray] = []
    for train_slice, test_slice in fold_slices:
        result = fit_predict_fold(
            data.iloc[train_slice].reset_index(drop=True), data.iloc[test_slice].reset_index(drop=True), lags
        )
        actuals_by_fold.append(result["actual"])
        predictions_by_fold.append(result["predicted"])
    grouped_errors = np.concatenate(
        [actual - predicted for actual, predicted in zip(actuals_by_fold, predictions_by_fold, strict=True)]
    )
    grouped_lb = ljung_box(grouped_errors, LB_LAGS)
    fixed_intervals = analysis.prequential_interval_quality(actuals_by_fold, predictions_by_fold)
    volatility_intervals = analysis.prequential_interval_quality_volatility(actuals_by_fold, predictions_by_fold)
    overall = analysis.metricas(
        np.concatenate(actuals_by_fold),
        np.concatenate(predictions_by_fold),
        data["vendas_saar_milhoes"].to_numpy(dtype=float)[: len(data) - N_FOLDS * FOLD_SIZE],
    )
    summary = {
        "lag_name": lag_name,
        "lags": lags,
        "n_folds": N_FOLDS,
        "fold_size": FOLD_SIZE,
        "n_oos_residuals": len(grouped_errors),
        "overall_metrics": overall,
        "folds": folds,
        "horizon_metrics": horizon_metrics(
            data,
            [
                {"actual": actual, "predicted": predicted}
                for actual, predicted in zip(actuals_by_fold, predictions_by_fold, strict=True)
            ],
        ),
        "grouped_oos_ljung_box": grouped_lb,
        "grouped_oos_dw_descriptive": float(durbin_watson(grouped_errors)),
        "grouped_oos_mean_error": float(np.mean(grouped_errors)),
        "prequential_interval_fixed": fixed_intervals,
        "prequential_interval_volatility": volatility_intervals,
        "acceptance_diagnostics": {
            "ljung_box_lag6": grouped_lb.get("6", {}).get("pvalue", np.nan) >= LB_ALPHA,
            "ljung_box_lag12": grouped_lb.get("12", {}).get("pvalue", np.nan) >= LB_ALPHA,
            "coverage_fixed_80pct": fixed_intervals["coverage_p10_p90"] >= 0.80,
            "mape_2_87pct": overall["MAPE (%)"] <= 2.87,
        },
    }
    return summary


def main() -> None:
    data = load_market()
    operational_backtest = analysis.run_backtest(data, n_dobras=N_FOLDS, tamanho_dobra=FOLD_SIZE)
    output = {
        "protocol": {
            "source": "data/TOTALSA_snapshot.csv real versionado",
            "n_folds": N_FOLDS,
            "fold_size_months": FOLD_SIZE,
            "selection_metrics": ["RMSE", "MAE", "WAPE", "sMAPE", "MASE", "MAPE", "coverage_p10_p90", "Pinball Loss"],
            "in_sample_r2_used": False,
            "ljung_box_grouped_lags": LB_LAGS,
            "arch_lags": ARCH_LAGS,
            "alpha": LB_ALPHA,
            "operational_model": "Regressão com defasagens (Ridge alpha=1; lag_1 e lag_12; dummies mensais; tendência)",
        },
        "benchmark_context": {
            "winner": operational_backtest["winner"],
            "summary": operational_backtest["summary"].to_dict(orient="records"),
            "operational_prequential_interval_quality": operational_backtest["prequential_interval_quality"],
            "operational_prequential_interval_quality_volatility": operational_backtest[
                "prequential_interval_quality_volatility"
            ],
            "operational_residual_diagnostics": {
                "ljung_box": operational_backtest["ljung_box"].to_dict(orient="records"),
                "arch": operational_backtest["residual_diagnostics"]["arch"],
                "durbin_watson": operational_backtest["residual_diagnostics"]["durbin_watson"],
            },
        },
        "specifications": [diagnose_spec(data, name, lags) for name, lags in LAG_SPECS.items()],
    }
    path = ROOT / "data" / "model_artifacts" / "operational_lagged_regression_diagnostics.json"
    path.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.item() if hasattr(value, "item") else value,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.item() if hasattr(value, "item") else value,
        )
    )


if __name__ == "__main__":
    main()
