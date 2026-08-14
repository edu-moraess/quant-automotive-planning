"""Infraestrutura HTTP assíncrona, cache local e observabilidade das fontes externas."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from ..contracts import SourceName
from ..settings import FeatureSettings

LOGGER = logging.getLogger("quant_automotive.features")


class SourceUnavailableError(RuntimeError):
    """Indica indisponibilidade transitória ou ausência de credencial de uma fonte."""


@dataclass(frozen=True)
class CachedResponse:
    """Representa a carga JSON e o estado de cache de uma chamada HTTP."""

    payload: dict[str, Any]
    cache_hit: bool
    latency_ms: float


class DiskResponseCache:
    """Armazena respostas JSON por chave determinística, sem credenciais no nome ou conteúdo."""

    def __init__(self, root: Path, ttl_seconds: int) -> None:
        self.root = root
        self.ttl = timedelta(seconds=ttl_seconds)

    def get(self, source: SourceName, key: str) -> dict[str, Any] | None:
        path = self._path(source, key)
        if not path.exists():
            return None
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if datetime.now(UTC) - modified_at > self.ttl:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, source: SourceName, key: str, payload: Mapping[str, Any]) -> None:
        path = self._path(source, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temp_path.replace(path)

    def _path(self, source: SourceName, key: str) -> Path:
        return self.root / source.value / f"{key}.json"


class BaseAPIClient:
    """Executa chamadas JSON com retry controlado, cache local e logs estruturados."""

    source: SourceName

    def __init__(
        self,
        settings: FeatureSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.cache = DiskResponseCache(settings.response_cache_dir, settings.cache_ttl_seconds)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            transport=transport,
            headers={"User-Agent": "quant-automotive-planning/feature-layer"},
        )

    async def __aenter__(self) -> BaseAPIClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Fecha o pool HTTP ao terminar a execução do pipeline."""
        await self._client.aclose()

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str | int | float | None],
        headers: Mapping[str, str] | None = None,
    ) -> CachedResponse:
        """Busca JSON com cache e retry apenas para falhas transitórias."""
        safe_params = {key: value for key, value in params.items() if value is not None and "key" not in key.lower()}
        cache_key = self._cache_key(url, safe_params)
        cached = self.cache.get(self.source, cache_key)
        if cached is not None:
            self._log("cache_hit", url=url, params=safe_params, latency_ms=0.0)
            return CachedResponse(payload=cached, cache_hit=True, latency_ms=0.0)

        started = time.perf_counter()
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.settings.max_attempts),
                wait=wait_exponential_jitter(initial=self.settings.retry_backoff_seconds, max=12),
                retry=retry_if_exception(self._is_retryable),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            latency_ms = (time.perf_counter() - started) * 1_000
            self._log("request_failed", url=url, params=safe_params, latency_ms=latency_ms, error=str(error))
            raise SourceUnavailableError(f"{self.source.value}: {error}") from error

        if not isinstance(payload, dict):
            raise SourceUnavailableError(f"{self.source.value}: resposta JSON fora do contrato esperado.")
        latency_ms = (time.perf_counter() - started) * 1_000
        self.cache.set(self.source, cache_key, payload)
        self._log("request_ok", url=url, params=safe_params, latency_ms=latency_ms)
        return CachedResponse(payload=payload, cache_hit=False, latency_ms=latency_ms)

    @staticmethod
    def _is_retryable(error: BaseException) -> bool:
        if isinstance(error, httpx.TransportError):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code == 429 or error.response.status_code >= 500
        return False

    @staticmethod
    def _cache_key(url: str, params: Mapping[str, object]) -> str:
        normalized = json.dumps({"url": url, "params": dict(params)}, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _log(self, event: str, **fields: object) -> None:
        LOGGER.info(
            json.dumps({"event": event, "source": self.source.value, **fields}, ensure_ascii=False, default=str)
        )
