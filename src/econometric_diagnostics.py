"""Diagnósticos econométricos consolidados para validação fora da amostra."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import jarque_bera, kurtosis, norm, skew
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.stattools import acf, pacf


def diagnose_residuals(
    residuals: np.ndarray | pd.Series,
    *,
    design_matrix: pd.DataFrame | np.ndarray | None = None,
    max_lag: int = 12,
) -> dict[str, Any]:
    """Calcula autocorrelação, heterocedasticidade, normalidade e multicolinearidade."""
    values = np.asarray(residuals, dtype=float)
    if values.ndim != 1 or len(values) < 8 or not np.isfinite(values).all():
        raise ValueError("Diagnósticos exigem pelo menos 8 resíduos finitos em vetor unidimensional.")
    lag_limit = min(max(int(max_lag), 1), max(1, len(values) // 2 - 1))
    acf_values = acf(values, nlags=lag_limit, fft=True)
    pacf_values = pacf(values, nlags=lag_limit, method="ywm")
    ljung = acorr_ljungbox(values, lags=list(range(1, lag_limit + 1)), return_df=True).reset_index()
    ljung = ljung.rename(columns={"index": "lag", "lb_stat": "statistic", "lb_pvalue": "pvalue"})

    jb = jarque_bera(values)
    arch = het_arch(values, nlags=min(lag_limit, max(1, len(values) // 5)))
    diagnostics: dict[str, Any] = {
        "durbin_watson": float(durbin_watson(values)),
        "ljung_box": ljung,
        "acf": pd.DataFrame({"lag": np.arange(len(acf_values)), "acf": acf_values}),
        "pacf": pd.DataFrame({"lag": np.arange(len(pacf_values)), "pacf": pacf_values}),
        "jarque_bera": {"statistic": float(jb.statistic), "pvalue": float(jb.pvalue)},
        "skewness": float(skew(values, bias=False)),
        "kurtosis_excess": float(kurtosis(values, fisher=True, bias=False)),
        "arch": {"statistic": float(arch[0]), "pvalue": float(arch[1])},
        "qq": _qq_frame(values),
    }

    if design_matrix is not None:
        design = _numeric_design(design_matrix)
        if len(design) != len(values):
            raise ValueError("A matriz de desenho deve ter o mesmo número de linhas dos resíduos.")
        diagnostics["vif"] = _vif_table(design)
        if design.shape[1] >= 2:
            exog = np.column_stack([np.ones(len(design)), design])
            bp = het_breuschpagan(values, exog)
            diagnostics["breusch_pagan"] = {"statistic": float(bp[0]), "pvalue": float(bp[1])}
        else:
            diagnostics["breusch_pagan"] = {"statistic": None, "pvalue": None}
    else:
        diagnostics["vif"] = pd.DataFrame(columns=["variavel", "vif"])
        diagnostics["breusch_pagan"] = {"statistic": None, "pvalue": None}
    return diagnostics


def _numeric_design(design_matrix: pd.DataFrame | np.ndarray) -> pd.DataFrame:
    if isinstance(design_matrix, pd.DataFrame):
        frame = design_matrix.copy()
    else:
        array = np.asarray(design_matrix, dtype=float)
        if array.ndim != 2:
            raise ValueError("A matriz de desenho deve ser bidimensional.")
        frame = pd.DataFrame(array, columns=[f"x_{index}" for index in range(array.shape[1])])
    frame = frame.apply(pd.to_numeric, errors="coerce")
    if frame.empty or frame.isna().any().any() or not np.isfinite(frame.to_numpy()).all():
        raise ValueError("A matriz de desenho deve conter somente valores numéricos finitos.")
    return frame


def _vif_table(design: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    values = design.to_numpy(dtype=float)
    for index, column in enumerate(design.columns):
        try:
            value = float(variance_inflation_factor(values, index))
        except Exception:
            value = float("inf")
        rows.append({"variavel": str(column), "vif": value})
    return pd.DataFrame(rows).sort_values("vif", ascending=False).reset_index(drop=True)


def _qq_frame(values: np.ndarray) -> pd.DataFrame:
    ordered = np.sort(values)
    probabilities = (np.arange(1, len(ordered) + 1) - 0.5) / len(ordered)
    return pd.DataFrame({"quantil_teorico": norm.ppf(probabilities), "residuo_ordenado": ordered})
