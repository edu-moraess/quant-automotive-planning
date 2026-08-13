"""Núcleo quantitativo do projeto de planejamento automotivo.

As funções são mantidas sem dependência do Streamlit para que possam ser testadas,
reutilizadas em notebooks e executadas em pipelines de validação.
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf  # noqa: F401
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import acf, adfuller, pacf

try:
    import pulp
except ImportError:  # pragma: no cover - mensagem tratada no uso
    pulp = None

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=TOTALSA"
FRED_SERIES_URL = "https://fred.stlouisfed.org/series/TOTALSA"
MODEL_NAMES = ["Referência sazonal", "Holt-Winters", "Regressão com defasagens"]
MONTH_NAMES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
REGRESSION_COLUMNS = ["lag_1", "lag_12", "tendencia"] + [f"mes_{month}" for month in range(2, 13)]


def read_fred_csv(source: str = FRED_CSV_URL, fallback_path: str | Path | None = None) -> tuple[pd.DataFrame, str]:
    """Lê a série oficial e usa snapshot local quando a fonte estiver indisponível."""
    try:
        raw = pd.read_csv(source)
        if not {"observation_date", "TOTALSA"}.issubset(raw.columns):
            raise ValueError("A fonte não contém as colunas esperadas.")
        return raw, "FRED — fonte online"
    except Exception as online_error:
        if fallback_path is None or not Path(fallback_path).exists():
            raise RuntimeError(
                "Não foi possível acessar o FRED e não existe snapshot local disponível. "
                f"Erro original: {online_error}"
            ) from online_error
        raw = pd.read_csv(fallback_path)
        return raw, "Snapshot local versionado"


def prepare_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Padroniza a série e calcula indicadores operacionais de qualidade."""
    required = {"observation_date", "TOTALSA"}
    if not required.issubset(raw.columns):
        raise ValueError(f"Formato inesperado. Colunas necessárias: {sorted(required)}")

    duplicate_count = int(raw["observation_date"].duplicated().sum())
    cleaned = (
        raw.rename(columns={"observation_date": "data", "TOTALSA": "vendas_saar_milhoes"})
        .assign(
            data=lambda frame: pd.to_datetime(frame["data"], errors="coerce"),
            vendas_saar_milhoes=lambda frame: pd.to_numeric(frame["vendas_saar_milhoes"], errors="coerce"),
        )
        .dropna(subset=["data", "vendas_saar_milhoes"])
        .sort_values("data")
        .drop_duplicates("data")
        .reset_index(drop=True)
    )
    cleaned["demanda_mensal_est_milhoes"] = cleaned["vendas_saar_milhoes"] / 12
    cleaned["mes"] = cleaned["data"].dt.month
    cleaned["ano"] = cleaned["data"].dt.year
    cleaned["variacao_mensal_pct"] = cleaned["vendas_saar_milhoes"].pct_change() * 100
    cleaned["variacao_anual_pct"] = cleaned["vendas_saar_milhoes"].pct_change(12) * 100

    intervals = cleaned["data"].diff().dt.days.dropna()
    irregular_intervals = int((~intervals.between(28, 31)).sum())
    missing_values = int(cleaned[["data", "vendas_saar_milhoes"]].isna().sum().sum())
    q1, q3 = cleaned["vendas_saar_milhoes"].quantile([0.25, 0.75])
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = cleaned[
        (cleaned["vendas_saar_milhoes"] < lower) | (cleaned["vendas_saar_milhoes"] > upper)
    ].copy()

    quality = {
        "duplicidades_brutas": duplicate_count,
        "valores_ausentes": missing_values,
        "intervalos_irregulares": irregular_intervals,
        "outliers_iqr": int(len(outliers)),
        "limite_iqr_inferior": float(lower),
        "limite_iqr_superior": float(upper),
        "observacoes": int(len(cleaned)),
        "data_inicial": cleaned["data"].min(),
        "data_final": cleaned["data"].max(),
        "outliers": outliers,
    }
    return cleaned, quality


def compute_diagnostics(data: pd.DataFrame) -> dict[str, Any]:
    """Calcula ADF, STL, perfil sazonal, ACF e PACF."""
    series = data["vendas_saar_milhoes"].astype(float).dropna()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        adf_level = adfuller(series, autolag="AIC")
        adf_diff = adfuller(series.diff().dropna(), autolag="AIC")
        stl_result = STL(data.set_index("data")["vendas_saar_milhoes"], period=12, robust=True).fit()
        acf_values = acf(series, nlags=min(36, len(series) // 2 - 1), fft=True)
        pacf_values = pacf(series, nlags=min(36, len(series) // 2 - 1), method="ywm")

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
        "adf_level": {"statistic": float(adf_level[0]), "pvalue": float(adf_level[1])},
        "adf_diff": {"statistic": float(adf_diff[0]), "pvalue": float(adf_diff[1])},
        "stl": stl,
        "seasonal_profile": seasonal_profile,
        "acf": pd.DataFrame({"lag": np.arange(len(acf_values)), "acf": acf_values}),
        "pacf": pd.DataFrame({"lag": np.arange(len(pacf_values)), "pacf": pacf_values}),
    }


def metricas(y_real: np.ndarray, y_previsto: np.ndarray) -> dict[str, float]:
    """Calcula MAE, RMSE e MAPE."""
    real = np.asarray(y_real, dtype=float)
    predicted = np.asarray(y_previsto, dtype=float)
    denominator = np.where(np.abs(real) < 1e-12, 1e-12, np.abs(real))
    return {
        "MAE (milhões SAAR)": float(np.mean(np.abs(real - predicted))),
        "RMSE (milhões SAAR)": float(np.sqrt(np.mean((real - predicted) ** 2))),
        "MAPE (%)": float(np.mean(np.abs((real - predicted) / denominator)) * 100),
    }


def construir_dobras(data: pd.DataFrame, n_dobras: int = 4, tamanho_dobra: int = 6) -> list[tuple[slice, slice]]:
    """Gera pares de treino/teste para validação walk-forward expansiva."""
    if n_dobras < 1 or tamanho_dobra < 1:
        raise ValueError("O número e o tamanho das dobras devem ser positivos.")
    n = len(data)
    inicio_teste = n - n_dobras * tamanho_dobra
    if inicio_teste < 24:
        raise ValueError("O histórico precisa ter pelo menos 24 observações antes do primeiro teste.")
    return [
        (slice(0, inicio_teste + k * tamanho_dobra), slice(inicio_teste + k * tamanho_dobra, inicio_teste + (k + 1) * tamanho_dobra))
        for k in range(n_dobras)
    ]


def prever_sazonal_naive(treino: pd.DataFrame, datas_teste: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    """Previsão pela média histórica do mesmo mês, estimada apenas no treino."""
    monthly_means = treino.groupby(treino["data"].dt.month)["vendas_saar_milhoes"].mean()
    fallback = float(treino["vendas_saar_milhoes"].mean())
    return np.array([monthly_means.get(date.month, fallback) for date in pd.to_datetime(datas_teste)])


def prever_holt_winters(treino: pd.DataFrame, n_periodos: int) -> np.ndarray:
    """Holt-Winters aditivo com sazonalidade anual."""
    model = ExponentialSmoothing(
        treino["vendas_saar_milhoes"], trend="add", seasonal="add", seasonal_periods=12, initialization_method="estimated"
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
    """Ridge com lags 1/12 e previsão recursiva multi-passo."""
    train_features = construir_features_regressao(treino).dropna(subset=REGRESSION_COLUMNS + ["vendas_saar_milhoes"])
    model = Ridge(alpha=1.0)
    model.fit(train_features[REGRESSION_COLUMNS], train_features["vendas_saar_milhoes"])
    history = treino[["data", "vendas_saar_milhoes", "mes"]].copy()
    predictions: list[float] = []
    for _ in range(n_periodos):
        next_date = history["data"].max() + pd.offsets.MonthBegin(1)
        row = {
            "lag_1": history["vendas_saar_milhoes"].iloc[-1],
            "lag_12": history["vendas_saar_milhoes"].iloc[-12],
            "tendencia": len(history),
        }
        row.update({f"mes_{month}": 1.0 if next_date.month == month else 0.0 for month in range(2, 13)})
        prediction = float(model.predict(pd.DataFrame([row])[REGRESSION_COLUMNS])[0])
        predictions.append(prediction)
        history = pd.concat(
            [history, pd.DataFrame({"data": [next_date], "vendas_saar_milhoes": [prediction], "mes": [next_date.month]})],
            ignore_index=True,
        )
    return np.asarray(predictions)


def run_backtest(data: pd.DataFrame, n_dobras: int = 4, tamanho_dobra: int = 6) -> dict[str, Any]:
    """Executa backtest, resume erros e coleta previsões fora da amostra."""
    folds = construir_dobras(data, n_dobras, tamanho_dobra)
    records: list[dict[str, Any]] = []
    predictions_by_model: dict[str, list[np.ndarray]] = {model: [] for model in MODEL_NAMES}
    actuals_by_fold: list[np.ndarray] = []
    fold_details: list[dict[str, Any]] = []

    for fold_number, (train_idx, test_idx) in enumerate(folds, start=1):
        train = data.iloc[train_idx].reset_index(drop=True)
        test = data.iloc[test_idx].reset_index(drop=True)
        period = f"{test['data'].min():%m/%Y}–{test['data'].max():%m/%Y}"
        actual = test["vendas_saar_milhoes"].to_numpy()
        model_predictions = {
            "Referência sazonal": prever_sazonal_naive(train, test["data"]),
            "Holt-Winters": prever_holt_winters(train, len(test)),
            "Regressão com defasagens": prever_regressao_defasagens(train, len(test)),
        }
        actuals_by_fold.append(actual)
        fold_details.append({"dobra": fold_number, "periodo": period, "treino_ate": train["data"].max(), "teste_de": test["data"].min(), "teste_ate": test["data"].max()})
        for model_name, prediction in model_predictions.items():
            predictions_by_model[model_name].append(prediction)
            records.append({"dobra": fold_number, "período": period, "modelo": model_name, **metricas(actual, prediction)})

    results = pd.DataFrame(records)
    summary = (
        results.groupby("modelo")["MAPE (%)"]
        .agg(mape_medio="mean", mape_desvio="std")
        .sort_values("mape_medio")
        .reset_index()
    )
    winner = str(summary.iloc[0]["modelo"])
    actuals = np.concatenate(actuals_by_fold)
    winner_predictions = np.concatenate(predictions_by_model[winner])
    residuals = actuals - winner_predictions
    ljung_box = acorr_ljungbox(residuals, lags=[6, 12], return_df=True).reset_index(names="lag")
    residual_acf_values = acf(residuals, nlags=min(11, len(residuals) - 1), fft=True)
    residual_acf = pd.DataFrame({"lag": np.arange(len(residual_acf_values)), "acf": residual_acf_values})
    return {
        "results": results,
        "summary": summary,
        "winner": winner,
        "predictions_by_model": predictions_by_model,
        "actuals": actuals,
        "winner_predictions": winner_predictions,
        "residuals": residuals,
        "ljung_box": ljung_box,
        "residual_acf": residual_acf,
        "fold_details": pd.DataFrame(fold_details),
    }


def make_forecast(data: pd.DataFrame, backtest: dict[str, Any], horizon: int = 6, bootstrap_replicas: int = 2000, seed: int = 42) -> tuple[pd.DataFrame, np.ndarray]:
    """Reestima o vencedor e produz cenários empíricos p10/base/p90."""
    winner = backtest["winner"]
    future_dates = pd.date_range(data["data"].max() + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    if winner == "Holt-Winters":
        point_forecast = prever_holt_winters(data, horizon)
    elif winner == "Regressão com defasagens":
        point_forecast = prever_regressao_defasagens(data, horizon)
    else:
        point_forecast = prever_sazonal_naive(data, future_dates)

    rng = np.random.default_rng(seed)
    residuals = np.asarray(backtest["residuals"], dtype=float)
    bootstrap_errors = rng.choice(residuals, size=(bootstrap_replicas, horizon), replace=True)
    simulations = point_forecast[None, :] + bootstrap_errors
    forecast = pd.DataFrame(
        {
            "data": future_dates,
            "cenario_conservador": np.maximum(np.percentile(simulations, 10, axis=0), 0),
            "cenario_base": point_forecast,
            "cenario_otimista": np.maximum(np.percentile(simulations, 90, axis=0), 0),
        }
    )
    forecast["demanda_mensal_base_milhoes"] = forecast["cenario_base"] / 12
    return forecast, simulations


def converter_demanda_veiculos(scenario_millions_saar: pd.Series, participation: float) -> pd.Series:
    """Converte SAAR em unidades mensais de uma carteira hipotética."""
    return (scenario_millions_saar / 12 * 1_000_000 * participation).round().astype(int)


def resolver_plano_producao(
    demanda: np.ndarray,
    capacidade: int,
    estoque_inicial: int,
    custo_producao: float,
    custo_estoque: float,
    custo_ruptura: float,
    nome: str = "plano",
) -> dict[str, Any]:
    """Resolve a programação linear de produção, estoque e backlog."""
    if pulp is None:
        raise RuntimeError("A dependência PuLP não está instalada.")
    periods = list(range(len(demanda)))
    problem = pulp.LpProblem(f"Planejamento_{nome}", pulp.LpMinimize)
    production = pulp.LpVariable.dicts("producao", periods, lowBound=0, upBound=capacidade, cat="Continuous")
    inventory = pulp.LpVariable.dicts("estoque", periods, lowBound=0, cat="Continuous")
    backlog = pulp.LpVariable.dicts("backlog", periods, lowBound=0, cat="Continuous")
    problem += pulp.lpSum(custo_producao * production[t] + custo_estoque * inventory[t] + custo_ruptura * backlog[t] for t in periods)
    for t in periods:
        previous_inventory = estoque_inicial if t == 0 else inventory[t - 1]
        previous_backlog = 0 if t == 0 else backlog[t - 1]
        problem += inventory[t] - backlog[t] == previous_inventory - previous_backlog + production[t] - float(demanda[t]), f"balanco_{t}"
    status = problem.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"Otimização não encontrou solução ótima: {pulp.LpStatus[status]}")
    return {
        "status": pulp.LpStatus[status],
        "producao": [round(pulp.value(production[t])) for t in periods],
        "estoque": [round(pulp.value(inventory[t])) for t in periods],
        "backlog": [round(pulp.value(backlog[t])) for t in periods],
        "custo_total": float(pulp.value(problem.objective)),
    }


def build_production_plan(forecast: pd.DataFrame, participation: float, capacity: int, initial_inventory: int, production_cost: float, inventory_cost: float, backlog_cost: float) -> dict[str, Any]:
    """Calcula plano base, comparação de cenários e mapa de sensibilidade."""
    plan = forecast[["data", "cenario_conservador", "cenario_base", "cenario_otimista"]].copy()
    plan["demanda_planejada_veiculos"] = converter_demanda_veiculos(plan["cenario_base"], participation)
    base_solution = resolver_plano_producao(plan["demanda_planejada_veiculos"].to_numpy(), capacity, initial_inventory, production_cost, inventory_cost, backlog_cost, "cenario_base")
    plan["producao_recomendada"] = base_solution["producao"]
    plan["estoque_final"] = base_solution["estoque"]
    plan["demanda_pendente"] = base_solution["backlog"]
    plan["utilizacao_capacidade_pct"] = plan["producao_recomendada"] / capacity * 100

    scenario_rows: list[dict[str, Any]] = []
    scenario_solutions: dict[str, dict[str, Any]] = {}
    scenario_columns = [("Conservador", "cenario_conservador"), ("Base", "cenario_base"), ("Otimista", "cenario_otimista")]
    for scenario_name, column in scenario_columns:
        demand = converter_demanda_veiculos(plan[column], participation)
        solution = resolver_plano_producao(demand.to_numpy(), capacity, initial_inventory, production_cost, inventory_cost, backlog_cost, scenario_name)
        scenario_solutions[scenario_name] = solution
        scenario_rows.append(
            {
                "Cenário": scenario_name,
                "Demanda total (veículos)": int(demand.sum()),
                "Produção total (veículos)": int(sum(solution["producao"])),
                "Utilização média (%)": float(np.mean(solution["producao"]) / capacity * 100),
                "Demanda pendente final": int(solution["backlog"][-1]),
                "Custo total (US$)": float(solution["custo_total"]),
            }
        )
    scenarios = pd.DataFrame(scenario_rows)

    capacity_grid = [round(capacity * factor) for factor in (0.8, 0.9, 1.0, 1.1, 1.2)]
    participation_grid = [0.06, 0.08, 0.10]
    sensitivity = pd.DataFrame(index=capacity_grid, columns=participation_grid, dtype=float)
    for grid_capacity in capacity_grid:
        for grid_participation in participation_grid:
            grid_demand = converter_demanda_veiculos(plan["cenario_base"], grid_participation)
            grid_solution = resolver_plano_producao(grid_demand.to_numpy(), grid_capacity, initial_inventory, production_cost, inventory_cost, backlog_cost, f"grade_{grid_capacity}_{grid_participation}")
            sensitivity.loc[grid_capacity, grid_participation] = sum(grid_solution["backlog"])
    sensitivity.index.name = "Capacidade mensal"
    sensitivity.columns.name = "Participação de mercado"
    return {"plan": plan, "base_solution": base_solution, "scenarios": scenarios, "sensitivity": sensitivity, "scenario_solutions": scenario_solutions}


def run_full_analysis(
    fallback_path: str | Path,
    n_folds: int = 4,
    test_size: int = 6,
    horizon: int = 6,
    bootstrap_replicas: int = 2000,
    seed: int = 42,
    participation: float = 0.08,
    capacity: int = 110_000,
    initial_inventory: int = 15_000,
    production_cost: float = 25_000,
    inventory_cost: float = 350,
    backlog_cost: float = 45_000,
    source_url: str = FRED_CSV_URL,
) -> dict[str, Any]:
    """Executa o fluxo completo da aplicação."""
    raw, source_label = read_fred_csv(source_url, fallback_path)
    data, quality = prepare_data(raw)
    diagnostics = compute_diagnostics(data)
    backtest = run_backtest(data, n_folds, test_size)
    forecast, simulations = make_forecast(data, backtest, horizon, bootstrap_replicas, seed)
    production = build_production_plan(forecast, participation, capacity, initial_inventory, production_cost, inventory_cost, backlog_cost)
    return {
        "raw": raw,
        "source_label": source_label,
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
        },
    }
