"""Ingestão resiliente de CSVs públicos com fallback e proveniência explícitos."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from time import sleep

import pandas as pd
import requests

from config import SOURCES, SourceSettings


class SourceUnavailable(RuntimeError):
    """Indica indisponibilidade de fonte após tentativas controladas."""


@dataclass(frozen=True)
class IngestionResult:
    frame: pd.DataFrame
    source_status: str
    source_url: str | None
    retrieved_at_utc: str | None
    fallback_reason: str | None


def _validate_schema(frame: pd.DataFrame, expected_columns: Iterable[str], source_name: str) -> pd.DataFrame:
    missing = [column for column in expected_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{source_name}: schema inválido; faltam colunas {missing}.")
    if frame.empty:
        raise ValueError(f"{source_name}: fonte retornou arquivo vazio.")
    return frame


def fetch_csv(
    url: str, expected_columns: Iterable[str], source_name: str, settings: SourceSettings = SOURCES
) -> IngestionResult:
    """Baixa CSV com timeout e retry exponencial curto, sem mascarar schema inválido."""
    last_error: Exception | None = None
    for attempt in range(1, settings.max_attempts + 1):
        try:
            response = requests.get(
                url,
                timeout=settings.request_timeout_seconds,
                headers={"User-Agent": "quant-automotive-intelligence/1.0"},
            )
            response.raise_for_status()
            frame = pd.read_csv(StringIO(response.text))
            _validate_schema(frame, expected_columns, source_name)
            return IngestionResult(
                frame=frame,
                source_status="ONLINE",
                source_url=url,
                retrieved_at_utc=pd.Timestamp.utcnow().isoformat(),
                fallback_reason=None,
            )
        except (requests.RequestException, ValueError, pd.errors.ParserError) as error:
            last_error = error
            if attempt < settings.max_attempts:
                sleep(settings.retry_backoff_seconds * attempt)
    raise SourceUnavailable(
        f"{source_name}: indisponível após {settings.max_attempts} tentativas. Motivo: {last_error}"
    )


def load_csv_with_fallback(
    url: str,
    expected_columns: Iterable[str],
    source_name: str,
    snapshot_path: str | Path,
    allow_online: bool,
    settings: SourceSettings = SOURCES,
) -> IngestionResult:
    """Retorna fonte online quando solicitada; caso contrário, usa snapshot explicitamente."""
    snapshot = Path(snapshot_path)
    if allow_online:
        try:
            return fetch_csv(url, expected_columns, source_name, settings)
        except SourceUnavailable as error:
            fallback_reason = str(error)
        except Exception as error:  # pragma: no cover - proteção final de dashboard
            fallback_reason = f"{source_name}: falha inesperada: {error}"
    else:
        fallback_reason = "Atualização online não solicitada nesta execução."
    if not snapshot.exists():
        raise SourceUnavailable(f"{source_name}: fonte online indisponível e snapshot ausente em {snapshot}.")
    frame = pd.read_csv(snapshot)
    _validate_schema(frame, expected_columns, source_name)
    return IngestionResult(
        frame=frame,
        source_status="SNAPSHOT",
        source_url=None,
        retrieved_at_utc=None,
        fallback_reason=fallback_reason,
    )


def fetch_monthly_fred_energy_series(
    series_id: str, output_column: str, settings: SourceSettings = SOURCES
) -> IngestionResult:
    """Atualiza uma série FRED e harmoniza a observação para início do mês."""
    result = fetch_csv(
        settings.fred_energy_url(series_id), ["observation_date", series_id], f"FRED {series_id}", settings
    )
    frame = result.frame.rename(columns={"observation_date": "data", series_id: output_column})
    frame["data"] = pd.to_datetime(frame["data"], errors="coerce")
    frame[output_column] = pd.to_numeric(frame[output_column], errors="coerce")
    frame = frame.dropna(subset=["data"]).set_index("data").resample("MS").mean().reset_index()
    return IngestionResult(
        frame=frame,
        source_status=result.source_status,
        source_url=result.source_url,
        retrieved_at_utc=result.retrieved_at_utc,
        fallback_reason=result.fallback_reason,
    )
