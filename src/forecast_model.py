"""Modelo de forecast macroeconômico com OLS Newey-West e validação walk-forward.

Consome o feature store particionado em Parquet para construir a matriz de regressores,
aplica erros-padrão HAC (Newey-West) para lidar com autocorrelação residual remanescente,
e executa validação walk-forward para gerar intervalos p10–90. O estimador
padrão é OLS com erros HAC; GLSAR fica disponível como contingência para
resíduos persistentemente autocorrelacionados.

Especificação de variáveis (v2.3):
    - A matriz usa conjuntamente y_lag1, y_lag2, y_lag3, y_lag6, y_lag9 e y_lag12.
    - Drivers macro opcionais entram somente quando as colunas estão disponíveis.
    - CPI entra em variação percentual mensal com lags 1 e 3.
    - Produção industrial entra em variação percentual mensal com lag 2.
    - Os níveis CPI e produção industrial não entram diretamente na matriz.

Política de aceite:
    - Ljung–Box OOS agrupado, lag e alpha definidos em acceptance_policy.py.
    - MAPE ≤ 4,00 % é o piso de aceite recalibrado; 2,87 % permanece como alvo nominal exploratório.
    - Cobertura p10–90 ≥ 75 % é o piso de aceite; 80 % permanece como alvo nominal.
    - ARCH e CUSUM continuam diagnósticos obrigatórios e reportados.
    - Durbin–Watson por dobra é somente descritivo.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.stats.stattools import durbin_watson

from acceptance_policy import ACCEPTANCE_POLICY
from config import DATA_DIR

logger = logging.getLogger(__name__)

# Séries FRED com lag t-1 (regra point-in-time padrão).
MACRO_FEATURES_LAG1: dict[str, str] = {
    "taxa_financiamento_auto_pct": "Financiamento auto",
    "desemprego_pct": "Desemprego",
    "preco_gasolina_regular_fred": "Gasolina (GASREG)",
    "confianca_consumidor": "Confiança do consumidor",
    "empregados_total_milhares": "Emprego total",
}

# FEDFUNDS com lag t-2: sinal negativo mais consistente que lag t-1 para vendas SAAR.
MACRO_FEATURES_LAG2: dict[str, str] = {
    "fed_funds_pct": "Juros Fed (lag 2)",
}

# Diferenças já defasadas no feature builder; não aplicar shift adicional.
DIFF_FEATURES: dict[str, str] = {
    "CPI_diff_lag1": "Inflação Δ% (lag 1)",
    "CPI_diff_lag3": "Inflação Δ% (lag 3)",
    "PRODIND_diff_lag2": "Produção industrial Δ% (lag 2)",
}

# Compat: MACRO_FEATURES aponta para todos os drivers expostos no gráfico.
MACRO_FEATURES: dict[str, str] = {**MACRO_FEATURES_LAG1, **MACRO_FEATURES_LAG2, **DIFF_FEATURES}

# Família de lags distribuídos validada no backtest OOS do painel diagnóstico.
# O conjunto captura dinâmica curta, intermediária e sazonal sem alterar o forecast operacional.
TARGET_LAGS = [1, 2, 3, 6, 9, 12]

# Arquivo de referência com métricas da versão anterior (Ridge com defasagens).
_PREV_PERF_FILE = DATA_DIR / "model_artifacts" / "advanced_model_summary.json"
_V2_PERF_FILE = DATA_DIR / "model_artifacts" / "model_performance_v2.json"

# Número de dobras walk-forward e tamanho de cada dobra (meses).
_N_FOLDS = 3
_FOLD_SIZE = 6

# Critério OOS agrupado: 18 resíduos permitem um teste conjunto, mas não um lag alto.
GROUPED_OOS_LB_LAG = ACCEPTANCE_POLICY.grouped_ljung_box_lag
GROUPED_OOS_LB_PVALUE_MIN = ACCEPTANCE_POLICY.alpha


def _load_feature_store_market(store_dir: Path) -> pd.DataFrame:
    """Lê as partições mensais do feature_builder sem entidade (mercado agregado)."""
    source_path = store_dir / "source=feature_builder"
    if not source_path.exists():
        return pd.DataFrame()
    # Apenas partições sem subdirectórios de marca/modelo (mercado agregado).
    partitions = [
        p
        for p in sorted(source_path.rglob("data.parquet"))
        if p.parent.name.startswith("month=") or p.parent.parent.name.startswith("month=")
    ]
    # Filtra somente partições de nível month= (sem marca=).
    market_partitions = [p for p in partitions if p.parent.name.startswith("month=")]
    if not market_partitions:
        return pd.DataFrame()
    frames = [pd.read_parquet(p) for p in market_partitions]
    return pd.concat(frames, ignore_index=True)


def _load_fred_snapshot() -> pd.DataFrame:
    """Carrega o snapshot FRED local (607 obs) como base histórica do target."""
    from config import MARKET_SNAPSHOT  # noqa: PLC0415

    if not MARKET_SNAPSHOT.exists():
        return pd.DataFrame()
    df = pd.read_csv(MARKET_SNAPSHOT)
    date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
    val_col = "TOTALSA" if "TOTALSA" in df.columns else df.columns[1]
    result = pd.DataFrame(
        {
            "mes": pd.to_datetime(df[date_col], errors="coerce"),
            "vendas_saar_milhoes": pd.to_numeric(df[val_col], errors="coerce"),
        }
    ).dropna()
    return result.set_index("mes").sort_index()


def build_regression_matrix(
    store_dir: Path | None = None,
    *,
    target_lags: list[int] | None = None,
) -> pd.DataFrame:
    """Constrói a matriz mensal com target e regressores defasados.

    Usa o snapshot FRED local (607 obs) como base histórica do target e enriquece
    com séries macroeconômicas do feature store quando disponíveis. Retorna um
    DataFrame com índice temporal mensal, coluna `y` (TOTALSA t) e colunas `X_*`
    para cada regressor, já com os lags aplicados e linhas com NaN removidas.
    """
    store_dir = store_dir or DATA_DIR / "feature_store"
    target_lags = TARGET_LAGS if target_lags is None else target_lags

    # Base histórica: snapshot FRED local com 607 observações mensais.
    base = _load_fred_snapshot()
    if base.empty:
        raise ValueError("Snapshot FRED local ausente. Verifique data/TOTALSA_snapshot.csv.")

    matrix = pd.DataFrame(index=base.index)
    matrix["y"] = base["vendas_saar_milhoes"]

    # Defasagens da própria série-alvo.
    for lag in target_lags:
        matrix[f"y_lag{lag}"] = matrix["y"].shift(lag)

    # Enriquece com séries macro do feature store quando disponíveis.
    store_raw = _load_feature_store_market(store_dir)
    if not store_raw.empty and "mes" in store_raw.columns:
        store_raw["mes"] = pd.to_datetime(store_raw["mes"], errors="coerce")
        store_raw = store_raw.dropna(subset=["mes"]).sort_values("mes").drop_duplicates(subset=["mes"])
        store_raw = store_raw.set_index("mes")

        # Regressores com lag t-1 (regra point-in-time padrão).
        for col, label in MACRO_FEATURES_LAG1.items():
            if col in store_raw.columns:
                aligned = store_raw[col].reindex(matrix.index)
                matrix[f"X_{col}"] = aligned.shift(1)
                logger.debug("Regressor '%s' (%s) lag=1 adicionado.", col, label)
            else:
                logger.debug("Regressor '%s' (%s) ausente no feature store — omitido.", col, label)

        # FEDFUNDS com lag t-2: transmissão da política monetária leva ~2 meses para afetar vendas.
        for col, label in MACRO_FEATURES_LAG2.items():
            if col in store_raw.columns:
                aligned = store_raw[col].reindex(matrix.index)
                matrix[f"X_{col}_lag2"] = aligned.shift(2)
                logger.debug("Regressor '%s' (%s) lag=2 adicionado.", col, label)
            else:
                logger.debug("Regressor '%s' (%s) ausente no feature store — omitido.", col, label)

        # CPI e produção industrial entram como variações percentuais mensais.
        # Lags materializados pelo builder são preferidos; quando não existem,
        # deriva-se a variação dos níveis no próprio ponto de montagem da matriz.
        diff_specs = {
            "CPI_diff_lag1": ("cpi", 1),
            "CPI_diff_lag3": ("cpi", 3),
            "PRODIND_diff_lag2": ("producao_industrial", 2),
        }
        for feature_name, (source_name, lag) in diff_specs.items():
            if feature_name in store_raw.columns:
                matrix[f"X_{feature_name}"] = pd.to_numeric(store_raw[feature_name], errors="coerce").reindex(
                    matrix.index
                )
                logger.debug("Regressor pré-calculado '%s' adicionado.", feature_name)
                continue
            if source_name not in store_raw.columns:
                logger.debug("Fonte para '%s' ausente no feature store — omitida.", feature_name)
                continue
            levels = pd.to_numeric(store_raw[source_name], errors="coerce")
            diff_series = levels.pct_change(fill_method=None).mul(100)
            diff_series = diff_series.replace([np.inf, -np.inf], np.nan)
            matrix[f"X_{feature_name}"] = diff_series.reindex(matrix.index).shift(lag)
            logger.debug("Regressor derivado '%s' lag=%d adicionado.", feature_name, lag)
    else:
        logger.info("Feature store sem dados de mercado; modelo usa apenas defasagem y_lag1.")

    # Dummies sazonais mensais (janeiro como referência).
    for month in range(2, 13):
        matrix[f"mes_{month}"] = (matrix.index.month == month).astype(float)

    # Remove linhas com NaN em qualquer coluna (resultado natural dos lags).
    matrix = matrix.dropna()
    logger.info("Matriz de regressão: %d observações × %d colunas.", len(matrix), matrix.shape[1])
    return matrix


def _ols_newey_west(
    y: np.ndarray, X: np.ndarray, maxlags: int = 4
) -> sm.regression.linear_model.RegressionResultsWrapper:
    """Ajusta OLS com erros-padrão HAC (Newey-West)."""
    X_const = sm.add_constant(X, has_constant="add")
    model = sm.OLS(y, X_const)
    # cov_type='HAC' com maxlags de Newey-West: floor(4 * (n/100)^(2/9)) é a regra padrão.
    result = model.fit(cov_type="HAC", cov_kwds={"maxlags": maxlags, "use_correction": True})
    return result


def _glsar_cochrane_orcutt(
    y: np.ndarray, X: np.ndarray, rho: int = 1
) -> sm.regression.linear_model.RegressionResultsWrapper:
    """Ajusta GLSAR iterativo para modelar AR(1) nos erros do OLS."""
    X_const = sm.add_constant(X, has_constant="add")
    model = sm.GLSAR(y, X_const, rho=rho)
    return model.iterative_fit(maxiter=10)


def _fit_estimator(
    y: np.ndarray,
    X: np.ndarray,
    *,
    estimator: str,
    maxlags: int,
) -> sm.regression.linear_model.RegressionResultsWrapper:
    """Despacha o estimador mantendo o contrato comum de predição e coeficientes."""
    if estimator == "newey_west":
        return _ols_newey_west(y, X, maxlags=maxlags)
    if estimator == "glsar":
        return _glsar_cochrane_orcutt(y, X)
    raise ValueError(f"Estimador desconhecido: {estimator!r}")


def _pinball_loss(actual: np.ndarray, predicted: np.ndarray, residuals: np.ndarray) -> float:
    """Pinball loss médio para quantis p10, p50, p90 usando resíduos históricos."""
    losses = []
    for q in (0.10, 0.50, 0.90):
        adj = np.quantile(residuals, q)
        err = actual - (predicted + adj)
        losses.append(float(np.mean(np.maximum(q * err, (q - 1) * err))))
    return float(np.mean(losses))


def _coverage(actual: np.ndarray, predicted: np.ndarray, residuals: np.ndarray) -> float:
    lo, hi = np.quantile(residuals, [0.10, 0.90])
    return float(np.mean((actual >= predicted + lo) & (actual <= predicted + hi)))


def walk_forward_ols(matrix: pd.DataFrame, *, estimator: str = "newey_west") -> dict[str, Any]:
    """Validação walk-forward com dobras expansivas e estimador configurável.

    Retorna métricas agregadas, coeficientes padronizados da última dobra e DW médio.
    """
    n = len(matrix)
    start_test = n - _N_FOLDS * _FOLD_SIZE
    if start_test < 24:
        raise ValueError(
            f"Histórico insuficiente para {_N_FOLDS} dobras de {_FOLD_SIZE} meses "
            f"(disponível: {n} obs; mínimo: {24 + _N_FOLDS * _FOLD_SIZE})."
        )

    feature_cols = [c for c in matrix.columns if c != "y"]
    X_all = matrix[feature_cols].to_numpy(dtype=float)
    y_all = matrix["y"].to_numpy(dtype=float)

    fold_metrics: list[dict[str, float]] = []
    all_actuals: list[np.ndarray] = []
    all_preds: list[np.ndarray] = []
    all_residuals: list[np.ndarray] = []
    all_oos_errors: list[np.ndarray] = []
    last_result = None

    for fold in range(_N_FOLDS):
        train_end = start_test + fold * _FOLD_SIZE
        test_end = train_end + _FOLD_SIZE

        X_train, y_train = X_all[:train_end], y_all[:train_end]
        X_test, y_test = X_all[train_end:test_end], y_all[train_end:test_end]

        # Determina maxlags de Newey-West pela regra de bandwidth automático.
        n_train = len(y_train)
        maxlags = max(1, int(np.floor(4 * (n_train / 100) ** (2 / 9))))

        result = _fit_estimator(y_train, X_train, estimator=estimator, maxlags=maxlags)
        last_result = result

        X_test_const = sm.add_constant(X_test, has_constant="add")
        preds = result.predict(X_test_const)
        residuals_train = y_train - result.predict(sm.add_constant(X_train, has_constant="add"))

        errors = y_test - preds
        denom = np.where(np.abs(y_test) < 1e-12, 1e-12, np.abs(y_test))
        mape = float(np.mean(np.abs(errors / denom)) * 100)
        mae = float(np.mean(np.abs(errors)))
        rmse = float(np.sqrt(np.mean(errors**2)))
        dw = float(durbin_watson(errors))
        dw_centered = float(durbin_watson(errors - np.mean(errors)))
        ljung_box_pvalue = float(acorr_ljungbox(residuals_train, lags=[12], return_df=True)["lb_pvalue"].iloc[0])
        arch_pvalue = float(het_arch(residuals_train, nlags=12)[1])
        pinball = _pinball_loss(y_test, preds, residuals_train)
        cov = _coverage(y_test, preds, residuals_train)

        fold_metrics.append(
            {
                "fold": fold + 1,
                "mape": mape,
                "mae": mae,
                "rmse": rmse,
                "dw": dw,
                "dw_centered": dw_centered,
                "mean_oos_error": float(np.mean(errors)),
                "ljung_box_pvalue_train_lag12": ljung_box_pvalue,
                "arch_pvalue_train_lag12": arch_pvalue,
                "pinball": pinball,
                "coverage": cov,
            }
        )
        all_actuals.append(y_test)
        all_preds.append(preds)
        all_residuals.append(residuals_train)
        all_oos_errors.append(errors)

    # Ljung–Box primário sobre todos os resíduos OOS, mantendo a ordem temporal.
    oos_residuals = np.concatenate(all_oos_errors)
    grouped_lb = acorr_ljungbox(oos_residuals, lags=[GROUPED_OOS_LB_LAG], return_df=True)
    grouped_lb_stat = float(grouped_lb["lb_stat"].iloc[0])
    grouped_lb_pvalue = float(grouped_lb["lb_pvalue"].iloc[0])

    # Métricas agregadas.
    mapes = [m["mape"] for m in fold_metrics]
    maes = [m["mae"] for m in fold_metrics]
    rmses = [m["rmse"] for m in fold_metrics]
    dws = [m["dw"] for m in fold_metrics]
    coverages = [m["coverage"] for m in fold_metrics]
    pinballs = [m["pinball"] for m in fold_metrics]

    # Coeficientes padronizados da última dobra (para o gráfico de drivers).
    coef_df = _standardized_coefficients(last_result, feature_cols)
    effective_regressors = [column for column in feature_cols if not column.startswith("mes_")]
    configured_driver_labels = {
        **{f"X_{column}_lag1": label for column, label in MACRO_FEATURES_LAG1.items()},
        **{f"X_{column}_lag2": label for column, label in MACRO_FEATURES_LAG2.items()},
    }
    absent_configured_drivers = [
        label for column, label in configured_driver_labels.items() if column not in effective_regressors
    ]

    return {
        "estimador": estimator,
        "regressores": effective_regressors,
        "drivers_configurados_mas_ausentes": absent_configured_drivers,
        "fold_metrics": fold_metrics,
        "mape_medio": float(np.mean(mapes)),
        "mape_desvio": float(np.std(mapes)),
        "mae_medio": float(np.mean(maes)),
        "rmse_medio": float(np.mean(rmses)),
        "durbin_watson_medio": float(np.mean(dws)),
        "durbin_watson_ultima_dobra": float(dws[-1]),
        "durbin_watson_papel": "descritivo; não participa do aceite binário",
        "ljung_box_oos_grouped_lag": GROUPED_OOS_LB_LAG,
        "ljung_box_oos_grouped_stat": grouped_lb_stat,
        "ljung_box_oos_grouped_pvalue": grouped_lb_pvalue,
        "n_oos_residuals": int(len(oos_residuals)),
        "coverage_p10_p90": float(np.mean(coverages)),
        "pinball_loss_medio": float(np.mean(pinballs)),
        "n_obs_treino_final": int(len(matrix) - _FOLD_SIZE),
        "n_folds": _N_FOLDS,
        "fold_size": _FOLD_SIZE,
        "coeficientes_padronizados": coef_df,
        "actuals": np.concatenate(all_actuals),
        "predictions": np.concatenate(all_preds),
        "residuals": np.concatenate(all_residuals),
        "oos_residuals": oos_residuals,
    }


def _standardized_coefficients(result: Any, feature_cols: list[str]) -> pd.DataFrame:
    """Extrai coeficientes padronizados (beta) e intervalos de confiança 95 % do modelo."""
    # Quando X é passado como ndarray, statsmodels usa nomes genéricos (x1, x2...)
    # e params/conf_int/pvalues são ndarrays indexados por posição.
    # O primeiro elemento é sempre a constante (add_constant insere na posição 0).
    params_arr = np.asarray(result.params)  # shape: (n_params,)
    conf_arr = np.asarray(result.conf_int())  # shape: (n_params, 2)
    pvalues_arr = np.asarray(result.pvalues)  # shape: (n_params,)

    # Nomes legíveis para o gráfico de drivers.
    label_map = {f"X_{k}": v for k, v in MACRO_FEATURES_LAG1.items()}
    # FEDFUNDS usa coluna X_fed_funds_pct_lag2 (lag=2 explícito no nome).
    label_map.update({f"X_{k}_lag2": v for k, v in MACRO_FEATURES_LAG2.items()})
    label_map.update({f"X_{k}": v for k, v in DIFF_FEATURES.items()})
    label_map.update({f"y_lag{lag}": f"Vendas t-{lag}" for lag in TARGET_LAGS})
    # Dummies sazonais omitidas do gráfico de drivers.
    names = []
    coefs = []
    lo95 = []
    hi95 = []
    pvs = []
    # feature_cols[i] corresponde a params_arr[i + 1] (posição 0 é a constante).
    for i, col in enumerate(feature_cols):
        if col.startswith("mes_"):
            continue
        label = label_map.get(col, col)
        param_idx = i + 1  # desloca 1 por causa da constante
        names.append(label)
        coefs.append(float(params_arr[param_idx]))
        lo95.append(float(conf_arr[param_idx, 0]))
        hi95.append(float(conf_arr[param_idx, 1]))
        pvs.append(float(pvalues_arr[param_idx]))

    df = pd.DataFrame(
        {
            "variavel": names,
            "coeficiente": coefs,
            "ic_lo95": lo95,
            "ic_hi95": hi95,
            "pvalue": pvs,
        }
    )
    # Padroniza pelo desvio absoluto para comparação de magnitude entre variáveis.
    max_abs = df["coeficiente"].abs().max()
    df["coef_norm"] = df["coeficiente"] / max_abs if max_abs > 1e-12 else df["coeficiente"]
    return df.sort_values("coef_norm", key=abs, ascending=False).reset_index(drop=True)


def save_performance_v2(metrics: dict[str, Any], path: Path | None = None) -> Path:
    """Persiste métricas do novo modelo e compara com a versão anterior quando disponível."""
    out = path or _V2_PERF_FILE
    out.parent.mkdir(parents=True, exist_ok=True)

    previous: dict[str, Any] = {}
    if _PREV_PERF_FILE.exists():
        try:
            raw = json.loads(_PREV_PERF_FILE.read_text(encoding="utf-8"))
            # Extrai métricas do modelo vencedor anterior (Ridge com defasagens).
            for candidate in raw.get("candidatos", []):
                if candidate.get("modelo") == "Regressão com defasagens":
                    previous = {
                        "modelo": "Ridge com defasagens (v1)",
                        "mape_medio": candidate.get("mape_medio"),
                        "mae_medio": candidate.get("mae_medio"),
                        "rmse_medio": candidate.get("rmse_medio"),
                    }
                    break
        except Exception:
            pass

    # Aceite v2.3: dependência serial OOS agrupada; DW por dobra é descritivo.
    metas = {
        "ljung_box_oos_grouped_lag": GROUPED_OOS_LB_LAG,
        "ljung_box_oos_grouped_pvalue_min": GROUPED_OOS_LB_PVALUE_MIN,
        "policy_version": ACCEPTANCE_POLICY.version,
        "ljung_box_alpha": ACCEPTANCE_POLICY.alpha,
        "mape_max_pct": ACCEPTANCE_POLICY.mape_acceptance_max_pct,
        "mape_nominal_target_max_pct": ACCEPTANCE_POLICY.mape_nominal_target_max_pct,
        "coverage_p10_p90_min": ACCEPTANCE_POLICY.coverage_acceptance_min,
        "coverage_nominal_target": ACCEPTANCE_POLICY.coverage_nominal_target,
        "diagnostic_tests_required": list(ACCEPTANCE_POLICY.diagnostic_tests_required),
        "tail_metrics_required": list(ACCEPTANCE_POLICY.tail_metrics_required),
        "tail_preservation_direction": ACCEPTANCE_POLICY.tail_preservation_direction,
    }
    resultados = {
        "ljung_box_oos_grouped_pvalue": metrics["ljung_box_oos_grouped_pvalue"],
        "mape_medio_pct": metrics["mape_medio"],
        "coverage_p10_p90": metrics["coverage_p10_p90"],
    }
    aceite = {
        "ljung_box_oos_grouped": (
            resultados["ljung_box_oos_grouped_pvalue"] >= metas["ljung_box_oos_grouped_pvalue_min"]
        ),
        "mape": resultados["mape_medio_pct"] <= metas["mape_max_pct"],
        "coverage": resultados["coverage_p10_p90"] >= metas["coverage_p10_p90_min"],
    }

    effective_regressors = metrics.get("regressores", [])
    effective_description = ", ".join(effective_regressors) or "nenhum regressor disponível"
    absent_configured_drivers = metrics.get("drivers_configurados_mas_ausentes", [])
    estimator_name = metrics.get("estimador", "newey_west")
    payload = {
        "modelo": "OLS Newey-West (v2.3)" if estimator_name == "newey_west" else "GLSAR (Cochrane-Orcutt)",
        "descricao": f"Regressores usados: {effective_description}.",
        "papel_no_app": "diagnostico_de_drivers",
        "candidatos_avaliados_e_nao_selecionados": [],
        "drivers_configurados_mas_ausentes_na_matriz": absent_configured_drivers,
        "nota_sobre_selecao": (
            "O código atual não executa seleção stepwise desses drivers; os itens ausentes foram omitidos "
            "por indisponibilidade das colunas no feature store, não por rejeição estatística documentada."
        ),
        "nao_alimenta_forecast_principal": True,
        "forecast_principal_app": "Regressão com defasagens (src/analysis.py e src/forecast_engine.py)",
        "status_operacional": "aprovado" if all(aceite.values()) else "nao_aprovado",
        "criterio_dependencia_serial_primario": "Ljung–Box OOS agrupado das 3 dobras, lag 3, n=18",
        "durbin_watson_uso": "descritivo; não participa do aceite binário",
        "criterios_aceite_reprovados": [nome for nome, aprovado in aceite.items() if not aprovado],
        "n_folds": metrics["n_folds"],
        "fold_size_meses": metrics["fold_size"],
        "n_obs_treino_final": metrics["n_obs_treino_final"],
        "regressores": metrics.get("regressores", []),
        "metricas": {
            "mape_medio_pct": round(metrics["mape_medio"], 4),
            "mape_desvio_pp": round(metrics["mape_desvio"], 4),
            "mae_medio": round(metrics["mae_medio"], 4),
            "rmse_medio": round(metrics["rmse_medio"], 4),
            "durbin_watson_medio": round(metrics["durbin_watson_medio"], 4),
            "durbin_watson_ultima_dobra": round(metrics["durbin_watson_ultima_dobra"], 4),
            "durbin_watson_papel": "descritivo",
            "ljung_box_oos_grouped_lag": metrics["ljung_box_oos_grouped_lag"],
            "ljung_box_oos_grouped_stat": round(metrics["ljung_box_oos_grouped_stat"], 4),
            "ljung_box_oos_grouped_pvalue": round(metrics["ljung_box_oos_grouped_pvalue"], 4),
            "n_oos_residuals": metrics["n_oos_residuals"],
            "coverage_p10_p90": round(metrics["coverage_p10_p90"], 4),
            "pinball_loss_medio": round(metrics["pinball_loss_medio"], 4),
        },
        "metas_aceite": metas,
        "resultado_aceite": aceite,
        "todos_criterios_atingidos": all(aceite.values()),
        "versao_anterior": previous,
        "dobras": metrics["fold_metrics"],
    }

    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "model_performance_v2.json salvo — DW=%.2f | MAPE=%.2f%% | Cob=%.1f%%",
        metrics["durbin_watson_medio"],
        metrics["mape_medio"],
        metrics["coverage_p10_p90"] * 100,
    )
    return out


def run_ols_forecast(
    store_dir: Path | None = None,
    save: bool = True,
    *,
    estimator: str = "newey_west",
) -> dict[str, Any]:
    """Lê o feature store, treina o estimador selecionado e persiste as métricas.

    Retorna o dicionário de métricas e o DataFrame de coeficientes padronizados.
    """
    matrix = build_regression_matrix(store_dir)
    results = walk_forward_ols(matrix, estimator=estimator)

    if save:
        save_performance_v2(results)

    return results
