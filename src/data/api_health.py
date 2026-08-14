"""Diagnóstico de conectividade das fontes externas antes de qualquer ingestão."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Endpoints leves usados exclusivamente para o probe de conectividade.
_FRED_PROBE_URL = "https://api.stlouisfed.org/fred/series/observations"
_EIA_PROBE_URL = "https://api.eia.gov/v2/seriesid/PET.WRG0_EPM0_PTE_DPG.W"
_NEWS_PROBE_URL = "https://newsapi.org/v2/everything"
_NHTSA_PROBE_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"

# Valores possíveis para o campo "status" de cada fonte no relatório.
STATUS_OK = "ok"
STATUS_FAIL = "falha"
STATUS_NO_KEY = "chave_ausente"


@dataclass
class SourceHealth:
    """Resultado do probe de uma única fonte externa."""

    source: str
    status: str  # STATUS_OK | STATUS_FAIL | STATUS_NO_KEY
    latency_ms: float | None = None
    message: str = ""
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class HealthReport:
    """Relatório consolidado de todas as fontes verificadas."""

    sources: dict[str, SourceHealth] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def all_ok(self) -> bool:
        return all(s.status == STATUS_OK for s in self.sources.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "sources": {
                name: {
                    "status": health.status,
                    "latency_ms": health.latency_ms,
                    "message": health.message,
                    "checked_at": health.checked_at,
                }
                for name, health in self.sources.items()
            },
        }

    def save(self, path: Path) -> None:
        """Persiste o relatório em JSON; cria o diretório se necessário."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("api_health.json salvo em %s", path)

    @classmethod
    def load(cls, path: Path) -> HealthReport | None:
        """Carrega um relatório existente; retorna None se o arquivo não existir ou estiver corrompido."""
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        report = cls(generated_at=raw.get("generated_at", ""))
        for name, values in raw.get("sources", {}).items():
            report.sources[name] = SourceHealth(
                source=name,
                status=values.get("status", STATUS_FAIL),
                latency_ms=values.get("latency_ms"),
                message=values.get("message", ""),
                checked_at=values.get("checked_at", ""),
            )
        return report


def _read_key(env_var: str, streamlit_section: str | None = None) -> str | None:
    """Lê uma credencial de st.secrets (se disponível) ou de variável de ambiente."""
    # Tenta st.secrets primeiro para não depender de variáveis de ambiente no Streamlit Cloud.
    try:
        import streamlit as st  # noqa: PLC0415

        section = st.secrets.get("feature_sources", st.secrets)
        value = section.get(env_var) or section.get(env_var.lower())
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get(env_var) or os.environ.get(env_var.lower())


def _probe(url: str, params: dict[str, Any], timeout: float = 10.0) -> tuple[bool, float, str]:
    """Executa uma requisição GET leve e retorna (sucesso, latência_ms, mensagem)."""
    start = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, params=params)
        latency = (time.monotonic() - start) * 1000
        if response.status_code == 200:
            return True, latency, f"HTTP 200 em {latency:.0f} ms"
        return False, latency, f"HTTP {response.status_code}"
    except httpx.TimeoutException:
        latency = (time.monotonic() - start) * 1000
        return False, latency, "Timeout na requisição"
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        return False, latency, f"Erro de conexão: {type(exc).__name__}"


def check_fred(api_key: str | None = None) -> SourceHealth:
    """Probe FRED: busca TOTALSA com limit=1 para verificar conectividade e chave."""
    key = api_key or _read_key("FRED_API_KEY")
    if not key:
        return SourceHealth(source="fred", status=STATUS_NO_KEY, message="FRED_API_KEY ausente.")
    ok, latency, msg = _probe(
        _FRED_PROBE_URL,
        {
            "series_id": "TOTALSA",
            "api_key": key,
            "file_type": "json",
            "limit": "1",
            "realtime_start": "2025-01-01",
        },
    )
    return SourceHealth(source="fred", status=STATUS_OK if ok else STATUS_FAIL, latency_ms=latency, message=msg)


def check_eia(api_key: str | None = None) -> SourceHealth:
    """Probe EIA: busca preço da gasolina regular com length=1."""
    key = api_key or _read_key("EIA_API_KEY")
    if not key:
        return SourceHealth(source="eia", status=STATUS_NO_KEY, message="EIA_API_KEY ausente.")
    ok, latency, msg = _probe(_EIA_PROBE_URL, {"api_key": key, "length": "1"})
    return SourceHealth(source="eia", status=STATUS_OK if ok else STATUS_FAIL, latency_ms=latency, message=msg)


def check_news(api_key: str | None = None) -> SourceHealth:
    """Probe News API: busca 1 artigo sobre 'car' para verificar chave e conectividade."""
    key = api_key or _read_key("NEWS_API_KEY")
    if not key:
        return SourceHealth(source="news", status=STATUS_NO_KEY, message="NEWS_API_KEY ausente.")
    ok, latency, msg = _probe(_NEWS_PROBE_URL, {"q": "car", "pageSize": "1", "apiKey": key})
    return SourceHealth(source="news", status=STATUS_OK if ok else STATUS_FAIL, latency_ms=latency, message=msg)


def check_nhtsa() -> SourceHealth:
    """Probe NHTSA: endpoint público de recalls para Ford 2024 — sem chave necessária."""
    ok, latency, msg = _probe(_NHTSA_PROBE_URL, {"modelYear": "2024", "make": "FORD"})
    return SourceHealth(source="nhtsa", status=STATUS_OK if ok else STATUS_FAIL, latency_ms=latency, message=msg)


def run_health_check(
    *,
    fred_key: str | None = None,
    eia_key: str | None = None,
    news_key: str | None = None,
    save_path: Path | None = None,
) -> HealthReport:
    """Executa o probe de todas as fontes e persiste o relatório se `save_path` for fornecido."""
    report = HealthReport()
    report.sources["fred"] = check_fred(fred_key)
    report.sources["eia"] = check_eia(eia_key)
    report.sources["news"] = check_news(news_key)
    report.sources["nhtsa"] = check_nhtsa()

    for name, health in report.sources.items():
        level = logging.INFO if health.status == STATUS_OK else logging.WARNING
        logger.log(level, "API health [%s]: %s — %s", name, health.status, health.message)

    if save_path is not None:
        report.save(save_path)

    return report
