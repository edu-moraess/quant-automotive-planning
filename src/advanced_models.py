"""Modelos integrados de mercado/energia e eficiência de produto.

Os resultados são treinados em snapshots públicos versionados. A separação temporal
impede que configurações recentes ou meses futuros apareçam no treinamento.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson, jarque_bera

MARKET_TARGET = "vendas_saar_milhoes"
ENERGY_FEATURES = ["gasolina_usd_gal", "diesel_usd_gal", "eletricidade_usd_kwh"]
NEURAL_NUMERIC_FEATURES = ["year", "cylinders", "displ"]
NEURAL_CATEGORICAL_FEATURES = ["VClass", "fuelType1", "atvType", "trany", "drive", "tCharger", "sCharger", "startStop"]


def _metrics(actual: pd.Series | np.ndarray, predicted: pd.Series | np.ndarray) -> dict[str, float]:
    actual_array = np.asarray(actual, dtype=float)
    predicted_array = np.asarray(predicted, dtype=float)
    return {
        "mae": float(mean_absolute_error(actual_array, predicted_array)),
        "rmse": float(mean_squared_error(actual_array, predicted_array) ** 0.5),
        "r2": float(r2_score(actual_array, predicted_array)),
        "observacoes": int(len(actual_array)),
    }


def prepare_econometric_frame(market_data: pd.DataFrame, energy_prices: pd.DataFrame) -> pd.DataFrame:
    """Harmoniza mercado mensal, energia e variáveis defasadas em período comum."""
    market = market_data[["data", MARKET_TARGET]].copy()
    market["data"] = pd.to_datetime(market["data"])
    energy = energy_prices[["data", *ENERGY_FEATURES]].copy()
    energy["data"] = pd.to_datetime(energy["data"])
    frame = market.merge(energy, on="data", how="inner").sort_values("data").reset_index(drop=True)
    frame["lag_1"] = frame[MARKET_TARGET].shift(1)
    frame["lag_12"] = frame[MARKET_TARGET].shift(12)
    frame["tendencia"] = np.arange(len(frame), dtype=float)
    frame["mes"] = frame["data"].dt.month.astype(str)
    dummies = pd.get_dummies(frame["mes"], prefix="mes", drop_first=True, dtype=float)
    frame = pd.concat([frame, dummies], axis=1).dropna().reset_index(drop=True)
    return frame


def fit_econometric_energy_model(
    market_data: pd.DataFrame, energy_prices: pd.DataFrame, holdout_months: int = 24
) -> dict[str, Any]:
    """Estima OLS padronizado e avalia os últimos meses sem reordenar o tempo."""
    frame = prepare_econometric_frame(market_data, energy_prices)
    if len(frame) <= holdout_months + 36:
        raise ValueError("A sobreposição entre mercado e energia é insuficiente para a validação temporal.")
    train = frame.iloc[:-holdout_months].copy()
    test = frame.iloc[-holdout_months:].copy()
    dummy_features = [column for column in frame.columns if column.startswith("mes_")]
    continuous_features = ["lag_1", "lag_12", "tendencia", *ENERGY_FEATURES]
    feature_columns = [*continuous_features, *dummy_features]
    scaler = StandardScaler()
    train_scaled = train.copy()
    test_scaled = test.copy()
    train_scaled[continuous_features] = scaler.fit_transform(train[continuous_features])
    test_scaled[continuous_features] = scaler.transform(test[continuous_features])
    x_train = sm.add_constant(train_scaled[feature_columns], has_constant="add")
    x_test = sm.add_constant(test_scaled[feature_columns], has_constant="add")
    fitted = sm.OLS(train[MARKET_TARGET], x_train).fit()
    predictions = fitted.predict(x_test)
    coefficients = pd.DataFrame(
        {
            "variavel": fitted.params.index,
            "coeficiente_padronizado": fitted.params.values,
            "p_valor": fitted.pvalues.values,
        }
    )
    coefficients["abs_coeficiente"] = coefficients["coeficiente_padronizado"].abs()
    coefficients = (
        coefficients.sort_values("abs_coeficiente", ascending=False)
        .drop(columns="abs_coeficiente")
        .reset_index(drop=True)
    )
    validation = test[["data", MARKET_TARGET, *ENERGY_FEATURES]].copy()
    validation["previsto_ols"] = predictions.to_numpy()
    metrics = _metrics(test[MARKET_TARGET], predictions)
    metrics.update(
        {
            "r2_treino": float(fitted.rsquared),
            "inicio_treino": train["data"].min().strftime("%Y-%m"),
            "fim_treino": train["data"].max().strftime("%Y-%m"),
            "inicio_teste": test["data"].min().strftime("%Y-%m"),
            "fim_teste": test["data"].max().strftime("%Y-%m"),
            "variaveis": int(len(feature_columns)),
        }
    )
    diagnostics = _econometric_diagnostics(fitted, x_train)
    return {
        "metrics": metrics,
        "coefficients": coefficients,
        "validation": validation,
        "frame": frame,
        "diagnostics": diagnostics,
    }


def _econometric_diagnostics(fitted: Any, x_train: pd.DataFrame) -> dict[str, Any]:
    residuals = np.asarray(fitted.resid, dtype=float)
    jb = jarque_bera(residuals)
    bp = het_breuschpagan(residuals, x_train)
    vif_rows: list[dict[str, float | str]] = []
    values = x_train.to_numpy(dtype=float)
    for index, column in enumerate(x_train.columns):
        if column == "const":
            continue
        try:
            vif = float(variance_inflation_factor(values, index))
        except Exception:
            vif = float("inf")
        vif_rows.append({"variavel": column, "vif": vif})
    return {
        "durbin_watson": float(durbin_watson(residuals)),
        "jarque_bera": {"statistic": float(jb[0]), "pvalue": float(jb[1])},
        "breusch_pagan": {"statistic": float(bp[0]), "pvalue": float(bp[1])},
        "vif": pd.DataFrame(vif_rows).sort_values("vif", ascending=False).reset_index(drop=True),
    }


def _neural_preprocessor() -> ColumnTransformer:
    numeric_pipeline = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    categorical_pipeline = Pipeline(
        [("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric_pipeline, NEURAL_NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, NEURAL_CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


def fit_efficiency_neural_model(vehicle_data: pd.DataFrame, cutoff_year: int = 2024) -> dict[str, Any]:
    """Treina MLP de eficiência usando separação de ano-modelo, sem vazamento do alvo."""
    features = [*NEURAL_NUMERIC_FEATURES, *NEURAL_CATEGORICAL_FEATURES]
    required = list(dict.fromkeys(["id", "make", "model", "year", "comb08", "powertrain", *features]))
    frame = vehicle_data[required].copy()
    frame["comb08"] = pd.to_numeric(frame["comb08"], errors="coerce")
    frame = frame.dropna(subset=["year", "comb08"])
    frame = frame.loc[frame["comb08"].gt(0)].reset_index(drop=True)
    train = frame.loc[frame["year"] <= cutoff_year].copy()
    test = frame.loc[frame["year"] > cutoff_year].copy()
    if train.empty or test.empty:
        raise ValueError("A divisão temporal da rede neural não produziu treinamento e teste válidos.")
    estimator = Pipeline(
        [
            ("preprocessor", _neural_preprocessor()),
            (
                "model",
                MLPRegressor(
                    hidden_layer_sizes=(64, 32),
                    activation="relu",
                    solver="adam",
                    alpha=0.0005,
                    learning_rate_init=0.001,
                    early_stopping=True,
                    validation_fraction=0.12,
                    n_iter_no_change=15,
                    max_iter=220,
                    random_state=42,
                ),
            ),
        ]
    )
    estimator.fit(train[features], train["comb08"])
    predicted = estimator.predict(test[features])
    validation = test[["id", "make", "model", "year", "powertrain", "VClass", "fuelType1", "comb08"]].copy()
    validation["previsto_mlp"] = predicted
    validation["erro_abs"] = (validation["comb08"] - validation["previsto_mlp"]).abs()
    permutation = permutation_importance(
        estimator,
        test[features],
        test["comb08"],
        scoring="neg_mean_absolute_error",
        n_repeats=8,
        random_state=42,
        n_jobs=1,
    )
    importance = (
        pd.DataFrame(
            {
                "variavel": features,
                "incremento_mae_permutacao": permutation.importances_mean,
                "desvio_mae_permutacao": permutation.importances_std,
            }
        )
        .sort_values("incremento_mae_permutacao", ascending=False)
        .reset_index(drop=True)
    )
    error_by_powertrain = (
        validation.groupby("powertrain", as_index=False)
        .agg(configuracoes=("id", "count"), mae=("erro_abs", "mean"), mediana_erro=("erro_abs", "median"))
        .sort_values("mae", ascending=False)
        .reset_index(drop=True)
    )
    metrics = _metrics(test["comb08"], predicted)
    metrics.update(
        {
            "inicio_treino": int(train["year"].min()),
            "fim_treino": int(train["year"].max()),
            "inicio_teste": int(test["year"].min()),
            "fim_teste": int(test["year"].max()),
            "variaveis_numericas": len(NEURAL_NUMERIC_FEATURES),
            "variaveis_categoricas": len(NEURAL_CATEGORICAL_FEATURES),
            "iteracoes": int(estimator.named_steps["model"].n_iter_),
        }
    )
    return {
        "metrics": metrics,
        "validation": validation,
        "importance": importance,
        "error_by_powertrain": error_by_powertrain,
        "estimator": estimator,
        "training_rows": len(train),
        "test_rows": len(test),
    }


def save_advanced_results(output_dir: str | Path, econometric: dict[str, Any], neural: dict[str, Any]) -> None:
    """Persiste métricas, coeficientes e previsões para leitura rápida na interface."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary = {
        "econometria_energia": econometric["metrics"],
        "rede_neural_eficiencia": neural["metrics"],
        "amostras": {
            "econometria_total": int(len(econometric["frame"])),
            "neural_treino": int(neural["training_rows"]),
            "neural_teste": int(neural["test_rows"]),
        },
    }
    (destination / "advanced_model_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    econometric["coefficients"].to_csv(destination / "econometric_coefficients.csv", index=False)
    econometric["validation"].to_csv(destination / "econometric_validation.csv", index=False)
    econometric["diagnostics"]["vif"].to_csv(destination / "econometric_vif.csv", index=False)
    neural["validation"].to_csv(destination / "neural_efficiency_validation.csv", index=False)
    neural["importance"].to_csv(destination / "neural_permutation_importance.csv", index=False)
    neural["error_by_powertrain"].to_csv(destination / "neural_error_by_powertrain.csv", index=False)
