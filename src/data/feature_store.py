"""Persistência leve de features em Parquet particionado e manifesto de execução."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .contracts import SourceName, SourceRunStatus

_SAFE_PATH = re.compile(r"[^a-z0-9]+")


class FeatureStore:
    """Grava tabelas por fonte e competência, preservando uma trilha de atualização."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest_path = root / "manifest.json"

    def write(
        self,
        source: SourceName,
        frame: pd.DataFrame,
        *,
        date_column: str,
        dedupe_columns: Iterable[str],
        entity_columns: tuple[str, ...] = (),
    ) -> int:
        """Atualiza partições afetadas e remove duplicatas de uma mesma observação."""
        if frame.empty:
            return 0
        if date_column not in frame.columns:
            raise ValueError(f"Coluna temporal ausente para persistência: {date_column}")
        prepared = frame.copy()
        prepared[date_column] = pd.to_datetime(prepared[date_column], errors="coerce")
        prepared = prepared.loc[prepared[date_column].notna()].copy()
        if prepared.empty:
            return 0
        prepared["_month"] = prepared[date_column].dt.to_period("M").astype(str)
        written = 0
        grouped = prepared.groupby(self._group_columns(prepared, entity_columns), dropna=False, sort=True)
        for group_key, partition in grouped:
            key_values = group_key if isinstance(group_key, tuple) else (group_key,)
            partition_path = self._partition_path(source, entity_columns, key_values)
            partition_path.mkdir(parents=True, exist_ok=True)
            file_path = partition_path / "data.parquet"
            existing = pd.read_parquet(file_path) if file_path.exists() else pd.DataFrame()
            merged = pd.concat([existing, partition.drop(columns="_month")], ignore_index=True)
            available_keys = [column for column in dedupe_columns if column in merged.columns]
            if available_keys:
                merged = merged.drop_duplicates(available_keys, keep="last")
            merged = merged.sort_values(date_column).reset_index(drop=True)
            temp_path = file_path.with_suffix(".tmp.parquet")
            merged.to_parquet(temp_path, index=False)
            temp_path.replace(file_path)
            written += len(partition)
        return written

    def clear_source(self, source: SourceName) -> None:
        """Remove partições de uma fonte antes de uma sincronização completa e validada."""
        source_path = self.root / f"source={source.value}"
        if source_path.exists():
            shutil.rmtree(source_path)

    def read_source(self, source: SourceName) -> pd.DataFrame:
        """Lê todas as partições de uma fonte para agregações locais de baixo volume."""
        source_path = self.root / f"source={source.value}"
        files = sorted(source_path.rglob("data.parquet")) if source_path.exists() else []
        frames = [pd.read_parquet(path) for path in files]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def record_statuses(self, statuses: Iterable[SourceRunStatus]) -> None:
        """Atualiza o manifesto sem incluir credenciais ou respostas brutas."""
        self.root.mkdir(parents=True, exist_ok=True)
        current = self.load_manifest()
        current["updated_at_utc"] = datetime.now(UTC).isoformat()
        source_manifest = dict(current.get("sources", {}))
        source_manifest.update(
            {
                status.source.value: {
                    "state": status.state.value,
                    "rows": status.rows,
                    "requested_at_utc": status.requested_at_utc.isoformat(),
                    "latency_ms": status.latency_ms,
                    "coverage_start": self._iso(status.coverage_start),
                    "coverage_end": self._iso(status.coverage_end),
                    "cache_hit": status.cache_hit,
                    "message": status.message,
                }
                for status in statuses
            }
        )
        current["sources"] = source_manifest
        temp_path = self.manifest_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.manifest_path)

    def load_manifest(self) -> dict[str, object]:
        """Retorna o manifesto existente ou uma estrutura vazia para a interface."""
        if not self.manifest_path.exists():
            return {"updated_at_utc": None, "sources": {}}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"updated_at_utc": None, "sources": {}}

    def _partition_path(
        self,
        source: SourceName,
        entity_columns: tuple[str, ...],
        values: tuple[object, ...],
    ) -> Path:
        path = self.root / f"source={source.value}"
        month = str(values[0])
        path = path / f"month={self._safe_value(month)}"
        for column, value in zip(entity_columns, values[1:], strict=True):
            if pd.isna(value) or value is None:
                continue
            path = path / f"{column}={self._safe_value(str(value))}"
        return path

    @staticmethod
    def _group_columns(frame: pd.DataFrame, entity_columns: tuple[str, ...]) -> list[str]:
        return ["_month", *(column for column in entity_columns if column in frame.columns)]

    @staticmethod
    def _safe_value(value: str) -> str:
        normalized = _SAFE_PATH.sub("-", value.lower()).strip("-")
        return normalized or "unknown"

    @staticmethod
    def _iso(value: pd.Timestamp | None) -> str | None:
        return None if value is None or pd.isna(value) else pd.Timestamp(value).isoformat()
