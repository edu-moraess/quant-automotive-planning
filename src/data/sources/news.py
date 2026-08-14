"""Cliente da News API para sinais estruturados de eventos automotivos."""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Iterable

import httpx
import pandas as pd

from ..contracts import NewsQuery, SourceName, SourcePayload, SourceRunStatus, SourceState, TimeWindow
from ..settings import FeatureSettings
from .base import BaseAPIClient, SourceUnavailableError

NEWS_EVERYTHING_URL = "https://newsapi.org/v2/everything"
_POSITIVE_TERMS = frozenset({"growth", "beat", "record", "launch", "award", "profit", "gain", "expand", "upgrade"})
_NEGATIVE_TERMS = frozenset(
    {"recall", "strike", "delay", "tariff", "shutdown", "cut", "loss", "defect", "investigation", "lawsuit"}
)
_TOKEN_PATTERN = re.compile(r"[a-zA-Z]{3,}")


class NewsAPIClient(BaseAPIClient):
    """Transforma artigos publicados em registros estruturados e deduplicados de evento."""

    source = SourceName.NEWS

    def __init__(self, settings: FeatureSettings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        super().__init__(settings, transport=transport)

    async def fetch_query(self, item: NewsQuery, window: TimeWindow) -> SourcePayload:
        """Busca uma consulta de evento e mantém somente artigos publicados até a data de corte."""
        api_key = self.settings.secret_value("news")
        if not api_key:
            return self._unavailable_payload("NEWS_API_KEY ausente; coleta de eventos não executada.")
        try:
            response = await self.get_json(
                NEWS_EVERYTHING_URL,
                params={
                    "apiKey": api_key,
                    "q": item.query,
                    "from": window.start.strftime("%Y-%m-%d"),
                    "to": window.as_of.strftime("%Y-%m-%d"),
                    "language": item.language,
                    "sortBy": "publishedAt",
                    "pageSize": 100,
                    "page": 1,
                },
            )
        except SourceUnavailableError as error:
            return self._unavailable_payload(str(error))

        frame = self._parse_articles(response.payload.get("articles", []), item, window)
        state = SourceState.CACHED if response.cache_hit else SourceState.FRESH
        if frame.empty:
            state = SourceState.DEGRADED
        return SourcePayload(
            frame=frame,
            status=SourceRunStatus(
                source=self.source,
                state=state,
                rows=len(frame),
                latency_ms=response.latency_ms,
                coverage_start=frame["publicado_em"].min() if not frame.empty else None,
                coverage_end=frame["publicado_em"].max() if not frame.empty else None,
                cache_hit=response.cache_hit,
                message=f"{item.query_id}: {len(frame)} artigos elegíveis.",
            ),
            metadata={"query": item.model_dump(mode="json"), "total_results": response.payload.get("totalResults", 0)},
        )

    async def fetch_many(self, queries: Iterable[NewsQuery], window: TimeWindow) -> SourcePayload:
        """Executa as consultas configuradas em paralelo e remove republicações idênticas."""
        query_list = list(queries)
        payloads = await asyncio.gather(*(self.fetch_query(item, window) for item in query_list))
        frames = [payload.frame for payload in payloads if not payload.frame.empty]
        combined = pd.concat(frames, ignore_index=True) if frames else self._empty_frame()
        if not combined.empty:
            combined = (
                combined.sort_values("publicado_em").drop_duplicates("article_id", keep="first").reset_index(drop=True)
            )
        statuses = [payload.status for payload in payloads]
        return SourcePayload(
            frame=combined,
            status=SourceRunStatus(
                source=self.source,
                state=self._combined_state(statuses),
                rows=len(combined),
                latency_ms=sum(item.latency_ms or 0 for item in statuses),
                coverage_start=combined["publicado_em"].min() if not combined.empty else None,
                coverage_end=combined["publicado_em"].max() if not combined.empty else None,
                cache_hit=bool(statuses) and all(item.cache_hit for item in statuses),
                message=f"{len(query_list)} consultas; {len(combined)} artigos únicos.",
            ),
            metadata={"components": statuses},
        )

    @staticmethod
    def _parse_articles(articles: list[dict[str, object]], item: NewsQuery, window: TimeWindow) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        for article in articles:
            published_at = pd.to_datetime(article.get("publishedAt"), errors="coerce", utc=True)
            if pd.isna(published_at):
                continue
            published_at = published_at.tz_convert("UTC").tz_localize(None)
            if published_at < window.start or published_at > window.as_of:
                continue
            title = str(article.get("title") or "")
            description = str(article.get("description") or "")
            source = article.get("source")
            source_name = source.get("name") if isinstance(source, dict) else None
            url = str(article.get("url") or "")
            fingerprint = url or f"{source_name}|{published_at.isoformat()}|{title}".lower()
            rows.append(
                {
                    "article_id": hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(),
                    "publicado_em": published_at,
                    "disponivel_em": published_at,
                    "marca": item.brand,
                    "modelo": item.model,
                    "tema": item.theme,
                    "query_id": item.query_id,
                    "sentimento": NewsAPIClient._sentiment(f"{title} {description}"),
                    "fonte": source_name,
                }
            )
        return pd.DataFrame(
            rows,
            columns=[
                "article_id",
                "publicado_em",
                "disponivel_em",
                "marca",
                "modelo",
                "tema",
                "query_id",
                "sentimento",
                "fonte",
            ],
        )

    @staticmethod
    def _sentiment(text: str) -> float:
        tokens = _TOKEN_PATTERN.findall(text.lower())
        if not tokens:
            return 0.0
        positive = sum(token in _POSITIVE_TERMS for token in tokens)
        negative = sum(token in _NEGATIVE_TERMS for token in tokens)
        return round((positive - negative) / max(len(tokens) ** 0.5, 1), 4)

    def _unavailable_payload(self, message: str) -> SourcePayload:
        return SourcePayload(
            frame=self._empty_frame(),
            status=SourceRunStatus(source=self.source, state=SourceState.UNAVAILABLE, rows=0, message=message),
        )

    @staticmethod
    def _empty_frame() -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "article_id",
                "publicado_em",
                "disponivel_em",
                "marca",
                "modelo",
                "tema",
                "query_id",
                "sentimento",
                "fonte",
            ]
        )

    @staticmethod
    def _combined_state(statuses: list[SourceRunStatus]) -> SourceState:
        if statuses and all(status.state == SourceState.UNAVAILABLE for status in statuses):
            return SourceState.UNAVAILABLE
        if any(status.state in {SourceState.UNAVAILABLE, SourceState.DEGRADED} for status in statuses):
            return SourceState.DEGRADED
        if statuses and all(status.state == SourceState.CACHED for status in statuses):
            return SourceState.CACHED
        return SourceState.FRESH
