"""Atualiza features gratuitas de mercado, energia e eventos para o feature store."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from data import FeatureBuilder, FeatureSettings, SourceName, TimeWindow, load_feature_source_config  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Lê a janela de atualização sem aceitar segredos por argumento."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2018-01-01", help="Início da janela de observação (YYYY-MM-DD).")
    parser.add_argument("--as-of", default=None, help="Data e hora de corte em ISO-8601; padrão: agora em UTC.")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "features.toml")
    parser.add_argument(
        "--sources",
        default="fred,eia,news",
        help="Lista separada por vírgula: fred,eia,news.",
    )
    return parser.parse_args()


def configure_logging() -> None:
    """Ativa logs JSON compactos para auditoria de latência e cobertura."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


async def run(args: argparse.Namespace) -> dict[str, object]:
    """Executa o construtor e devolve apenas metadados seguros para o job."""
    as_of = pd.Timestamp(args.as_of) if args.as_of else pd.Timestamp(datetime.now(UTC))
    settings = FeatureSettings()
    source_config = load_feature_source_config(args.config)
    builder = FeatureBuilder(settings, source_config)
    selected = {SourceName(name.strip()) for name in args.sources.split(",") if name.strip()}
    result = await builder.build(TimeWindow(start=pd.Timestamp(args.start), as_of=as_of), sources=selected)
    return {
        "as_of": result.as_of.isoformat(),
        "market_feature_rows": len(result.market_features),
        "event_feature_rows": len(result.event_features),
        "sources": [status.to_display_row() for status in result.statuses],
    }


def main() -> int:
    """Executa a atualização e imprime um resumo sem valores de segredo."""
    configure_logging()
    summary = asyncio.run(run(parse_args()))
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
