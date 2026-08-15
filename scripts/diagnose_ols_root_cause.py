from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox, breaks_cusumolsresid, het_arch
from statsmodels.tsa.stattools import acf, pacf

ROOT = Path("/home/ubuntu/quant_automotivo_streamlit")
sys.path.insert(0, str(ROOT / "src"))

import forecast_model as fm  # noqa: E402


def safe_acf(values: np.ndarray, max_lag: int) -> list[float]:
    if len(values) < 4:
        return []
    lag = min(max_lag, len(values) - 1)
    return [round(float(value), 6) for value in acf(values, nlags=lag, fft=False)]


def safe_pacf(values: np.ndarray, max_lag: int) -> list[float]:
    if len(values) < 6:
        return []
    lag = min(max_lag, max(1, len(values) // 2 - 1))
    return [round(float(value), 6) for value in pacf(values, nlags=lag, method="ywm")]


def fit_folds(matrix: pd.DataFrame, estimator: str) -> dict[str, object]:
    n = len(matrix)
    start_test = n - fm._N_FOLDS * fm._FOLD_SIZE
    feature_cols = [column for column in matrix.columns if column != "y"]
    x_all = matrix[feature_cols].to_numpy(dtype=float)
    y_all = matrix["y"].to_numpy(dtype=float)
    fold_rows: list[dict[str, object]] = []
    all_oos_errors: list[np.ndarray] = []
    for fold in range(fm._N_FOLDS):
        train_end = start_test + fold * fm._FOLD_SIZE
        test_end = train_end + fm._FOLD_SIZE
        x_train, y_train = x_all[:train_end], y_all[:train_end]
        x_test, y_test = x_all[train_end:test_end], y_all[train_end:test_end]
        maxlags = max(1, int(np.floor(4 * (len(y_train) / 100) ** (2 / 9))))
        fitted = fm._fit_estimator(y_train, x_train, estimator=estimator, maxlags=maxlags)
        train_pred = fitted.predict(fm.sm.add_constant(x_train, has_constant="add"))
        test_pred = fitted.predict(fm.sm.add_constant(x_test, has_constant="add"))
        train_residuals = y_train - train_pred
        oos_errors = y_test - test_pred
        fold_date_index = matrix.index[train_end:test_end]
        row: dict[str, object] = {
            "fold": fold + 1,
            "train_start": matrix.index[0].strftime("%Y-%m"),
            "train_end": matrix.index[train_end - 1].strftime("%Y-%m"),
            "test_start": fold_date_index[0].strftime("%Y-%m"),
            "test_end": fold_date_index[-1].strftime("%Y-%m"),
            "n_train": len(y_train),
            "n_test": len(y_test),
            "mean_oos_error": float(np.mean(oos_errors)),
            "dw_oos": float(fm.durbin_watson(oos_errors)),
            "dw_oos_centered": float(fm.durbin_watson(oos_errors - np.mean(oos_errors))),
            "oos_errors": [round(float(value), 8) for value in oos_errors],
            "acf_oos": safe_acf(oos_errors, 3),
            "pacf_oos": safe_pacf(oos_errors, 2),
            "acf_train_residuals": safe_acf(train_residuals, 12),
            "pacf_train_residuals": safe_pacf(train_residuals, 12),
            "ljung_box_train_pvalue_lag12": float(
                acorr_ljungbox(train_residuals, lags=[12], return_df=True)["lb_pvalue"].iloc[0]
            ),
            "arch_train_pvalue_lag12": float(het_arch(train_residuals, nlags=12)[1]),
        }
        try:
            cusum_stat, cusum_pvalue, cusum_critical = breaks_cusumolsresid(fitted.resid, ddof=int(fitted.df_model) + 1)
            row["cusum_stat"] = float(cusum_stat)
            row["cusum_pvalue"] = float(cusum_pvalue)
            row["cusum_critical_5pct"] = float(cusum_critical[1][1])
        except Exception as error:
            row["cusum_error"] = str(error)
        all_oos_errors.append(oos_errors)
        fold_rows.append(row)
    grouped_errors = np.concatenate(all_oos_errors)
    grouped_lb = acorr_ljungbox(grouped_errors, lags=[fm.GROUPED_OOS_LB_LAG], return_df=True)
    return {
        "estimator": estimator,
        "folds": fold_rows,
        "dw_mean": float(np.mean([row["dw_oos"] for row in fold_rows])),
        "ljung_box_oos_grouped_lag": fm.GROUPED_OOS_LB_LAG,
        "ljung_box_oos_grouped_stat": float(grouped_lb["lb_stat"].iloc[0]),
        "ljung_box_oos_grouped_pvalue": float(grouped_lb["lb_pvalue"].iloc[0]),
        "n_oos_residuals": int(len(grouped_errors)),
    }


def compare_hac_to_classic(matrix: pd.DataFrame) -> dict[str, float]:
    n = len(matrix)
    start_test = n - fm._N_FOLDS * fm._FOLD_SIZE
    feature_cols = [column for column in matrix.columns if column != "y"]
    x_train = matrix[feature_cols].to_numpy(dtype=float)[:start_test]
    y_train = matrix["y"].to_numpy(dtype=float)[:start_test]
    x_const = fm.sm.add_constant(x_train, has_constant="add")
    classic = fm.sm.OLS(y_train, x_const).fit()
    hac = fm.sm.OLS(y_train, x_const).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": max(1, int(np.floor(4 * (len(y_train) / 100) ** (2 / 9)))), "use_correction": True},
    )
    return {
        "max_abs_param_difference": float(np.max(np.abs(classic.params - hac.params))),
        "max_abs_residual_difference": float(np.max(np.abs(classic.resid - hac.resid))),
        "dw_classic": float(fm.durbin_watson(classic.resid)),
        "dw_hac": float(fm.durbin_watson(hac.resid)),
        "classic_se_mean": float(np.mean(classic.bse)),
        "hac_se_mean": float(np.mean(hac.bse)),
    }


def main() -> None:
    matrix = fm.build_regression_matrix()
    seasonal = matrix.copy()
    seasonal["y_lag12"] = seasonal["y"].shift(12)
    seasonal = seasonal.dropna()
    target_acf = safe_acf(matrix["y"].to_numpy(dtype=float), 24)
    result = {
        "base_matrix": {
            "rows": len(matrix),
            "start": matrix.index.min().strftime("%Y-%m"),
            "end": matrix.index.max().strftime("%Y-%m"),
            "columns": list(matrix.columns),
            "target_acf_lag1": target_acf[1] if len(target_acf) > 1 else None,
            "target_acf_lag6": target_acf[6] if len(target_acf) > 6 else None,
            "target_acf_lag12": target_acf[12] if len(target_acf) > 12 else None,
        },
        "ols_newey_west": fit_folds(matrix, "newey_west"),
        "glsar": fit_folds(matrix, "glsar"),
        "ols_with_y_lag12": fit_folds(seasonal, "newey_west"),
        "glsar_with_y_lag12": fit_folds(seasonal, "glsar"),
        "hac_vs_classic_first_fold_train": compare_hac_to_classic(matrix),
    }
    output = ROOT / "data" / "model_artifacts" / "ols_root_cause_diagnostics.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
