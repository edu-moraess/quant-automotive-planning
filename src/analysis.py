"""Motor de mercado, forecast probabilístico e planejamento operacional.

O módulo não depende de Streamlit: pode ser testado, executado por scripts e usado
pela interface apenas como camada de cálculo. Forecasts são validados em ordem
temporal e a incerteza é construída a partir de erros fora da amostra.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.stats.stattools import durbin_watson, jarque_bera
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import acf, adfuller, kpss, pacf

from config import FORECAST_DEFAULTS, SOURCES, PlanningAssumptions
from ingestion import load_csv_with_fallback
from planning import build_scenario_table, build_sensitivity, decision_brief, demand_from_saar, solve_production_plan

FRED_CSV_URL = SOURCES.fred_market_url
FRED_SERIES_URL = "https://fred.stlouisfed.org/series/TOTALSA"
MODEL_NAMES = ["Referência sazonal", "Holt-Winters", "Regressão com defasagens", "AutoReg sazonal"]
MODEL_COMPLEXITY = {
    "Referência sazonal": 1,
    "Holt-Winters": 2,
    "Regressão com defasagens": 3,
    "AutoReg sazonal": 3,
}
MONTH_NAMES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
REGRESSION_COLUMNS = ["lag_1", "lag_12", "tendencia", *[f"mes_{month}" for month in range(2, 13)]]


def read_fred_with_provenance(
    source: str = FRED_CSV_URL,
    fallback_path: str | Path | None = None,
    allow_online: bool = True,
) -> tuple[pd.DataFrame, dict[str, str | None]]:
    """Lê TOTALSA e preserva a proveniência da fonte efetivamente usada."""
    if fallback_path is None:
        raise ValueError("Um snapshot local é obrigatório para a degradação controlada da fonte FRED.")
    result = load_csv_with_fallback(
        url=source,
        expected_columns=["observation_date", "TOTALSA"],
        source_name="FRED TOTALSA",
        snapshot_path=fallback_path,
        allow_online=allow_online,
        settings=SOURCES,
    )
    label = "FRED — fonte online" if result.source_status == "ONLINE" else "Snapshot local versionado"
    return result.frame, {
        "source_status": result.source_status,
        "source_label": label,
        "source_url": result.source_url,
        "retrieved_at_utc": result.retrieved_at_utc,
        "fallback_reason": result.fallback_reason,
    }


def read_fred_csv(
    source: str = FRED_CSV_URL,
    fallback_path: str | Path | None = None,
    allow_online: bool = True,
) -> tuple[pd.DataFrame, str]:
    """Compatibilidade: retorna série TOTALSA e rótulo legível da fonte."""
    frame, provenance = read_fred_with_provenance(source, fallback_path, allow_online)
    return frame, str(provenance["source_label"])


def market_refresh_summary(
    market_data: pd.DataFrame,
    snapshot_path: str | Path,
    provenance: dict[str, str | None],
) -> dict[str, str | int | None]:
    """Resume a atualização FRED comparando a série usada ao snapshot versionado."""
    snapshot_raw = pd.read_csv(snapshot_path)
    snapshot_data, _ = prepare_data(snapshot_raw)
    current = market_data[["data", "vendas_saar_milhoes"]].rename(columns={"vendas_saar_milhoes": "valor_atual"})
    snapshot = snapshot_data[["data", "vendas_saar_milhoes"]].rename(columns={"vendas_saar_milhoes": "valor_snapshot"})
    comparison = current.merge(snapshot, on="data", how="left")
    common = comparison.dropna(subset=["valor_snapshot"])
    revised = int(
        (
            ~np.isclose(common["valor_atual"].to_numpy(), common["valor_snapshot"].to_numpy(), rtol=1e-10, atol=1e-12)
        ).sum()
    )
    snapshot_end = snapshot_data["data"].max()
    current_end = market_data["data"].max()
    return {
        **provenance,
        "observations": int(len(market_data)),
        "data_start": market_data["data"].min().strftime("%Y-%m"),
        "data_end": current_end.strftime("%Y-%m"),
        "snapshot_observations": int(len(snapshot_data)),
        "snapshot_data_end": snapshot_end.strftime("%Y-%m"),
        "new_observations": int(comparison["valor_snapshot"].isna().sum()),
        "revised_observations": revised,
    }


def prepare_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Normaliza TOTALSA, preserva observações válidas e calcula qualidade descritiva."""
    required = {"observation_date", "TOTALSA"}
    if not required.issubset(raw.columns):
        raise ValueError(f"Formato inesperado. Colunas necessárias: {sorted(required)}")
    duplicate_count = int(raw["observation_date"].duplicated().sum())
    cleaned = (
        raw.rename(columns={"observation_date": "data", "TOTALSA": "vendas_saar_milhoes"})
        .assign(
            data=lambda frame: pd.to_datetime(frame["data"], errors="coerce").dt.to_period("M").dt.to_timestamp(),
            vendas_saar_milhoes=lambda frame: pd.to_numeric(frame["vendas_saar_milhoes"], errors="coerce"),
        )
        .dropna(subset=["data", "vendas_saar_milhoes"])
        .sort_values("data")
        .drop_duplicates("data", keep="last")
        .reset_index(drop=True)
    )
    cleaned["demanda_mensal_est_milhoes"] = cleaned["vendas_saar_milhoes"] / 12
    cleaned["mes"] = cleaned["data"].dt.month
    cleaned["ano"] = cleaned["data"].dt.year
    cleaned["variacao_mensal_pct"] = cleaned["vendas_saar_milhoes"].pct_change() * 100
    cleaned["variacao_anual_pct"] = cleaned["vendas_saar_milhoes"].pct_change(12) * 100
    expected = pd.date_range(cleaned["data"].min(), cleaned["data"].max(), freq="MS")
    missing_months = int(len(expected.difference(pd.DatetimeIndex(cleaned["data"]))))
    q1, q3 = cleaned["vendas_saar_milhoes"].quantile([0.25, 0.75])
    spread = q3 - q1
    lower, upper = q1 - 1.5 * spread, q3 + 1.5 * spread
    outliers = cleaned.loc[cleaned["vendas_saar_milhoes"].lt(lower) | cleaned["vendas_saar_milhoes"].gt(upper)].copy()
    quality = {
        "duplicidades_brutas": duplicate_count,
        "valores_ausentes": int(cleaned[["data", "vendas_saar_milhoes"]].isna().sum().sum()),
        "intervalos_irregulares": missing_months,
        "outliers_iqr": int(len(outliers)),
        "limite_iqr_inferior": float(lower),
        "limite_iqr_superior": float(upper),
        "observacoes": int(len(cleaned)),
        "data_inicial": cleaned["data"].min(),
        "data_final": cleaned["data"].max(),
        "outliers": outliers,
    }
    return cleaned, quality


def _test_result(test: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, float | None]:
    try:
        result = test(*args, **kwargs)
        return {"statistic": float(result[0]), "pvalue": float(result[1])}
    except Exception:
        return {"statistic": None, "pvalue": None}


def compute_diagnostics(data: pd.DataFrame) -> dict[str, Any]:
    """Calcula estacionariedade, decomposição, autocorrelação e normalidade da série."""
    series = data["vendas_saar_milhoes"].astype(float).dropna()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        adf_level = _test_result(adfuller, series, autolag="AIC")
        adf_diff = _test_result(adfuller, series.diff().dropna(), autolag="AIC")
        kpss_level = _test_result(kpss, series, regression="c", nlags="auto")
        stl_result = STL(data.set_index("data")["vendas_saar_milhoes"], period=12, robust=True).fit()
        max_lags = min(36, max(1, len(series) // 2 - 1))
        acf_values = acf(series, nlags=max_lags, fft=True)
        pacf_values = pacf(series, nlags=max_lags, method="ywm")
    seasonal_profile = (
        data.groupby("mes", as_index=False)["vendas_saar_milhoes"]
        .mean()
        .assign(nome_mes=lambda frame: frame["mes"].map(dict(enumerate(MONTH_NAMES, start=1))))
    )
    stl = pd.DataFrame(
        {
            "data": stl_result.observed.index,
            "observada": stl_result.observed.to_numpy(),
            "tendencia": stl_result.trend.to_numpy(),
            "sazonalidade": stl_result.seasonal.to_numpy(),
            "residuo": stl_result.resid.to_numpy(),
        }
    )
    return {
        "adf_level": adf_level,
        "adf_diff": adf_diff,
        "kpss_level": kpss_level,
        "stl": stl,
        "seasonal_profile": seasonal_profile,
        "acf": pd.DataFrame({"lag": np.arange(len(acf_values)), "acf": acf_values}),
        "pacf": pd.DataFrame({"lag": np.arange(len(pacf_values)), "pacf": pacf_values}),
    }


def metricas(y_real: np.ndarray, y_previsto: np.ndarray, insample: np.ndarray | None = None) -> dict[str, float]:
    """Calcula métricas de escala, percentuais e erro relativo para seleção temporal."""
    real = np.asarray(y_real, dtype=float)
    predicted = np.asarray(y_previsto, dtype=float)
    denominator = np.where(np.abs(real) < 1e-12, 1e-12, np.abs(real))
    smape_denominator = np.maximum(np.abs(real) + np.abs(predicted), 1e-12)
    metrics = {
        "MAE (milhões SAAR)": float(np.mean(np.abs(real - predicted))),
        "RMSE (milhões SAAR)": float(np.sqrt(np.mean((real - predicted) ** 2))),
        "MAPE (%)": float(np.mean(np.abs((real - predicted) / denominator)) * 100),
        "sMAPE (%)": float(np.mean(2 * np.abs(real - predicted) / smape_denominator) * 100),
        "WAPE (%)": float(np.sum(np.abs(real - predicted)) / np.maximum(np.sum(np.abs(real)), 1e-12) * 100),
    }
    if insample is not None:
        history = np.asarray(insample, dtype=float)
        naive_scale = np.mean(np.abs(np.diff(history))) if len(history) > 1 else np.nan
        metrics["MASE"] = float(metrics["MAE (milhões SAAR)"] / naive_scale) if naive_scale > 1e-12 else np.nan
    return metrics


def construir_dobras(data: pd.DataFrame, n_dobras: int = 4, tamanho_dobra: int = 6) -> list[tuple[slice, slice]]:
    """Gera dobras walk-forward expansivas, sem vazamento temporal."""
    if n_dobras < 1 or tamanho_dobra < 1:
        raise ValueError("O número e o tamanho das dobras devem ser positivos.")
    start_test = len(data) - n_dobras * tamanho_dobra
    if start_test < 24:
        raise ValueError("O histórico precisa ter pelo menos 24 observações antes do primeiro teste.")
    return [
        (
            slice(0, start_test + fold * tamanho_dobra),
            slice(start_test + fold * tamanho_dobra, start_test + (fold + 1) * tamanho_dobra),
        )
        for fold in range(n_dobras)
    ]


def prever_sazonal_naive(treino: pd.DataFrame, datas_teste: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    monthly_means = treino.groupby(treino["data"].dt.month)["vendas_saar_milhoes"].mean()
    fallback = float(treino["vendas_saar_milhoes"].mean())
    return np.asarray([monthly_means.get(date.month, fallback) for date in pd.to_datetime(datas_teste)], dtype=float)


def prever_holt_winters(treino: pd.DataFrame, n_periodos: int) -> np.ndarray:
    model = ExponentialSmoothing(
        treino["vendas_saar_milhoes"],
        trend="add",
        seasonal="add",
        seasonal_periods=12,
        initialization_method="estimated",
    ).fit(optimized=True)
    return np.asarray(model.forecast(n_periodos), dtype=float)


def construir_features_regressao(data: pd.DataFrame) -> pd.DataFrame:
    features = data.copy()
    features["lag_1"] = features["vendas_saar_milhoes"].shift(1)
    features["lag_12"] = features["vendas_saar_milhoes"].shift(12)
    features["tendencia"] = np.arange(len(features))
    dummies = pd.get_dummies(features["mes"], prefix="mes", drop_first=True).astype(float)
    return pd.concat([features, dummies], axis=1)


def prever_regressao_defasagens(treino: pd.DataFrame, n_periodos: int) -> np.ndarray:
    train_features = construir_features_regressao(treino).dropna(subset=[*REGRESSION_COLUMNS, "vendas_saar_milhoes"])
    model = Ridge(alpha=1.0).fit(train_features[REGRESSION_COLUMNS], train_features["vendas_saar_milhoes"])
    history = treino[["data", "vendas_saar_milhoes", "mes"]].copy()
    predictions: list[float] = []
    for _ in range(n_periodos):
        next_date = history["data"].max() + pd.offsets.MonthBegin(1)
        row = {
            "lag_1": history["vendas_saar_milhoes"].iloc[-1],
            "lag_12": history["vendas_saar_milhoes"].iloc[-12],
            "tendencia": len(history),
        }
        row.update({f"mes_{month}": float(next_date.month == month) for month in range(2, 13)})
        prediction = float(model.predict(pd.DataFrame([row])[REGRESSION_COLUMNS])[0])
        predictions.append(prediction)
        history = pd.concat(
            [
                history,
                pd.DataFrame({"data": [next_date], "vendas_saar_milhoes": [prediction], "mes": [next_date.month]}),
            ],
            ignore_index=True,
        )
    return np.asarray(predictions)


def prever_autoreg_sazonal(treino: pd.DataFrame, n_periodos: int) -> np.ndarray:
    """AutoReg com tendência e efeitos sazonais; adequado a uma série mensal curta."""
    series = treino["vendas_saar_milhoes"].astype(float).to_numpy()
    model = AutoReg(series, lags=12, trend="ct", seasonal=True, period=12, old_names=False).fit()
    return np.asarray(model.predict(start=len(series), end=len(series) + n_periodos - 1, dynamic=False), dtype=float)


def _model_predictions(treino: pd.DataFrame, test: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        "Referência sazonal": prever_sazonal_naive(treino, test["data"]),
        "Holt-Winters": prever_holt_winters(treino, len(test)),
        "Regressão com defasagens": prever_regressao_defasagens(treino, len(test)),
        "AutoReg sazonal": prever_autoreg_sazonal(treino, len(test)),
    }


def _select_model(summary: pd.DataFrame, tolerance_mape: float) -> str:
    ranked = summary.copy()
    for metric in ["mape_medio", "smape_medio", "wape_medio", "rmse_medio", "mape_desvio"]:
        ranked[f"rank_{metric}"] = ranked[metric].rank(method="min")
    rank_columns = [column for column in ranked if column.startswith("rank_")]
    ranked["selection_score"] = ranked[rank_columns].mean(axis=1)
    best_mape = float(ranked["mape_medio"].min())
    close = ranked.loc[ranked["mape_medio"] <= best_mape + tolerance_mape].copy()
    close["complexidade"] = close["modelo"].map(MODEL_COMPLEXITY)
    selected = close.sort_values(["selection_score", "complexidade", "mape_medio"]).iloc[0]
    summary["selection_score"] = ranked["selection_score"].to_numpy()
    return str(selected["modelo"])


def _residual_diagnostics(residuals: np.ndarray) -> dict[str, Any]:
    values = np.asarray(residuals, dtype=float)
    if len(values) < 4:
        return {
            "ljung_box": pd.DataFrame(),
            "residual_acf": pd.DataFrame(),
            "jarque_bera": {},
            "arch": {},
            "durbin_watson": np.nan,
        }
    lags = sorted({min(6, len(values) - 1), min(12, len(values) - 1)})
    ljung_box = acorr_ljungbox(values, lags=lags, return_df=True).reset_index(names="lag")
    residual_acf_values = acf(values, nlags=min(11, len(values) - 1), fft=True)
    jb = jarque_bera(values)
    try:
        arch = het_arch(values, nlags=min(4, max(1, len(values) // 4)))
        arch_result = {"statistic": float(arch[0]), "pvalue": float(arch[1])}
    except Exception:
        arch_result = {"statistic": None, "pvalue": None}
    return {
        "ljung_box": ljung_box,
        "residual_acf": pd.DataFrame({"lag": np.arange(len(residual_acf_values)), "acf": residual_acf_values}),
        "jarque_bera": {
            "statistic": float(jb[0]),
            "pvalue": float(jb[1]),
            "skew": float(jb[2]),
            "kurtosis": float(jb[3]),
        },
        "arch": arch_result,
        "durbin_watson": float(durbin_watson(values)),
    }


def _interval_quality(actual: np.ndarray, predicted: np.ndarray, residuals: np.ndarray) -> dict[str, float]:
    lower, upper = np.quantile(residuals, [0.10, 0.90])
    coverage = np.mean((actual >= predicted + lower) & (actual <= predicted + upper))
    losses = []
    for quantile in (0.10, 0.50, 0.90):
        error = actual - (predicted + np.quantile(residuals, quantile))
        losses.append(float(np.mean(np.maximum(quantile * error, (quantile - 1) * error))))
    return {"coverage_p10_p90": float(coverage), "pinball_loss_medio": float(np.mean(losses))}


def run_backtest(
    data: pd.DataFrame,
    n_dobras: int = 4,
    tamanho_dobra: int = 6,
    selection_tolerance_mape: float = FORECAST_DEFAULTS.selection_tolerance_mape_pp,
) -> dict[str, Any]:
    """Compara candidatos por walk-forward expansivo e seleciona com métricas múltiplas."""
    records: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    predictions_by_model: dict[str, list[np.ndarray]] = {model: [] for model in MODEL_NAMES}
    actuals_by_model: dict[str, list[np.ndarray]] = {model: [] for model in MODEL_NAMES}
    fold_details: list[dict[str, Any]] = []
    for fold_number, (train_idx, test_idx) in enumerate(construir_dobras(data, n_dobras, tamanho_dobra), start=1):
        train = data.iloc[train_idx].reset_index(drop=True)
        test = data.iloc[test_idx].reset_index(drop=True)
        actual = test["vendas_saar_milhoes"].to_numpy()
        period = f"{test['data'].min():%m/%Y}–{test['data'].max():%m/%Y}"
        fold_details.append(
            {
                "dobra": fold_number,
                "periodo": period,
                "treino_ate": train["data"].max(),
                "teste_de": test["data"].min(),
                "teste_ate": test["data"].max(),
            }
        )
        started = perf_counter()
        predictions = _model_predictions(train, test)
        elapsed = perf_counter() - started
        for model_name, prediction in predictions.items():
            if len(prediction) != len(actual) or not np.isfinite(prediction).all():
                records.append(
                    {
                        "dobra": fold_number,
                        "período": period,
                        "modelo": model_name,
                        "status": "FALHOU",
                        "erro": "Previsão inválida",
                    }
                )
                continue
            metrics = metricas(actual, prediction, train["vendas_saar_milhoes"].to_numpy())
            records.append(
                {
                    "dobra": fold_number,
                    "período": period,
                    "modelo": model_name,
                    "status": "OK",
                    "tempo_execucao_s": elapsed / len(predictions),
                    **metrics,
                }
            )
            predictions_by_model[model_name].append(prediction)
            actuals_by_model[model_name].append(actual)
            prediction_rows.extend(
                {
                    "dobra": fold_number,
                    "modelo": model_name,
                    "data": date,
                    "observado": float(observed),
                    "previsto": float(estimated),
                    "erro": float(observed - estimated),
                    "erro_abs": float(abs(observed - estimated)),
                }
                for date, observed, estimated in zip(test["data"], actual, prediction, strict=True)
            )
    results = pd.DataFrame(records)
    success = results.loc[results["status"].eq("OK")].copy()
    if success.empty:
        raise RuntimeError("Nenhum modelo gerou previsões válidas no backtest.")
    summary = (
        success.groupby("modelo", as_index=False)
        .agg(
            mape_medio=("MAPE (%)", "mean"),
            mape_desvio=("MAPE (%)", "std"),
            smape_medio=("sMAPE (%)", "mean"),
            wape_medio=("WAPE (%)", "mean"),
            mae_medio=("MAE (milhões SAAR)", "mean"),
            rmse_medio=("RMSE (milhões SAAR)", "mean"),
            mase_medio=("MASE", "mean"),
            tempo_medio_s=("tempo_execucao_s", "mean"),
            dobras_validas=("dobra", "nunique"),
        )
        .sort_values("mape_medio")
        .reset_index(drop=True)
    )
    winner = _select_model(summary, selection_tolerance_mape)
    actuals = np.concatenate(actuals_by_model[winner])
    winner_predictions = np.concatenate(predictions_by_model[winner])
    residuals = actuals - winner_predictions
    diagnostics = _residual_diagnostics(residuals)
    return {
        "results": results,
        "summary": summary.sort_values(["selection_score", "mape_medio"]).reset_index(drop=True),
        "winner": winner,
        "predictions_by_model": predictions_by_model,
        "actuals": actuals,
        "winner_predictions": winner_predictions,
        "residuals": residuals,
        "ljung_box": diagnostics["ljung_box"],
        "residual_acf": diagnostics["residual_acf"],
        "residual_diagnostics": diagnostics,
        "interval_quality": _interval_quality(actuals, winner_predictions, residuals),
        "fold_details": pd.DataFrame(fold_details),
        "oos_predictions": pd.DataFrame(prediction_rows),
    }


def _moving_block_bootstrap(
    residuals: np.ndarray, replicas: int, horizon: int, block_size: int, rng: np.random.Generator
) -> np.ndarray:
    values = np.asarray(residuals, dtype=float)
    if len(values) <= block_size:
        return rng.choice(values, size=(replicas, horizon), replace=True)
    blocks_needed = int(np.ceil(horizon / block_size))
    starts = rng.integers(0, len(values) - block_size + 1, size=(replicas, blocks_needed))
    paths = np.empty((replicas, blocks_needed * block_size))
    for replica in range(replicas):
        paths[replica] = np.concatenate([values[start : start + block_size] for start in starts[replica]])
    return paths[:, :horizon]


def make_forecast(
    data: pd.DataFrame,
    backtest: dict[str, Any],
    horizon: int = FORECAST_DEFAULTS.horizon_months,
    bootstrap_replicas: int = FORECAST_DEFAULTS.bootstrap_replicas,
    seed: int = FORECAST_DEFAULTS.random_seed,
    bootstrap_block_size: int = FORECAST_DEFAULTS.bootstrap_block_size,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Reestima o vencedor e produz P10/P25/P50/P75/P90 por bootstrap empírico."""
    winner = backtest["winner"]
    future_dates = pd.date_range(data["data"].max() + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    if winner == "Holt-Winters":
        point_forecast = prever_holt_winters(data, horizon)
    elif winner == "Regressão com defasagens":
        point_forecast = prever_regressao_defasagens(data, horizon)
    elif winner == "AutoReg sazonal":
        point_forecast = prever_autoreg_sazonal(data, horizon)
    else:
        point_forecast = prever_sazonal_naive(data, future_dates)
    residuals = np.asarray(backtest["residuals"], dtype=float)
    rng = np.random.default_rng(seed)
    ljung = backtest.get("residual_diagnostics", {}).get("ljung_box", pd.DataFrame())
    residual_dependence = not ljung.empty and bool((ljung["lb_pvalue"] < 0.05).any())
    if residual_dependence:
        bootstrap_errors = _moving_block_bootstrap(residuals, bootstrap_replicas, horizon, bootstrap_block_size, rng)
        bootstrap_method = "moving_block"
    else:
        bootstrap_errors = rng.choice(residuals, size=(bootstrap_replicas, horizon), replace=True)
        bootstrap_method = "iid"
    simulations = np.maximum(point_forecast[None, :] + bootstrap_errors, 0)
    quantiles = {
        f"p{int(q * 100)}": np.percentile(simulations, q * 100, axis=0) for q in FORECAST_DEFAULTS.confidence_quantiles
    }
    forecast = pd.DataFrame({"data": future_dates, **quantiles})
    forecast["cenario_conservador"] = forecast["p10"]
    forecast["cenario_base"] = forecast["p50"]
    forecast["cenario_otimista"] = forecast["p90"]
    forecast["demanda_mensal_base_milhoes"] = forecast["p50"] / 12
    forecast.attrs["bootstrap_method"] = bootstrap_method
    forecast.attrs["bootstrap_block_size"] = bootstrap_block_size if residual_dependence else None
    return forecast, simulations


def converter_demanda_veiculos(scenario_millions_saar: pd.Series, participation: float) -> pd.Series:
    """Compatibilidade pública: converte SAAR em unidades mensais assumidas."""
    return demand_from_saar(scenario_millions_saar, participation)


def resolver_plano_producao(
    demanda: np.ndarray,
    capacidade: int,
    estoque_inicial: int,
    custo_producao: float,
    custo_estoque: float,
    custo_ruptura: float,
    nome: str = "plano",
) -> dict[str, Any]:
    """Compatibilidade pública com o motor de planejamento configurável."""
    assumptions = PlanningAssumptions(
        participation=0.0,
        regular_capacity=capacidade,
        initial_inventory=estoque_inicial,
        production_cost=custo_producao,
        inventory_cost=custo_estoque,
        backlog_cost=custo_ruptura,
    )
    return solve_production_plan(demanda, assumptions, nome)


def build_production_plan(
    forecast: pd.DataFrame,
    participation: float,
    capacity: int,
    initial_inventory: int,
    production_cost: float,
    inventory_cost: float,
    backlog_cost: float,
    overtime_capacity: int = 0,
    overtime_cost: float = 30_000.0,
    safety_stock: int = 0,
    safety_stock_penalty: float = 1_000.0,
    setup_cost: float = 0.0,
) -> dict[str, Any]:
    """Produz cenários Base/Upside/Downside/Stress e sensibilidade com hipóteses declaradas."""
    assumptions = PlanningAssumptions(
        participation=participation,
        regular_capacity=capacity,
        overtime_capacity=overtime_capacity,
        initial_inventory=initial_inventory,
        safety_stock=safety_stock,
        production_cost=production_cost,
        overtime_cost=overtime_cost,
        inventory_cost=inventory_cost,
        backlog_cost=backlog_cost,
        safety_stock_penalty=safety_stock_penalty,
        setup_cost=setup_cost,
    )
    result = build_scenario_table(forecast, assumptions)
    result["sensitivity"] = build_sensitivity(forecast, assumptions)
    result["decision"] = decision_brief(result["scenarios"], assumptions)
    result["assumptions"] = assumptions
    result["plan"]["utilizacao_capacidade_pct"] = result["plan"]["utilizacao_regular_pct"]
    return result


def run_full_analysis(
    fallback_path: str | Path,
    n_folds: int = FORECAST_DEFAULTS.n_folds,
    test_size: int = FORECAST_DEFAULTS.test_size_months,
    horizon: int = FORECAST_DEFAULTS.horizon_months,
    bootstrap_replicas: int = FORECAST_DEFAULTS.bootstrap_replicas,
    seed: int = FORECAST_DEFAULTS.random_seed,
    participation: float = 0.08,
    capacity: int = 110_000,
    initial_inventory: int = 15_000,
    production_cost: float = 25_000,
    inventory_cost: float = 350,
    backlog_cost: float = 45_000,
    overtime_capacity: int = 0,
    overtime_cost: float = 30_000.0,
    safety_stock: int = 0,
    safety_stock_penalty: float = 1_000.0,
    setup_cost: float = 0.0,
    source_url: str = FRED_CSV_URL,
    allow_online: bool = True,
) -> dict[str, Any]:
    """Executa mercado → forecast probabilístico → plano operacional de forma determinística."""
    raw, provenance = read_fred_with_provenance(source_url, fallback_path, allow_online=allow_online)
    data, quality = prepare_data(raw)
    refresh = market_refresh_summary(data, fallback_path, provenance)
    diagnostics = compute_diagnostics(data)
    backtest = run_backtest(data, n_folds, test_size)
    forecast, simulations = make_forecast(data, backtest, horizon, bootstrap_replicas, seed)
    production = build_production_plan(
        forecast,
        participation,
        capacity,
        initial_inventory,
        production_cost,
        inventory_cost,
        backlog_cost,
        overtime_capacity=overtime_capacity,
        overtime_cost=overtime_cost,
        safety_stock=safety_stock,
        safety_stock_penalty=safety_stock_penalty,
        setup_cost=setup_cost,
    )
    return {
        "raw": raw,
        "source_label": str(refresh["source_label"]),
        "market_refresh": refresh,
        "data": data,
        "quality": quality,
        "diagnostics": diagnostics,
        "backtest": backtest,
        "forecast": forecast,
        "simulations": simulations,
        "production": production,
        "parameters": {
            "n_folds": n_folds,
            "test_size": test_size,
            "horizon": horizon,
            "bootstrap_replicas": bootstrap_replicas,
            "seed": seed,
            "participation": participation,
            "capacity": capacity,
            "initial_inventory": initial_inventory,
            "production_cost": production_cost,
            "inventory_cost": inventory_cost,
            "backlog_cost": backlog_cost,
            "overtime_capacity": overtime_capacity,
            "overtime_cost": overtime_cost,
            "safety_stock": safety_stock,
            "safety_stock_penalty": safety_stock_penalty,
            "setup_cost": setup_cost,
            "allow_online": allow_online,
            "bootstrap_method": forecast.attrs.get("bootstrap_method"),
        },
    }
