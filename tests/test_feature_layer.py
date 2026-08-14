import asyncio
import json
import sys
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data import FeatureBuilder, FeatureSettings, FeatureSourceConfig, NewsQuery, NHTSATarget, SourceName, TimeWindow
from data.feature_store import FeatureStore
from data.sources.eia import EIAClient
from data.sources.epa import EPAClient
from data.sources.fred import FREDClient
from data.sources.news import NewsAPIClient
from data.sources.nhtsa import NHTSAClient
from data.temporal import assert_no_future_availability, enforce_point_in_time


def _settings(tmp_path: Path, **keys: str) -> FeatureSettings:
    return FeatureSettings(
        response_cache_dir=tmp_path / "cache",
        feature_store_dir=tmp_path / "store",
        cache_ttl_seconds=3_600,
        **keys,
    )


def _transport(payload: dict) -> httpx.MockTransport:
    return httpx.MockTransport(lambda _: httpx.Response(200, json=payload))


def test_settings_accept_streamlit_secret_section(tmp_path):
    settings = FeatureSettings.from_streamlit_secrets(
        {
            "feature_sources": {
                "FRED_API_KEY": "fred-test",
                "EIA_API_KEY": "eia-test",
                "NEWS_API_KEY": "news-test",
                "feature_store_dir": str(tmp_path / "store"),
            }
        }
    )
    assert settings.secret_value("fred") == "fred-test"
    assert settings.secret_value("eia") == "eia-test"
    assert settings.secret_value("news") == "news-test"


def test_epa_client_loads_technical_catalog_from_snapshot():
    result = EPAClient().load_catalog()
    assert result.status.rows > 0
    assert {"make", "model", "comb08", "ano_modelo"}.issubset(result.frame.columns)
    assert result.status.coverage_start is not None


def test_fred_client_respects_vintage_cutoff_and_uses_cache(tmp_path):
    payload = {
        "observations": [
            {"date": "2024-01-01", "value": "16.2", "realtime_start": "2024-02-01"},
            {"date": "2024-02-01", "value": ".", "realtime_start": "2024-03-01"},
        ]
    }
    settings = _settings(tmp_path, FRED_API_KEY="test-key")
    window = TimeWindow(start="2024-01-01", as_of="2024-02-15")

    async def run_client():
        async with FREDClient(settings, transport=_transport(payload)) as client:
            first = await client.fetch_series("TOTALSA", "vendas_saar_milhoes", window)
            second = await client.fetch_series("TOTALSA", "vendas_saar_milhoes", window)
        return first, second

    first, second = asyncio.run(run_client())
    assert len(first.frame) == 1
    assert first.frame.loc[0, "feature"] == "vendas_saar_milhoes"
    assert first.status.cache_hit is False
    assert second.status.cache_hit is True


def test_eia_client_applies_publication_lag_before_cutoff(tmp_path):
    payload = {"response": {"data": [{"period": "2024-02-01", "value": "3.12"}]}}
    settings = _settings(tmp_path, EIA_API_KEY="test-key")
    window = TimeWindow(start="2024-01-01", as_of="2024-03-20")

    async def run_client():
        async with EIAClient(settings, transport=_transport(payload)) as client:
            return await client.fetch_series("PET.TEST", "gasoline_regular", window, publication_lag_days=45)

    result = asyncio.run(run_client())
    assert len(result.frame) == 1
    assert result.frame.loc[0, "disponivel_em"] == pd.Timestamp("2024-03-17")


def test_news_client_deduplicates_and_excludes_future_articles(tmp_path):
    payload = {
        "articles": [
            {
                "title": "Ford recall announced",
                "description": "Defect investigation continues",
                "url": "https://example.test/recall",
                "publishedAt": "2024-01-15T12:00:00Z",
                "source": {"name": "Example"},
            },
            {
                "title": "Ford recall announced again",
                "description": "Republished coverage",
                "url": "https://example.test/recall",
                "publishedAt": "2024-01-15T13:00:00Z",
                "source": {"name": "Example"},
            },
            {
                "title": "Future article",
                "description": "Not yet available",
                "url": "https://example.test/future",
                "publishedAt": "2024-01-20T12:00:00Z",
                "source": {"name": "Example"},
            },
        ]
    }
    settings = _settings(tmp_path, NEWS_API_KEY="test-key")
    query = NewsQuery(query_id="ford_recall", query="Ford AND recall", brand="Ford", theme="recall")
    window = TimeWindow(start="2024-01-01", as_of="2024-01-19T23:59:59")

    async def run_client():
        async with NewsAPIClient(settings, transport=_transport(payload)) as client:
            return await client.fetch_many([query], window)

    result = asyncio.run(run_client())
    assert len(result.frame) == 1
    assert result.frame.loc[0, "tema"] == "recall"
    assert result.frame.loc[0, "sentimento"] < 0


def test_nhtsa_client_excludes_events_after_cutoff(tmp_path):
    payload = {
        "results": [
            {"NHTSACampaignNumber": "24V001", "ReportReceivedDate": "2024-01-15"},
            {"NHTSACampaignNumber": "24V999", "ReportReceivedDate": "2024-04-15"},
        ]
    }
    settings = _settings(tmp_path)
    window = TimeWindow(start="2024-01-01", as_of="2024-03-01")

    async def run_client():
        async with NHTSAClient(settings, transport=_transport(payload)) as client:
            return await client.fetch_recalls("Ford", "F-150", 2024, window)

    result = asyncio.run(run_client())
    assert len(result.frame) == 1
    assert result.frame.loc[0, "evento_id"] == "24V001"


def test_nhtsa_watchlist_consolidates_recalls_and_complaints(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if "recalls" in str(request.url):
            return httpx.Response(
                200,
                json={"results": [{"NHTSACampaignNumber": "24V001", "ReportReceivedDate": "2024-01-15"}]},
            )
        return httpx.Response(
            200,
            json={"results": [{"odiNumber": "11400001", "dateComplaintFiled": "2024-01-20"}]},
        )

    settings = _settings(tmp_path)
    window = TimeWindow(start="2024-01-01", as_of="2024-02-01")
    target = NHTSATarget(make="Ford", model="F-150", model_year=2024)

    async def run_client():
        async with NHTSAClient(settings, transport=httpx.MockTransport(handler)) as client:
            return await client.fetch_many([target], window)

    result = asyncio.run(run_client())
    assert {"recall", "complaint"} == set(result.frame["tipo_evento"])
    assert result.status.rows == 2


def test_nhtsa_event_features_calculate_monthly_risk_index():
    nhtsa = pd.DataFrame(
        {
            "evento_id": ["r1", "c1", "c2"],
            "disponivel_em": ["2024-01-10", "2024-01-12", "2024-01-13"],
            "marca": ["Ford", "Ford", "Ford"],
            "modelo": ["F-150", "F-150", "F-150"],
            "ano_modelo": [2024, 2024, 2024],
            "tipo_evento": ["recall", "complaint", "complaint"],
        }
    )
    result = FeatureBuilder._build_event_features(
        pd.DataFrame(),
        nhtsa,
        TimeWindow(start="2024-01-01", as_of="2024-01-31"),
    )
    row = result.loc[(pd.Timestamp("2024-01-01"), "Ford", "F-150")]
    assert row["nhtsa_recalls"] == 1
    assert row["nhtsa_reclamacoes"] == 2
    assert row["nhtsa_indice_risco"] == 4


def test_feature_store_reads_persisted_nhtsa_events(tmp_path):
    store = FeatureStore(tmp_path / "store")
    events = pd.DataFrame(
        {
            "evento_id": ["r1"],
            "disponivel_em": [pd.Timestamp("2024-01-10")],
            "marca": ["Ford"],
            "modelo": ["Maverick"],
            "ano_modelo": [2024],
            "tipo_evento": ["recall"],
        }
    )
    store.write(
        SourceName.NHTSA,
        events,
        date_column="disponivel_em",
        dedupe_columns=("evento_id", "tipo_evento"),
        entity_columns=("marca", "modelo", "ano_modelo"),
    )
    loaded = store.read_source(SourceName.NHTSA)
    assert loaded.loc[0, "evento_id"] == "r1"


def test_temporal_guard_filters_future_observations():
    frame = pd.DataFrame(
        {
            "data": ["2024-01-01", "2024-02-01"],
            "disponivel_em": ["2024-01-03", "2024-03-10"],
            "valor": [1.0, 2.0],
        }
    )
    result = enforce_point_in_time(frame, available_column="disponivel_em", as_of=pd.Timestamp("2024-02-28"))
    assert len(result) == 1
    assert_no_future_availability(result, available_column="disponivel_em", as_of=pd.Timestamp("2024-02-28"))


def test_feature_builder_delivers_total_sa_with_local_fallback(tmp_path):
    settings = _settings(tmp_path)
    config = FeatureSourceConfig(fred_series={"TOTALSA": "vendas_saar_milhoes"}, eia_series={}, news_queries=[])
    builder = FeatureBuilder(settings, config)
    window = TimeWindow(start="2025-01-01", as_of="2026-07-31")
    result = asyncio.run(builder.build(window, sources={SourceName.FRED}))

    assert "vendas_saar_milhoes" in result.market_features.columns
    assert not result.market_features.empty
    assert (settings.feature_store_dir / "manifest.json").exists()
    assert any(settings.feature_store_dir.glob("source=feature_builder/month=*/data.parquet"))


# ---------------------------------------------------------------------------
# Testes do módulo api_health
# ---------------------------------------------------------------------------


def _mock_transport_status(status_code: int, body: dict | None = None) -> httpx.MockTransport:
    """Cria um transporte mock que retorna um status HTTP fixo."""
    payload = body or {}
    return httpx.MockTransport(lambda _: httpx.Response(status_code, json=payload))


def test_health_report_serialization_roundtrip(tmp_path):
    """HealthReport.save/load preserva todos os campos sem perda."""
    from data.api_health import STATUS_OK, HealthReport, SourceHealth

    report = HealthReport()
    report.sources["fred"] = SourceHealth(source="fred", status=STATUS_OK, latency_ms=42.5, message="HTTP 200")
    report.sources["nhtsa"] = SourceHealth(source="nhtsa", status=STATUS_OK, latency_ms=88.0, message="HTTP 200")

    path = tmp_path / "api_health.json"
    report.save(path)
    assert path.exists()

    loaded = HealthReport.load(path)
    assert loaded is not None
    assert loaded.sources["fred"].status == STATUS_OK
    assert loaded.sources["fred"].latency_ms == 42.5
    assert loaded.sources["nhtsa"].status == STATUS_OK


def test_health_report_load_returns_none_for_missing_file(tmp_path):
    """HealthReport.load retorna None quando o arquivo não existe."""
    from data.api_health import HealthReport

    result = HealthReport.load(tmp_path / "nonexistent.json")
    assert result is None


def test_health_report_load_returns_none_for_corrupt_file(tmp_path):
    """HealthReport.load retorna None quando o JSON está corrompido."""
    from data.api_health import HealthReport

    path = tmp_path / "bad.json"
    path.write_text("{ not valid json }", encoding="utf-8")
    result = HealthReport.load(path)
    assert result is None


def test_check_fred_returns_no_key_when_key_absent(monkeypatch):
    """check_fred retorna STATUS_NO_KEY quando a chave não está configurada."""
    from data.api_health import STATUS_NO_KEY, check_fred

    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("QUANT_FRED_API_KEY", raising=False)
    result = check_fred(api_key=None)
    assert result.status == STATUS_NO_KEY


def test_check_eia_returns_no_key_when_key_absent(monkeypatch):
    """check_eia retorna STATUS_NO_KEY quando a chave não está configurada."""
    from data.api_health import STATUS_NO_KEY, check_eia

    monkeypatch.delenv("EIA_API_KEY", raising=False)
    monkeypatch.delenv("QUANT_EIA_API_KEY", raising=False)
    result = check_eia(api_key=None)
    assert result.status == STATUS_NO_KEY


def test_check_news_returns_no_key_when_key_absent(monkeypatch):
    """check_news retorna STATUS_NO_KEY quando a chave não está configurada."""
    from data.api_health import STATUS_NO_KEY, check_news

    monkeypatch.delenv("NEWS_API_KEY", raising=False)
    monkeypatch.delenv("QUANT_NEWS_API_KEY", raising=False)
    result = check_news(api_key=None)
    assert result.status == STATUS_NO_KEY


def test_health_report_all_ok_false_when_any_source_fails(tmp_path):
    """HealthReport.all_ok() retorna False quando ao menos uma fonte falhou."""
    from data.api_health import STATUS_FAIL, STATUS_OK, HealthReport, SourceHealth

    report = HealthReport()
    report.sources["fred"] = SourceHealth(source="fred", status=STATUS_OK)
    report.sources["eia"] = SourceHealth(source="eia", status=STATUS_FAIL, message="HTTP 403")
    assert not report.all_ok()


def test_health_report_all_ok_true_when_all_sources_ok(tmp_path):
    """HealthReport.all_ok() retorna True quando todas as fontes estão ok."""
    from data.api_health import STATUS_OK, HealthReport, SourceHealth

    report = HealthReport()
    report.sources["fred"] = SourceHealth(source="fred", status=STATUS_OK)
    report.sources["nhtsa"] = SourceHealth(source="nhtsa", status=STATUS_OK)
    assert report.all_ok()


def test_health_report_to_dict_does_not_expose_api_keys(tmp_path):
    """HealthReport.to_dict() não inclui chaves de API nem valores sensíveis."""
    from data.api_health import STATUS_OK, HealthReport, SourceHealth

    report = HealthReport()
    report.sources["fred"] = SourceHealth(source="fred", status=STATUS_OK, message="HTTP 200 em 45 ms")
    payload = report.to_dict()
    payload_str = json.dumps(payload)
    # Verifica que nenhum campo típico de credencial está presente.
    for sensitive in ("api_key", "apiKey", "token", "secret", "password", "Authorization"):
        assert sensitive.lower() not in payload_str.lower()
