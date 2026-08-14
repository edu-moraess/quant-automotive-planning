"""Forecast engine modular com benchmarks e validação walk-forward por horizonte.

A regressão de defasagem permanece o candidato principal quando validada fora da
amostra. Seasonal Naive, Holt-Winters e AutoReg são benchmarks comparativos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from statsmodels.tsa.ar_model import AutoReg
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from config import FORECAST_DEFAULTS

TARGET_COLUMN = "vendas_saar_milhoes"
DATE_COLUMN = "data"
PRIMARY_MODEL = "Regressão com defasagens"
BENCHMARK_MODELS = ("Seasonal Naive", "Holt-Winters", "AutoReg")
MODEL_NAMES = (PRIMARY_MODEL, *BENCHMARK_MODELS)


class ForecastModel(Protocol):
    """Contrato mínimo comum a modelos de forecast."""

    name: str

    def fit(self, frame: pd.DataFrame) -> ForecastModel: ...

    def predict(self, horizon: int, dates: pd.DatetimeIndex | None = None) -> np.ndarray: ...

    def forecast(self, horizon: int) -> np.ndarray: ...

    def evaluate(self, actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]: ...

    def diagnostics(self) -> dict[str, Any]: ...


@dataclass
class BaseForecastModel:
    """Base reutilizável com validação e métricas comuns."""

    name: str
    fitted_: bool = field(default=False, init=False)
    training_end_: pd.Timestamp | None = field(default=None, init=False)
    n_training_: int = field(default=0, init=False)

    def _validate_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        required = {DATE_COLUMN, TARGET_COLUMN}
        if not required.issubset(frame.columns):
            raise ValueError(f"{self.name}: colunas obrigatórias ausentes: {sorted(required - set(frame.columns))}")
        prepared = frame[[DATE_COLUMN, TARGET_COLUMN]].copy()
        prepared[DATE_COLUMN] = (
            pd.to_datetime(prepared[DATE_COLUMN], errors="coerce").dt.to_period("M").dt.to_timestamp()
        )
        prepared[TARGET_COLUMN] = pd.to_numeric(prepared[TARGET_COLUMN], errors="coerce")
        prepared = prepared.dropna().sort_values(DATE_COLUMN).drop_duplicates(DATE_COLUMN, keep="last")
        if prepared.empty or not np.isfinite(prepared[TARGET_COLUMN]).all():
            raise ValueError(f"{self.name}: série de treino vazia ou não finita.")
        return prepared.reset_index(drop=True)

    def _mark_fitted(self, frame: pd.DataFrame) -> None:
        self.fitted_ = True
        self.training_end_ = frame[DATE_COLUMN].max()
        self.n_training_ = len(frame)

    def _require_fitted(self) -> None:
        if not self.fitted_:
            raise RuntimeError(f"{self.name}: execute fit() antes de forecast().")

    def predict(self, horizon: int, dates: pd.DatetimeIndex | None = None) -> np.ndarray:
        del dates
        return self.forecast(horizon)

    def evaluate(self, actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
        real = np.asarray(actual, dtype=float)
        estimate = np.asarray(predicted, dtype=float)
        if real.ndim != 1 or estimate.ndim != 1 or len(real) == 0 or len(real) != len(estimate):
            raise ValueError(f"{self.name}: actual e predicted devem ser vetores de mesmo tamanho.")
        if not np.isfinite(real).all() or not np.isfinite(estimate).all():
            raise ValueError(f"{self.name}: actual e predicted não podem conter NaN ou infinito.")
        error = real - estimate
        denominator = np.maximum(np.abs(real), 1e-12)
        smape_denominator = np.maximum(np.abs(real) + np.abs(estimate), 1e-12)
        naive_scale = np.mean(np.abs(np.diff(real))) if len(real) > 1 else np.nan
        return {
            "RMSE": float(np.sqrt(np.mean(error**2))),
            "MAE": float(np.mean(np.abs(error))),
            "WAPE": float(np.sum(np.abs(error)) / max(np.sum(np.abs(real)), 1e-12) * 100),
            "sMAPE": float(np.mean(2 * np.abs(error) / smape_denominator) * 100),
            "MASE": float(np.mean(np.abs(error)) / naive_scale) if naive_scale > 1e-12 else float("nan"),
            "MAPE": float(np.mean(np.abs(error) / denominator) * 100),
            "Bias": float(np.mean(error)),
        }

    def diagnostics(self) -> dict[str, Any]:
        return {
            "model_name": self.name,
            "fitted": self.fitted_,
            "training_end": self.training_end_,
            "n_training": self.n_training_,
        }


@dataclass
class LaggedRegressionModel(BaseForecastModel):
    """Regressão de defasagens, modelo principal do pipeline."""

    name: str = PRIMARY_MODEL
    alpha: float = FORECAST_DEFAULTS.ridge_alpha
    lags: tuple[int, ...] = (1, 12)
    model_: Ridge | None = field(default=None, init=False)
    history_: pd.DataFrame | None = field(default=None, init=False)

    def fit(self, frame: pd.DataFrame) -> LaggedRegressionModel:
        prepared = self._validate_frame(frame)
        if len(prepared) < max(self.lags) + 12:
            raise ValueError(f"{self.name}: histórico insuficiente para os lags {self.lags}.")
        prepared["mes"] = prepared[DATE_COLUMN].dt.month
        features = self._features(prepared)
        usable = features.dropna()
        columns = self._feature_columns()
        self.model_ = Ridge(alpha=self.alpha).fit(usable[columns], usable[TARGET_COLUMN])
        self.history_ = prepared[[DATE_COLUMN, TARGET_COLUMN, "mes"]].copy()
        self._mark_fitted(prepared)
        return self

    def forecast(self, horizon: int) -> np.ndarray:
        self._require_fitted()
        if horizon < 1:
            raise ValueError("O horizonte deve ser positivo.")
        assert self.model_ is not None and self.history_ is not None
        history = self.history_.copy()
        predictions: list[float] = []
        for _ in range(horizon):
            next_date = history[DATE_COLUMN].max() + pd.offsets.MonthBegin(1)
            row = {f"lag_{lag}": history[TARGET_COLUMN].iloc[-lag] for lag in self.lags}
            row["tendencia"] = len(history)
            row.update({f"mes_{month}": float(next_date.month == month) for month in range(2, 13)})
            prediction = float(self.model_.predict(pd.DataFrame([row])[self._feature_columns()])[0])
            predictions.append(prediction)
            history = pd.concat(
                [
                    history,
                    pd.DataFrame({DATE_COLUMN: [next_date], TARGET_COLUMN: [prediction], "mes": [next_date.month]}),
                ],
                ignore_index=True,
            )
        return np.asarray(predictions, dtype=float)

    def _features(self, frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()
        for lag in self.lags:
            result[f"lag_{lag}"] = result[TARGET_COLUMN].shift(lag)
        result["tendencia"] = np.arange(len(result))
        dummies = pd.get_dummies(result["mes"], prefix="mes", drop_first=True).astype(float)
        for month in range(2, 13):
            column = f"mes_{month}"
            if column not in dummies.columns:
                dummies[column] = 0.0
        return pd.concat([result, dummies], axis=1)

    def _feature_columns(self) -> list[str]:
        return [*(f"lag_{lag}" for lag in self.lags), "tendencia", *[f"mes_{month}" for month in range(2, 13)]]

    def diagnostics(self) -> dict[str, Any]:
        return {**super().diagnostics(), "lags": list(self.lags), "alpha": self.alpha, "role": "primary"}


@dataclass
class SeasonalNaiveModel(BaseForecastModel):
    """Benchmark sazonal que usa a média histórica por mês."""

    name: str = "Seasonal Naive"
    monthly_means_: pd.Series | None = field(default=None, init=False)
    fallback_: float | None = field(default=None, init=False)

    def fit(self, frame: pd.DataFrame) -> SeasonalNaiveModel:
        prepared = self._validate_frame(frame)
        self.monthly_means_ = prepared.assign(mes=prepared[DATE_COLUMN].dt.month).groupby("mes")[TARGET_COLUMN].mean()
        self.fallback_ = float(prepared[TARGET_COLUMN].mean())
        self._mark_fitted(prepared)
        return self

    def forecast(self, horizon: int) -> np.ndarray:
        self._require_fitted()
        assert self.training_end_ is not None and self.monthly_means_ is not None and self.fallback_ is not None
        dates = pd.date_range(self.training_end_ + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
        return np.asarray([self.monthly_means_.get(date.month, self.fallback_) for date in dates], dtype=float)


@dataclass
class HoltWintersModel(BaseForecastModel):
    """Benchmark Holt-Winters aditivo com sazonalidade mensal."""

    name: str = "Holt-Winters"
    fitted_model_: Any = field(default=None, init=False)

    def fit(self, frame: pd.DataFrame) -> HoltWintersModel:
        prepared = self._validate_frame(frame)
        self.fitted_model_ = ExponentialSmoothing(
            prepared[TARGET_COLUMN],
            trend="add",
            seasonal="add",
            seasonal_periods=FORECAST_DEFAULTS.seasonal_periods,
            initialization_method="estimated",
        ).fit(optimized=True)
        self._mark_fitted(prepared)
        return self

    def forecast(self, horizon: int) -> np.ndarray:
        self._require_fitted()
        assert self.fitted_model_ is not None
        return np.asarray(self.fitted_model_.forecast(horizon), dtype=float)


@dataclass
class AutoRegModel(BaseForecastModel):
    """Benchmark AutoReg sazonal com tendência e 12 defasagens."""

    name: str = "AutoReg"
    fitted_model_: Any = field(default=None, init=False)
    lags: int = FORECAST_DEFAULTS.autoreg_lags

    def fit(self, frame: pd.DataFrame) -> AutoRegModel:
        prepared = self._validate_frame(frame)
        values = prepared[TARGET_COLUMN].to_numpy(dtype=float)
        self.fitted_model_ = AutoReg(
            values,
            lags=self.lags,
            trend="ct",
            seasonal=True,
            period=FORECAST_DEFAULTS.seasonal_periods,
            old_names=False,
        ).fit()
        self._mark_fitted(prepared)
        return self

    def forecast(self, horizon: int) -> np.ndarray:
        self._require_fitted()
        assert self.fitted_model_ is not None
        return np.asarray(
            self.fitted_model_.predict(start=self.n_training_, end=self.n_training_ + horizon - 1), dtype=float
        )


def build_model_registry() -> dict[str, ForecastModel]:
    """Cria candidatos sem compartilhar estado entre dobras do backtest."""
    return {
        PRIMARY_MODEL: LaggedRegressionModel(),
        "Seasonal Naive": SeasonalNaiveModel(),
        "Holt-Winters": HoltWintersModel(),
        "AutoReg": AutoRegModel(),
    }


def walk_forward_by_horizon(
    data: pd.DataFrame,
    *,
    horizons: tuple[int, ...] = (1, 3, 6, 12),
    n_origins: int = 4,
) -> pd.DataFrame:
    """Avalia todos os candidatos por origem e horizonte sem usar observações futuras."""
    if not horizons or any(horizon < 1 for horizon in horizons):
        raise ValueError("Os horizontes devem ser positivos e não vazios.")
    if n_origins < 1:
        raise ValueError("n_origins deve ser positivo.")
    prepared = BaseForecastModel("validation")._validate_frame(data)
    max_horizon = max(horizons)
    first_origin = len(prepared) - n_origins - max_horizon + 1
    if first_origin < max(24, max_horizon + 12):
        raise ValueError("Histórico insuficiente para walk-forward por horizonte.")

    rows: list[dict[str, Any]] = []
    for origin_offset in range(n_origins):
        origin = first_origin + origin_offset
        train = prepared.iloc[:origin].copy()
        future = prepared.iloc[origin : origin + max_horizon].copy()
        fitted_models: dict[str, ForecastModel] = {}
        for name, model in build_model_registry().items():
            try:
                fitted_models[name] = model.fit(train)
            except Exception as error:
                for horizon in horizons:
                    rows.append(
                        {
                            "model": name,
                            "origin": train[DATE_COLUMN].max(),
                            "horizon": horizon,
                            "status": "failed",
                            "error": type(error).__name__,
                        }
                    )
        for name, model in fitted_models.items():
            try:
                prediction = model.forecast(max_horizon)
                for horizon in horizons:
                    metrics = model.evaluate(
                        future[TARGET_COLUMN].to_numpy(dtype=float)[:horizon], prediction[:horizon]
                    )
                    rows.append(
                        {
                            "model": name,
                            "origin": train[DATE_COLUMN].max(),
                            "horizon": horizon,
                            "status": "ok",
                            **metrics,
                        }
                    )
            except Exception as error:
                for horizon in horizons:
                    rows.append(
                        {
                            "model": name,
                            "origin": train[DATE_COLUMN].max(),
                            "horizon": horizon,
                            "status": "failed",
                            "error": type(error).__name__,
                        }
                    )
    result = pd.DataFrame(rows)
    if result.empty or not result["status"].eq("ok").any():
        raise RuntimeError("Nenhum candidato gerou avaliação válida por horizonte.")
    return result


def aggregate_horizon_metrics(results: pd.DataFrame) -> pd.DataFrame:
    """Agrega métricas por modelo e horizonte para seleção baseada fora da amostra."""
    valid = results.loc[results["status"].eq("ok")].copy()
    if valid.empty:
        return pd.DataFrame()
    return (
        valid.groupby(["model", "horizon"], as_index=False)
        .agg(
            RMSE=("RMSE", "mean"),
            MAE=("MAE", "mean"),
            WAPE=("WAPE", "mean"),
            sMAPE=("sMAPE", "mean"),
            MASE=("MASE", "mean"),
            MAPE=("MAPE", "mean"),
            Bias=("Bias", "mean"),
            valid_origins=("origin", "nunique"),
        )
        .sort_values(["horizon", "MAPE", "RMSE"])
        .reset_index(drop=True)
    )


def select_model_by_evidence(
    summary: pd.DataFrame,
    *,
    primary_model: str = PRIMARY_MODEL,
    tolerance_mape_pp: float = FORECAST_DEFAULTS.selection_tolerance_mape_pp,
) -> str:
    """Seleciona por métricas OOS e prioriza a regressão principal apenas em empate estatístico."""
    if summary.empty or not {"model", "MAPE"}.issubset(summary.columns):
        raise ValueError("Resumo de modelos precisa conter model e MAPE.")
    valid = summary.dropna(subset=["MAPE"]).sort_values(["MAPE", "RMSE" if "RMSE" in summary else "MAPE"])
    if valid.empty:
        raise ValueError("Nenhum modelo possui métricas válidas.")
    best_mape = float(valid["MAPE"].min())
    close = valid.loc[valid["MAPE"] <= best_mape + tolerance_mape_pp]
    if primary_model in set(close["model"]):
        return primary_model
    return str(close.iloc[0]["model"])
