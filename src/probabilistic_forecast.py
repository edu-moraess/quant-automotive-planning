"""Forecast probabilístico baseado exclusivamente em resíduos out-of-sample."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import t as student_t


@dataclass(frozen=True)
class ProbabilisticForecastConfig:
    """Parâmetros reprodutíveis da camada de incerteza."""

    replicas: int = 2_000
    seed: int = 42
    block_size: int = 3
    quantiles: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75, 0.90)
    candidate_methods: tuple[str, ...] = ("normal", "student_t", "iid_bootstrap", "moving_block")


@dataclass(frozen=True)
class ProbabilisticForecastResult:
    """Saída tabular, simulações e auditoria da escolha distributiva."""

    forecast: pd.DataFrame
    simulations: np.ndarray
    selected_method: str
    calibration: pd.DataFrame
    metadata: dict[str, Any]


def build_probabilistic_forecast(
    point_forecast: np.ndarray | pd.Series,
    oos_residuals: np.ndarray | pd.Series,
    future_dates: pd.DatetimeIndex | pd.Series,
    *,
    config: ProbabilisticForecastConfig | None = None,
    actuals_by_fold: list[np.ndarray] | None = None,
    predictions_by_fold: list[np.ndarray] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProbabilisticForecastResult:
    """Gera quantis usando resíduos OOS e escolhe o método por calibração prequential."""
    settings = config or ProbabilisticForecastConfig()
    point = _finite_vector(point_forecast, "point_forecast")
    residuals = _finite_vector(oos_residuals, "oos_residuals")
    dates = pd.DatetimeIndex(pd.to_datetime(future_dates, errors="raise"))
    if len(point) == 0 or len(point) != len(dates):
        raise ValueError("point_forecast e future_dates devem ter o mesmo tamanho não vazio.")
    if settings.replicas < 100 or settings.block_size < 1:
        raise ValueError("replicas deve ser ≥ 100 e block_size deve ser positivo.")

    calibration = calibrate_error_methods(
        actuals_by_fold or [],
        predictions_by_fold or [],
        config=settings,
    )
    selected = select_error_method(calibration, available_methods=settings.candidate_methods)
    rng = np.random.default_rng(settings.seed)
    errors = draw_errors(
        selected,
        residuals,
        replicas=settings.replicas,
        horizon=len(point),
        rng=rng,
        block_size=settings.block_size,
    )
    simulations = np.maximum(point[None, :] + errors, 0.0)
    quantiles = {
        f"p{int(quantile * 100)}": np.quantile(simulations, quantile, axis=0) for quantile in settings.quantiles
    }
    forecast = pd.DataFrame({"data": dates, **quantiles})
    forecast["cenario_conservador"] = forecast["p10"]
    forecast["cenario_base"] = forecast["p50"]
    forecast["cenario_otimista"] = forecast["p90"]
    forecast["demanda_mensal_base_milhoes"] = forecast["p50"] / 12
    forecast_metadata = {
        "model_name": (metadata or {}).get("model_name"),
        "model_version": (metadata or {}).get("model_version", "probabilistic_forecast.v1"),
        "training_period": (metadata or {}).get("training_period"),
        "forecast_origin": (metadata or {}).get("forecast_origin"),
        "forecast_horizon": len(point),
        "dataset_hash": (metadata or {}).get("dataset_hash"),
        "feature_set": (metadata or {}).get("feature_set", []),
        "parameters": {
            "replicas": settings.replicas,
            "seed": settings.seed,
            "block_size": settings.block_size,
            "quantiles": list(settings.quantiles),
            "residual_source": "walk_forward_out_of_sample",
        },
        "validation_metrics": (metadata or {}).get("validation_metrics", {}),
        "created_at_utc": datetime.now(UTC).isoformat(),
        "error_method": selected,
    }
    forecast.attrs.update(forecast_metadata)
    forecast.attrs["residual_source"] = "walk_forward_out_of_sample"
    forecast.attrs["forecast_horizon"] = len(point)
    forecast.attrs["bootstrap_method"] = selected
    forecast.attrs["bootstrap_block_size"] = settings.block_size if selected == "moving_block" else None
    return ProbabilisticForecastResult(forecast, simulations, selected, calibration, forecast_metadata)


def calibrate_error_methods(
    actuals_by_fold: list[np.ndarray],
    predictions_by_fold: list[np.ndarray],
    *,
    config: ProbabilisticForecastConfig | None = None,
) -> pd.DataFrame:
    """Compara métodos usando apenas resíduos de dobras anteriores à dobra avaliada."""
    settings = config or ProbabilisticForecastConfig()
    if len(actuals_by_fold) != len(predictions_by_fold):
        raise ValueError("actuals_by_fold e predictions_by_fold devem ter o mesmo número de dobras.")
    rows: list[dict[str, Any]] = []
    for method in settings.candidate_methods:
        pool: list[float] = []
        fold_scores: list[dict[str, float]] = []
        for fold_index, (actual, prediction) in enumerate(zip(actuals_by_fold, predictions_by_fold, strict=True)):
            real = _finite_vector(actual, "actual_fold")
            estimate = _finite_vector(prediction, "prediction_fold")
            if len(real) != len(estimate):
                raise ValueError("Cada dobra precisa ter actual e prediction do mesmo tamanho.")
            if pool:
                rng = np.random.default_rng(settings.seed + fold_index)
                simulated = draw_errors(
                    method,
                    np.asarray(pool),
                    replicas=min(settings.replicas, 1_000),
                    horizon=len(real),
                    rng=rng,
                    block_size=settings.block_size,
                )
                error_quantiles = np.quantile(simulated, [0.10, 0.50, 0.90], axis=0)
                lower, median, upper = estimate + error_quantiles
                coverage = float(np.mean((real >= lower) & (real <= upper)))
                pinball = _pinball_loss(real, estimate, error_quantiles)
                fold_scores.append({"coverage": coverage, "pinball_loss": pinball})
            pool.extend((real - estimate).tolist())
        if fold_scores:
            coverage = float(np.mean([score["coverage"] for score in fold_scores]))
            pinball = float(np.mean([score["pinball_loss"] for score in fold_scores]))
            rows.append(
                {
                    "method": method,
                    "coverage_p10_p90": coverage,
                    "pinball_loss": pinball,
                    "coverage_gap": abs(coverage - 0.80),
                    "score": pinball + abs(coverage - 0.80),
                    "folds_scored": len(fold_scores),
                }
            )
    return pd.DataFrame(rows).sort_values("score").reset_index(drop=True) if rows else pd.DataFrame()


def select_error_method(calibration: pd.DataFrame, *, available_methods: tuple[str, ...]) -> str:
    """Seleciona o método com menor score de calibração; moving block é fallback conservador."""
    if calibration.empty:
        return "moving_block" if "moving_block" in available_methods else available_methods[0]
    valid = calibration.loc[calibration["method"].isin(available_methods)].dropna(subset=["score"])
    if valid.empty:
        return "moving_block" if "moving_block" in available_methods else available_methods[0]
    return str(valid.sort_values(["score", "pinball_loss"]).iloc[0]["method"])


def draw_errors(
    method: str,
    residuals: np.ndarray,
    *,
    replicas: int,
    horizon: int,
    rng: np.random.Generator,
    block_size: int,
) -> np.ndarray:
    """Amostra caminhos de erro a partir de uma distribuição ajustada somente em resíduos OOS."""
    values = _finite_vector(residuals, "residuals")
    if len(values) < 2:
        raise ValueError("São necessários pelo menos dois resíduos OOS.")
    if method == "normal":
        scale = float(np.std(values, ddof=1))
        if scale <= 1e-12:
            return np.full((replicas, horizon), float(np.mean(values)))
        return rng.normal(float(np.mean(values)), scale, size=(replicas, horizon))
    if method == "student_t":
        degrees, location, scale = student_t.fit(values)
        if not np.isfinite([degrees, location, scale]).all() or scale <= 1e-12:
            return rng.choice(values, size=(replicas, horizon), replace=True)
        return student_t.rvs(degrees, loc=location, scale=scale, size=(replicas, horizon), random_state=rng)
    if method == "iid_bootstrap":
        return rng.choice(values, size=(replicas, horizon), replace=True)
    if method == "moving_block":
        return _moving_block(values, replicas, horizon, block_size, rng)
    raise ValueError(f"Método de erro não suportado: {method}")


def _moving_block(
    values: np.ndarray,
    replicas: int,
    horizon: int,
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if len(values) <= block_size:
        return rng.choice(values, size=(replicas, horizon), replace=True)
    blocks = int(np.ceil(horizon / block_size))
    starts = rng.integers(0, len(values) - block_size + 1, size=(replicas, blocks))
    paths = np.empty((replicas, blocks * block_size), dtype=float)
    for replica in range(replicas):
        paths[replica] = np.concatenate([values[start : start + block_size] for start in starts[replica]])
    return paths[:, :horizon]


def _pinball_loss(actual: np.ndarray, prediction: np.ndarray, error_quantiles: np.ndarray) -> float:
    losses: list[float] = []
    for quantile, residual_quantile in zip((0.10, 0.50, 0.90), error_quantiles, strict=True):
        error = actual - (prediction + residual_quantile)
        losses.append(float(np.mean(np.maximum(quantile * error, (quantile - 1) * error))))
    return float(np.mean(losses))


def _finite_vector(values: np.ndarray | pd.Series, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.ndim != 1 or not np.isfinite(result).all():
        raise ValueError(f"{name} deve ser um vetor unidimensional finito.")
    return result
