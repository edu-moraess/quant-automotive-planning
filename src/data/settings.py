"""Configuração tipada da camada de features, sem persistir credenciais."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from config import DATA_DIR, ROOT_DIR

from .contracts import NewsQuery, NHTSATarget


class FeatureSourceConfig(BaseModel):
    """Parâmetros públicos e versionáveis das fontes externas."""

    model_config = ConfigDict(frozen=True)

    fred_series: dict[str, str] = Field(
        default_factory=lambda: {
            "TOTALSA": "vendas_saar_milhoes",
            "FEDFUNDS": "fed_funds_pct",
            "G18": "taxa_financiamento_auto_pct",
            "UNRATE": "desemprego_pct",
            "CPIAUCSL": "cpi",
            "GASREG": "preco_gasolina_regular_fred",
            "UMCSENT": "confianca_consumidor",
            "PAYEMS": "empregados_total_milhares",
            "INDPRO": "producao_industrial",
            "MORTGAGE30US": "mortgage_30y_pct",
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
    nhtsa_targets: list[NHTSATarget] = Field(
        default_factory=lambda: [
            NHTSATarget(make="Ford", model="Maverick", model_year=2024),
            NHTSATarget(make="Chevrolet", model="Silverado 1500", model_year=2024),
            NHTSATarget(make="Toyota", model="RAV4", model_year=2024),
            NHTSATarget(make="Honda", model="CR-V", model_year=2024),
            NHTSATarget(make="Tesla", model="Model 3", model_year=2024),
            NHTSATarget(make="Hyundai", model="IONIQ 5", model_year=2024),
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
