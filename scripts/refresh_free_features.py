"""Atualiza features gratuitas de mercado, energia e eventos para o feature store.

O pipeline executa um teste de saúde das APIs antes de qualquer ingestão:
- FRED e EIA requerem chave; falha bloqueia a fonte mas não interrompe o pipeline.
- News API requer chave; falha gera aviso e a fonte é ignorada.
- NHTSA é público; falha gera aviso e a fonte é ignorada.
- Se FRED falhar, o snapshot local é usado como fallback automático.
"""

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
from data.api_health import STATUS_FAIL, STATUS_NO_KEY, HealthReport, run_health_check  # noqa: E402

logger = logging.getLogger(__name__)

# Caminho padrão do relatório de saúde das APIs.
_HEALTH_PATH = ROOT / "data" / "feature_store" / "api_health.json"


def parse_args() -> argparse.Namespace:
    """Lê a janela de atualização sem aceitar segredos por argumento."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2018-01-01", help="Início da janela de observação (YYYY-MM-DD).")
    parser.add_argument("--as-of", default=None, help="Data e hora de corte em ISO-8601; padrão: agora em UTC.")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "features.toml")
    parser.add_argument(
        "--sources",
        default="fred,eia,news,nhtsa",
        help="Lista separada por vírgula: fred,eia,news,nhtsa.",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Pula o teste de saúde das APIs (útil em ambientes sem internet).",
    )
    return parser.parse_args()


def configure_logging() -> None:
    """Ativa logs JSON compactos para auditoria de latência e cobertura."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def _preflight_health_check(selected: set[SourceName]) -> tuple[set[SourceName], HealthReport]:
    """Executa o teste de saúde e retorna o conjunto de fontes elegíveis para ingestão.

    Regras de fallback:
    - FRED com falha ou chave ausente: mantém na lista (o FeatureBuilder usa o snapshot local).
    - EIA, News, NHTSA com falha ou chave ausente: remove da lista e emite aviso.
    """
    logger.info("Executando teste de saúde das APIs...")
    report = run_health_check(save_path=_HEALTH_PATH)

    eligible = set(selected)
    for source_name, health in report.sources.items():
        try:
            sn = SourceName(source_name)
        except ValueError:
            continue
        if sn not in selected:
            continue
        if health.status in {STATUS_FAIL, STATUS_NO_KEY}:
            if sn == SourceName.FRED:
                # FRED com falha: mantém na lista para acionar o fallback local.
                logger.warning(
                    "FRED indisponível (%s) — o pipeline usará o snapshot local como fallback.",
                    health.message,
                )
            else:
                eligible.discard(sn)
                logger.warning(
                    "%s indisponível (%s) — fonte removida desta execução.",
                    source_name.upper(),
                    health.message,
                )
        else:
            logger.info("%s: %s (%s)", source_name.upper(), health.status, health.message)

    return eligible, report


async def run(args: argparse.Namespace) -> dict[str, object]:
    """Executa o health check, constrói features e devolve apenas metadados seguros."""
    as_of = pd.Timestamp(args.as_of) if args.as_of else pd.Timestamp(datetime.now(UTC))
    settings = FeatureSettings()
    source_config = load_feature_source_config(args.config)
    selected_raw = {SourceName(name.strip()) for name in args.sources.split(",") if name.strip()}

    health_summary: dict[str, object] = {}
    if not args.skip_health_check:
        eligible, report = _preflight_health_check(selected_raw)
        health_summary = {name: {"status": h.status, "latency_ms": h.latency_ms} for name, h in report.sources.items()}
    else:
        eligible = selected_raw
        logger.info("Teste de saúde ignorado por --skip-health-check.")

    builder = FeatureBuilder(settings, source_config)
    result = await builder.build(TimeWindow(start=pd.Timestamp(args.start), as_of=as_of), sources=eligible)
    return {
        "as_of": result.as_of.isoformat(),
        "market_feature_rows": len(result.market_features),
        "event_feature_rows": len(result.event_features),
        "api_health": health_summary,
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
