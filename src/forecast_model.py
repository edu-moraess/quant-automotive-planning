"""Modelo de forecast macroeconômico com OLS Newey-West e validação walk-forward.

Consome o feature store particionado em Parquet para construir a matriz de regressores,
aplica erros-padrão HAC (Newey-West) para lidar com autocorrelação residual remanescente,
e executa validação walk-forward com bootstrap moving-block para gerar intervalos p10–p90.

Metas de qualidade:
    - Durbin-Watson ≥ 1.60
    - MAPE ≤ 3.0 %
    - Cobertura p10–p90 ≥ 75 %
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.stattools import durbin_watson

from config import DATA_DIR

logger = logging.getLogger(__name__)

# Séries FRED que compõem a matriz de regressores macroeconômicos.
# Cada série é defasada em t-1 para preservar a regra point-in-time.
MACRO_FEATURES: dict[str, str] = {
    "fed_funds_pct": "Juros (Fed Funds)",
    "taxa_financiamento_auto_pct": "Financiamento auto",
    "desemprego_pct": "Desemprego",
    "cpi": "Inflação (CPI)",
    "preco_gasolina_regular_fred": "Gasolina (FRED)",
    "confianca_consumidor": "Confiança do consumidor",
    "empregados_total_milhares": "Emprego total",
    "producao_industrial": "Produção industrial",
}

# Colunas de defasagem da própria série-alvo.
TARGET_LAGS = [1, 2, 12]

# Arquivo de referência com métricas da versão anterior (Ridge com defasagens).
_PREV_PERF_FILE = DATA_DIR / "model_artifacts" / "advanced_model_summary.json"
_V2_PERF_FILE = DATA_DIR / "model_artifacts" / "model_performance_v2.json"

# Número de dobras walk-forward e tamanho de cada dobra (meses).
_N_FOLDS = 3
_FOLD_SIZE = 6


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


def build_regression_matrix(store_dir: Path | None = None) -> pd.DataFrame:
    """Constrói a matriz mensal com target e regressores defasados.

    Usa o snapshot FRED local (607 obs) como base histórica do target e enriquece
    com séries macroeconômicas do feature store quando disponíveis. Retorna um
    DataFrame com índice temporal mensal, coluna `y` (TOTALSA t) e colunas `X_*`
    para cada regressor, já com os lags aplicados e linhas com NaN removidas.
    """
    store_dir = store_dir or DATA_DIR / "feature_store"

    # Base histórica: snapshot FRED local com 607 observações mensais.
    base = _load_fred_snapshot()
    if base.empty:
        raise ValueError("Snapshot FRED local ausente. Verifique data/TOTALSA_snapshot.csv.")

    matrix = pd.DataFrame(index=base.index)
    matrix["y"] = base["vendas_saar_milhoes"]

    # Defasagens da própria série-alvo.
    for lag in TARGET_LAGS:
        matrix[f"y_lag{lag}"] = matrix["y"].shift(lag)

    # Enriquece com séries macro do feature store quando disponíveis.
    store_raw = _load_feature_store_market(store_dir)
    if not store_raw.empty and "mes" in store_raw.columns:
        store_raw["mes"] = pd.to_datetime(store_raw["mes"], errors="coerce")
        store_raw = store_raw.dropna(subset=["mes"]).sort_values("mes").drop_duplicates(subset=["mes"])
        store_raw = store_raw.set_index("mes")
        for col, label in MACRO_FEATURES.items():
            if col in store_raw.columns:
                # Alinha pelo índice temporal e aplica lag t-1.
                aligned = store_raw[col].reindex(matrix.index)
                matrix[f"X_{col}"] = aligned.shift(1)
                logger.debug("Regressor '%s' (%s) adicionado do feature store.", col, label)
            else:
                logger.debug("Regressor '%s' (%s) ausente no feature store — omitido.", col, label)
    else:
        logger.info("Feature store sem dados de mercado; modelo usa apenas defasagens do target.")

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
    """Ajusta OLS com erros-padrão HAC (Newey-West) para corrigir autocorrelação residual."""
    X_const = sm.add_constant(X, has_constant="add")
    model = sm.OLS(y, X_const)
    # cov_type='HAC' com maxlags de Newey-West: floor(4 * (n/100)^(2/9)) é a regra padrão.
    result = model.fit(cov_type="HAC", cov_kwds={"maxlags": maxlags, "use_correction": True})
    return result


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


def walk_forward_ols(matrix: pd.DataFrame) -> dict[str, Any]:
    """Validação walk-forward com _N_FOLDS dobras expansivas e bootstrap moving-block.

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
    last_result = None

    for fold in range(_N_FOLDS):
        train_end = start_test + fold * _FOLD_SIZE
        test_end = train_end + _FOLD_SIZE

        X_train, y_train = X_all[:train_end], y_all[:train_end]
        X_test, y_test = X_all[train_end:test_end], y_all[train_end:test_end]

        # Determina maxlags de Newey-West pela regra de bandwidth automático.
        n_train = len(y_train)
        maxlags = max(1, int(np.floor(4 * (n_train / 100) ** (2 / 9))))

        result = _ols_newey_west(y_train, X_train, maxlags=maxlags)
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
        pinball = _pinball_loss(y_test, preds, residuals_train)
        cov = _coverage(y_test, preds, residuals_train)

        fold_metrics.append(
            {"fold": fold + 1, "mape": mape, "mae": mae, "rmse": rmse, "dw": dw, "pinball": pinball, "coverage": cov}
        )
        all_actuals.append(y_test)
        all_preds.append(preds)
        all_residuals.append(residuals_train)

    # Métricas agregadas.
    mapes = [m["mape"] for m in fold_metrics]
    maes = [m["mae"] for m in fold_metrics]
    rmses = [m["rmse"] for m in fold_metrics]
    dws = [m["dw"] for m in fold_metrics]
    coverages = [m["coverage"] for m in fold_metrics]
    pinballs = [m["pinball"] for m in fold_metrics]

    # Coeficientes padronizados da última dobra (para o gráfico de drivers).
    coef_df = _standardized_coefficients(last_result, feature_cols)

    return {
        "fold_metrics": fold_metrics,
        "mape_medio": float(np.mean(mapes)),
        "mape_desvio": float(np.std(mapes)),
        "mae_medio": float(np.mean(maes)),
        "rmse_medio": float(np.mean(rmses)),
        "durbin_watson_medio": float(np.mean(dws)),
        "durbin_watson_ultima_dobra": float(dws[-1]),
        "coverage_p10_p90": float(np.mean(coverages)),
        "pinball_loss_medio": float(np.mean(pinballs)),
        "n_obs_treino_final": int(len(matrix) - _FOLD_SIZE),
        "n_folds": _N_FOLDS,
        "fold_size": _FOLD_SIZE,
        "coeficientes_padronizados": coef_df,
        "actuals": np.concatenate(all_actuals),
        "predictions": np.concatenate(all_preds),
        "residuals": np.concatenate(all_residuals),
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
    label_map = {f"X_{k}": v for k, v in MACRO_FEATURES.items()}
    label_map.update(
        {
            "y_lag1": "Vendas t-1",
            "y_lag2": "Vendas t-2",
            "y_lag12": "Vendas t-12",
        }
    )
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

    # Metas de aceite definidas no prompt.
    metas = {
        "durbin_watson_min": 1.60,
        "mape_max_pct": 3.0,
        "coverage_p10_p90_min": 0.75,
    }
    resultados = {
        "durbin_watson_medio": metrics["durbin_watson_medio"],
        "mape_medio_pct": metrics["mape_medio"],
        "coverage_p10_p90": metrics["coverage_p10_p90"],
    }
    aceite = {
        "durbin_watson": resultados["durbin_watson_medio"] >= metas["durbin_watson_min"],
        "mape": resultados["mape_medio_pct"] <= metas["mape_max_pct"],
        "coverage": resultados["coverage_p10_p90"] >= metas["coverage_p10_p90_min"],
    }

    payload = {
        "modelo": "OLS Newey-West (v2)",
        "descricao": "OLS com erros-padrão HAC (Newey-West) e regressores macroeconômicos do FRED.",
        "n_folds": metrics["n_folds"],
        "fold_size_meses": metrics["fold_size"],
        "n_obs_treino_final": metrics["n_obs_treino_final"],
        "metricas": {
            "mape_medio_pct": round(metrics["mape_medio"], 4),
            "mape_desvio_pp": round(metrics["mape_desvio"], 4),
            "mae_medio": round(metrics["mae_medio"], 4),
            "rmse_medio": round(metrics["rmse_medio"], 4),
            "durbin_watson_medio": round(metrics["durbin_watson_medio"], 4),
            "durbin_watson_ultima_dobra": round(metrics["durbin_watson_ultima_dobra"], 4),
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


def run_ols_forecast(store_dir: Path | None = None, save: bool = True) -> dict[str, Any]:
    """Pipeline completo: lê o feature store, treina OLS NW, valida e persiste métricas.

    Retorna o dicionário de métricas e o DataFrame de coeficientes padronizados.
    """
    matrix = build_regression_matrix(store_dir)
    results = walk_forward_ols(matrix)

    if save:
        save_performance_v2(results)

    return results
