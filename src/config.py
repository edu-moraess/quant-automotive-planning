"""Parâmetros centralizados e determinísticos da plataforma."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


@dataclass(frozen=True)
class SourceSettings:
    fred_market_series: str = "TOTALSA"
    fred_energy_series: dict[str, str] = field(
        default_factory=lambda: {
            "GASREGW": "gasolina_usd_gal",
            "GASDESW": "diesel_usd_gal",
            "APU000072610": "eletricidade_usd_kwh",
        }
    )
    request_timeout_seconds: float = 15.0
    max_attempts: int = 3
    retry_backoff_seconds: float = 0.75

    @property
    def fred_market_url(self) -> str:
        return f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={self.fred_market_series}"

    def fred_energy_url(self, series_id: str) -> str:
        return f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


@dataclass(frozen=True)
class ForecastSettings:
    horizon_months: int = 6
    n_folds: int = 4
    test_size_months: int = 6
    seasonal_periods: int = 12
    autoreg_lags: int = 12
    ridge_alpha: float = 1.0
    bootstrap_replicas: int = 2000
    bootstrap_block_size: int = 3
    random_seed: int = 42
    confidence_quantiles: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75, 0.90)
    selection_tolerance_mape_pp: float = 0.15


@dataclass(frozen=True)
class PlanningAssumptions:
    participation: float = 0.08
    regular_capacity: int = 110_000
    overtime_capacity: int = 0
    initial_inventory: int = 15_000
    safety_stock: int = 0
    production_cost: float = 25_000.0
    overtime_cost: float = 30_000.0
    inventory_cost: float = 350.0
    backlog_cost: float = 45_000.0
    safety_stock_penalty: float = 1_000.0
    setup_cost: float = 0.0


SOURCES = SourceSettings()
# Atualização offline de energia: não deve aguardar a política mais longa de uma fonte indisponível.
ENERGY_REFRESH_SOURCES = replace(SOURCES, request_timeout_seconds=4.0, max_attempts=2, retry_backoff_seconds=0.25)
FORECAST_DEFAULTS = ForecastSettings()
PLANNING_DEFAULTS = PlanningAssumptions()

MARKET_SNAPSHOT = DATA_DIR / "TOTALSA_snapshot.csv"
EPA_SNAPSHOT = DATA_DIR / "EPA_vehicles_snapshot.csv"
ENERGY_SNAPSHOT = DATA_DIR / "energy_price_snapshot.csv"
MODEL_ARTIFACTS_DIR = DATA_DIR / "advanced_models"
