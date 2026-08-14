"""Configuração tipada da camada de features, sem persistir credenciais."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from config import DATA_DIR, ROOT_DIR

from .contracts import NewsQuery


class FeatureSourceConfig(BaseModel):
    """Parâmetros públicos e versionáveis das fontes externas."""

    model_config = ConfigDict(frozen=True)

    fred_series: dict[str, str] = Field(
        default_factory=lambda: {
            "TOTALSA": "vendas_saar_milhoes",
            "UNRATE": "desemprego_pct",
            "CPIAUCSL": "cpi",
            "FEDFUNDS": "fed_funds_pct",
            "MORTGAGE30US": "mortgage_30y_pct",
            "UMCSENT": "confianca_consumidor",
            "INDPRO": "producao_industrial",
            "RSAFS": "vendas_varejo",
        }
    )
    eia_series: dict[str, str] = Field(
        default_factory=lambda: {
            "gasoline_regular": "PET.WRG0_EPM0_PTE_DPG.W",
            "diesel": "PET.WDIUPUS1.W",
            "electricity_residential": "ELEC.PRICE.US-RES.M",
        }
    )
    news_queries: list[NewsQuery] = Field(
        default_factory=lambda: [
            NewsQuery(
                query_id="ford_recall",
                query="Ford AND recall",
                brand="Ford",
                theme="recall",
            ),
            NewsQuery(
                query_id="toyota_incentive",
                query="Toyota AND incentive",
                brand="Toyota",
                theme="incentive",
            ),
            NewsQuery(
                query_id="tesla_production",
                query="Tesla AND production",
                brand="Tesla",
                theme="production",
            ),
        ]
    )


class FeatureSettings(BaseSettings):
    """Lê chaves somente de ambiente seguro, mantendo valores sensíveis fora do código."""

    model_config = SettingsConfigDict(
        env_prefix="QUANT_",
        case_sensitive=False,
        extra="ignore",
    )

    fred_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("FRED_API_KEY", "QUANT_FRED_API_KEY"),
        repr=False,
    )
    eia_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("EIA_API_KEY", "QUANT_EIA_API_KEY"),
        repr=False,
    )
    news_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("NEWS_API_KEY", "QUANT_NEWS_API_KEY"),
        repr=False,
    )
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    max_attempts: int = Field(default=3, ge=1, le=8)
    retry_backoff_seconds: float = Field(default=0.75, gt=0, le=30)
    cache_ttl_seconds: int = Field(default=21_600, ge=0)
    feature_store_dir: Path = DATA_DIR / "feature_store"
    response_cache_dir: Path = DATA_DIR / "feature_cache"

    def secret_value(self, source: str) -> str | None:
        """Retorna uma credencial apenas no instante de autenticação do cliente."""
        secret = {
            "fred": self.fred_api_key,
            "eia": self.eia_api_key,
            "news": self.news_api_key,
        }.get(source)
        return None if secret is None else secret.get_secret_value()

    @classmethod
    def from_streamlit_secrets(cls, secrets: Mapping[str, Any]) -> FeatureSettings:
        """Cria a configuração a partir de uma seção `feature_sources` do Streamlit."""
        section = secrets.get("feature_sources", secrets)
        return cls.model_validate(dict(section))


def load_feature_source_config(path: Path | None = None) -> FeatureSourceConfig:
    """Carrega parâmetros públicos de fontes e consultas a partir de TOML versionado."""
    config_path = path or ROOT_DIR / "config" / "features.toml"
    if not config_path.exists():
        return FeatureSourceConfig()
    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)
    return FeatureSourceConfig.model_validate(payload)
