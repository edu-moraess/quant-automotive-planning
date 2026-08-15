from __future__ import annotations

import asyncio
import datetime
import json
import sys
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import analysis as analysis_module  # noqa: E402
import energy_intelligence as energy_module  # noqa: E402
import vehicle_intelligence as vehicle_module  # noqa: E402
from config import (  # noqa: E402
    DATA_DIR,
    ENERGY_SNAPSHOT,
    EPA_SNAPSHOT,
    MARKET_SNAPSHOT,
    MODEL_ARTIFACTS_DIR,
    PlanningAssumptions,
)
from data import FeatureBuilder, FeatureSettings, SourceName, TimeWindow, load_feature_source_config  # noqa: E402
from data.api_health import HealthReport, run_health_check  # noqa: E402
from data.feature_store import FeatureStore  # noqa: E402
from decision_intelligence import build_decision_intelligence  # noqa: E402
from presentation import fmt_month_display, format_temporal_display  # noqa: E402
from risk_engine import MonteCarloConfig, run_risk_engine  # noqa: E402
from robust_planning import RobustPlanningConfig, optimize_under_uncertainty  # noqa: E402
from scenarios import energy_price_sensitivity  # noqa: E402

FRED_SERIES_URL = analysis_module.FRED_SERIES_URL
EPA_DOWNLOAD_PAGE = vehicle_module.EPA_DOWNLOAD_PAGE
load_vehicle_data = vehicle_module.load_vehicle_data
filter_vehicles = vehicle_module.filter_vehicles
portfolio_kpis = vehicle_module.portfolio_kpis
brand_summary = vehicle_module.brand_summary
brand_registry = vehicle_module.brand_registry
segment_summary = vehicle_module.segment_summary
vehicle_universe_metadata = vehicle_module.vehicle_universe_metadata
load_energy_prices = energy_module.load_energy_prices
latest_energy_snapshot = energy_module.latest_energy_snapshot
energy_price_index = energy_module.energy_price_index
add_energy_cost_estimate = energy_module.add_energy_cost_estimate
energy_summary = energy_module.energy_summary
spearman_correlation_matrix = energy_module.spearman_correlation_matrix
strongest_spearman_pairs = energy_module.strongest_spearman_pairs

st.set_page_config(
    page_title="Quant Automotive Intelligence", page_icon="Q", layout="wide", initial_sidebar_state="expanded"
)

PRIMARY = "#14213D"
BLUE = "#1F4E79"
ORANGE = "#E87532"
TEAL = "#008A8A"
RED = "#C43D3D"
PURPLE = "#6959CD"
MUTED = "#667085"
GRID = "#E5EAF0"
MARKET_SOURCE_CACHE_SCHEMA_VERSION = 1

ENERGY_COLORS = {
    "Gasolina": "#577590",
    "Diesel": "#495867",
    "Eletricidade": "#6A5ACD",
    "Híbrido plug-in": "#00A6A6",
    "Etanol / E85": "#D68C45",
    "Gás natural": "#8AB17D",
    "Hidrogênio": "#2F75B5",
}


@st.cache_data(show_spinner=False)
def load_product_layer(epa_mtime: float, energy_mtime: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Carrega os snapshots de produto e energia; mtimes controlam a invalidação seletiva do cache."""
    raw_vehicles = load_vehicle_data(EPA_SNAPSHOT)
    prices = load_energy_prices(ENERGY_SNAPSHOT)
    return raw_vehicles, prices, add_energy_cost_estimate(raw_vehicles, prices)


@st.cache_data(show_spinner=False)
def load_model_artifacts(artifact_mtime: float) -> dict[str, pd.DataFrame | dict]:
    return {
        "summary": json.loads((MODEL_ARTIFACTS_DIR / "advanced_model_summary.json").read_text(encoding="utf-8")),
        "coefficients": pd.read_csv(MODEL_ARTIFACTS_DIR / "econometric_coefficients.csv"),
        "econometric_validation": pd.read_csv(MODEL_ARTIFACTS_DIR / "econometric_validation.csv", parse_dates=["data"]),
        "neural_validation": pd.read_csv(MODEL_ARTIFACTS_DIR / "neural_efficiency_validation.csv"),
        "vif": pd.read_csv(MODEL_ARTIFACTS_DIR / "econometric_vif.csv"),
        "importance": pd.read_csv(MODEL_ARTIFACTS_DIR / "neural_permutation_importance.csv"),
        "error_by_powertrain": pd.read_csv(MODEL_ARTIFACTS_DIR / "neural_error_by_powertrain.csv"),
    }


_API_HEALTH_PATH = DATA_DIR / "feature_store" / "api_health.json"
_API_HEALTH_ICONS = {"ok": "🟢", "falha": "🔴", "chave_ausente": "🟡"}
_API_HEALTH_LABELS = {"fred": "FRED", "eia": "EIA", "news": "News API", "nhtsa": "NHTSA"}
_FEATURES_TOML = ROOT / "config" / "features.toml"


def _build_feature_settings_from_secrets() -> FeatureSettings:
    """Constrói FeatureSettings lendo as chaves de st.secrets quando disponível."""
    try:
        if hasattr(st, "secrets") and st.secrets:
            return FeatureSettings.from_streamlit_secrets(dict(st.secrets))
    except Exception:
        pass
    return FeatureSettings()


def run_feature_refresh_from_secrets(
    sources: set[SourceName] | None = None,
    start: str = "2018-01-01",
) -> dict:
    """Executa o health check e a ingestão de features usando as chaves do Streamlit Cloud.

    Deve ser chamada apenas a partir de um botão na interface — não no carregamento inicial.
    Retorna um dict com o resumo da execução (sem expor credenciais).
    """
    settings = _build_feature_settings_from_secrets()
    source_config = load_feature_source_config(_FEATURES_TOML)
    selected = sources or {SourceName.FRED, SourceName.EIA, SourceName.NEWS, SourceName.NHTSA}

    # Health check antes da ingestão.
    health_report = run_health_check(
        fred_key=settings.secret_value("fred"),
        eia_key=settings.secret_value("eia"),
        news_key=settings.secret_value("news"),
        save_path=_API_HEALTH_PATH,
    )

    # Remove fontes indisponíveis (exceto FRED, que tem fallback local).
    from data.api_health import STATUS_FAIL, STATUS_NO_KEY  # noqa: PLC0415

    eligible = set(selected)
    for name, health in health_report.sources.items():
        try:
            sn = SourceName(name)
        except ValueError:
            continue
        if sn == SourceName.FRED:
            continue  # FRED sempre elegível — usa snapshot local se falhar
        if health.status in {STATUS_FAIL, STATUS_NO_KEY} and sn in eligible:
            eligible.discard(sn)

    # Executa a ingestão.
    as_of = pd.Timestamp(datetime.datetime.now(datetime.UTC))
    builder = FeatureBuilder(settings, source_config)
    result = asyncio.run(builder.build(TimeWindow(start=pd.Timestamp(start), as_of=as_of), sources=eligible))
    return {
        "as_of": result.as_of.isoformat(),
        "market_feature_rows": len(result.market_features),
        "event_feature_rows": len(result.event_features),
        "sources_run": [s.value for s in eligible],
        "health": {name: h.status for name, h in health_report.sources.items()},
    }


@st.cache_data(show_spinner=False)
def load_api_health_status(health_mtime: float) -> list[dict]:
    """Lê o api_health.json local sem executar novas requisições."""
    report = HealthReport.load(_API_HEALTH_PATH)
    if report is None:
        return []
    rows = []
    for name, health in report.sources.items():
        icon = _API_HEALTH_ICONS.get(health.status, "⚪")
        label = _API_HEALTH_LABELS.get(name, name.upper())
        latency = f"{health.latency_ms:.0f} ms" if health.latency_ms is not None else "—"
        rows.append({"icon": icon, "fonte": label, "status": health.status, "latência": latency})
    return rows


@st.cache_data(show_spinner=False)
def load_feature_source_status(manifest_mtime: float) -> pd.DataFrame:
    """Lê o manifesto local da camada de features sem executar novas requisições."""
    manifest = FeatureStore(DATA_DIR / "feature_store").load_manifest()
    sources = manifest.get("sources", {})
    if not isinstance(sources, dict) or not sources:
        return pd.DataFrame()
    rows = []
    for source, values in sources.items():
        if not isinstance(values, dict):
            continue
        rows.append(
            {
                "Fonte": source.upper(),
                "Status": values.get("state", "—"),
                "Linhas": values.get("rows", 0),
                "Cobertura": fmt_month_display(pd.Timestamp(values["coverage_end"]))
                if values.get("coverage_end")
                else "—",
                "Mensagem": values.get("message") or "—",
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def load_nhtsa_risk_snapshot(manifest_mtime: float) -> pd.DataFrame:
    """Agrega o monitoramento NHTSA persistido sem acionar a API no dashboard."""
    source_path = DATA_DIR / "feature_store" / f"source={SourceName.NHTSA.value}"
    partitions = sorted(source_path.rglob("data.parquet")) if source_path.exists() else []
    if not partitions:
        return pd.DataFrame()
    events = pd.concat([pd.read_parquet(path) for path in partitions], ignore_index=True)
    events["disponivel_em"] = pd.to_datetime(events["disponivel_em"], errors="coerce")
    events = events.dropna(subset=["disponivel_em", "marca", "modelo", "ano_modelo", "tipo_evento"])
    if events.empty:
        return pd.DataFrame()
    index_columns = ["marca", "modelo", "ano_modelo"]
    counts = (
        events.groupby([*index_columns, "tipo_evento"], as_index=False)["evento_id"]
        .nunique()
        .pivot(index=index_columns, columns="tipo_evento", values="evento_id")
        .fillna(0)
        .rename(columns={"recall": "recalls", "complaint": "reclamacoes"})
    )
    counts["recalls"] = counts.get("recalls", 0)
    counts["reclamacoes"] = counts.get("reclamacoes", 0)
    last_event = events.groupby(index_columns, as_index=True)["disponivel_em"].max().rename("ultimo_evento")
    result = counts.join(last_event).reset_index()
    result["indice_risco"] = 2 * result["recalls"] + result["reclamacoes"]
    return result.sort_values(["indice_risco", "ultimo_evento"], ascending=[False, False]).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_market_source_cached(
    source_schema_version: int,
    refresh_run_id: int,
    market_mtime: float,
    allow_online: bool,
) -> dict:
    """Obtém TOTALSA e invalida apenas a camada de ingestão quando a atualização é solicitada."""
    started = perf_counter()
    raw, provenance = analysis_module.read_fred_with_provenance(
        fallback_path=MARKET_SNAPSHOT,
        allow_online=allow_online,
    )
    data, quality = analysis_module.prepare_data(raw)
    refresh = analysis_module.market_refresh_summary(data, MARKET_SNAPSHOT, provenance)
    refresh["fetch_duration_seconds"] = perf_counter() - started
    return {"data": data, "quality": quality, "market_refresh": refresh}


@st.cache_data(show_spinner=False)
def run_forecast_cached(data: pd.DataFrame, n_folds: int, test_size: int, horizon: int) -> dict:
    """Executa diagnóstico, backtest walk-forward e forecast probabilístico quando série ou hiperparâmetros mudam."""
    diagnostics = analysis_module.compute_diagnostics(data)
    backtest = analysis_module.run_backtest(data, n_folds, test_size)
    forecast, simulations = analysis_module.make_forecast(data, backtest, horizon, bootstrap_replicas=2000, seed=42)
    return {"diagnostics": diagnostics, "backtest": backtest, "forecast": forecast, "simulations": simulations}


@st.cache_data(show_spinner=False)
def run_planning_cached(
    forecast: pd.DataFrame,
    participation: float,
    capacity: int,
    initial_inventory: int,
    production_cost: float,
    inventory_cost: float,
    backlog_cost: float,
    overtime_capacity: int,
    overtime_cost: float,
    safety_stock: int,
    safety_stock_penalty: float,
    setup_cost: float,
) -> dict:
    """Resolve a otimização de produção quando forecast ou hipóteses operacionais são alterados."""
    return analysis_module.build_production_plan(
        forecast,
        participation,
        capacity,
        initial_inventory,
        production_cost,
        inventory_cost,
        backlog_cost,
        overtime_capacity=overtime_capacity,
        overtime_cost=overtime_cost,
        safety_stock=safety_stock,
        safety_stock_penalty=safety_stock_penalty,
        setup_cost=setup_cost,
    )


@st.cache_data(show_spinner=False)
def run_risk_cached(
    simulations: np.ndarray,
    participation: float,
    capacity: int,
    initial_inventory: int,
    backlog_cost: float,
    overtime_capacity: int,
    n_simulations: int = 5_000,
    seed: int = 42,
) -> dict:
    """Calcula risco operacional sem chamar o solver PuLP em cada rerun da interface."""
    assumptions = PlanningAssumptions(
        participation=participation,
        regular_capacity=capacity,
        overtime_capacity=overtime_capacity,
        initial_inventory=initial_inventory,
        backlog_cost=backlog_cost,
    )
    result = run_risk_engine(
        simulations,
        assumptions,
        market_share=participation,
        config=MonteCarloConfig(n_simulations=n_simulations, seed=seed),
    )
    return {"metrics": result.metrics, "risk_table": result.risk_table, "metadata": result.metadata}


@st.cache_data(show_spinner=False)
def run_robust_planning_cached(
    simulations: np.ndarray,
    participation: float,
    capacity: int,
    initial_inventory: int,
    production_cost: float,
    inventory_cost: float,
    backlog_cost: float,
    overtime_capacity: int,
    overtime_cost: float,
    safety_stock: int,
    safety_stock_penalty: float,
    setup_cost: float,
    n_paths: int,
    seed: int = 42,
) -> dict:
    """Resolve amostra de caminhos com PuLP somente quando o usuário ativa a opção."""
    assumptions = PlanningAssumptions(
        participation=participation,
        regular_capacity=capacity,
        overtime_capacity=overtime_capacity,
        initial_inventory=initial_inventory,
        production_cost=production_cost,
        inventory_cost=inventory_cost,
        backlog_cost=backlog_cost,
        safety_stock=safety_stock,
        safety_stock_penalty=safety_stock_penalty,
        setup_cost=setup_cost,
        overtime_cost=overtime_cost,
    )
    result = optimize_under_uncertainty(
        simulations,
        assumptions,
        market_share=participation,
        config=RobustPlanningConfig(n_paths_to_optimize=n_paths, seed=seed),
    )
    return {
        "metrics": result["metrics"],
        "summary": result["summary"],
        "metadata": result["metadata"],
        "representative_solutions": result["representative_solutions"],
    }


PLOT_CONFIG = {
    "displaylogo": False,
    "displayModeBar": "hover",
    "scrollZoom": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
}

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
      html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
      .stApp { background: #F6F8FB; }
      [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E5EAF0; }
      .block-container { max-width: 1120px; padding-top: 1.1rem; padding-bottom: 3rem; }
      h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; color: #14213D; letter-spacing: -0.025em; }
      .hero { background: linear-gradient(112deg, #14213D 0%, #1F4E79 68%, #2D75B3 100%); border-radius: 14px; color: #fff; padding: 16px 22px; margin-bottom: 9px; box-shadow: 0 9px 22px rgba(20,33,61,.10); }
      .hero h1 { color: #fff; margin: 0; font-size: 1.4rem; line-height: 1.15; }
      .hero p { margin: 5px 0 0; color: rgba(255,255,255,.86); line-height: 1.42; max-width: 850px; font-size: .88rem; }
      .section-kicker { color: #E87532; font-weight: 700; font-size: .7rem; letter-spacing: .13em; text-transform: uppercase; margin-top: 7px; }
      .section-title { font-family: 'Space Grotesk', sans-serif; color: #14213D; font-size: 1.35rem; font-weight: 700; margin: 4px 0 12px; }
      .insight { background: #FFFFFF; border: 1px solid #E5EAF0; border-left: 4px solid #E87532; border-radius: 10px; padding: 14px 17px; color: #344054; line-height: 1.55; margin: 12px 0 18px; }
      .note { background: #EEF5FC; border: 1px solid #D7E5F4; border-radius: 10px; padding: 13px 15px; color: #294D70; line-height: 1.5; font-size: .9rem; margin: 12px 0 18px; }
      .vertical-metric { border-bottom: 1px solid #E5EAF0; padding: 8px 0 12px; }
      .compact-fact { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; padding: 10px 0; border-bottom: 1px solid #E5EAF0; }
      .compact-fact:last-child { border-bottom: 0; }
      .compact-fact-label { color: #667085; font-size: .84rem; font-weight: 600; }
      .compact-fact-value { color: #14213D; font-family: 'Space Grotesk', sans-serif; font-size: 1.45rem; font-weight: 700; letter-spacing: -.02em; }
      .compact-fact-detail { color: #397C59; font-size: .8rem; }
      div[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E5EAF0; border-radius: 11px; padding: 13px 15px; margin: 8px 0; box-shadow: 0 3px 10px rgba(20,33,61,.025); }
      div[data-testid="stMetricLabel"] p { white-space: normal; color: #667085; line-height: 1.2; }
      div[data-testid="stMetricValue"] { color: #14213D; font-family: 'Space Grotesk', sans-serif; }
      .stTabs [data-baseweb="tab-list"] { gap: 3px; border-bottom: 1px solid #DCE3EA; overflow-x: auto; }
      .stTabs [data-baseweb="tab"] { min-height: 45px; padding: 0 11px; color: #667085; font-weight: 600; font-size: .85rem; }
      .stTabs [aria-selected="true"] { color: #14213D; border-bottom-color: #E87532; }
      /* Controles Plotly: ficam invisíveis até o hover, verticais, transparentes e fora das legendas. */
      .js-plotly-plot .plotly .modebar { display: flex !important; flex-direction: column !important; gap: 1px !important; background: transparent !important; top: 58px !important; right: 6px !important; left: auto !important; }
      .js-plotly-plot .plotly .modebar-group { display: flex !important; flex-direction: column !important; background: transparent !important; margin: 0 !important; }
      .js-plotly-plot .plotly .modebar-btn { background: transparent !important; opacity: 0.12 !important; padding: 2px !important; }
      .js-plotly-plot .plotly .modebar:hover .modebar-btn { opacity: 0.72 !important; }
      .js-plotly-plot .plotly .modebar-btn:hover { opacity: 1 !important; background: rgba(255,255,255,.72) !important; }
      .footer { color: #98A2B3; border-top: 1px solid #E5EAF0; padding-top: 15px; margin-top: 28px; font-size: .78rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def fmt_int(value: float | int) -> str:
    return "—" if pd.isna(value) else f"{value:,.0f}".replace(",", ".")


def fmt_decimal(value: float, digits: int = 1) -> str:
    return "—" if pd.isna(value) else f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_usd(value: float, digits: int = 2) -> str:
    return "—" if pd.isna(value) else f"US$ {value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.1f}%".replace(".", ",")


def vertical_metric(label: str, value: str, detail: str | None = None) -> None:
    st.markdown('<div class="vertical-metric">', unsafe_allow_html=True)
    st.metric(label, value, detail)
    st.markdown("</div>", unsafe_allow_html=True)


def compact_fact(label: str, value: str, detail: str | None = None) -> None:
    """Renderiza um KPI compacto em fluxo vertical para preservar a legibilidade."""
    detail_markup = f'<span class="compact-fact-detail">{detail}</span>' if detail else ""
    st.markdown(
        f'<div class="compact-fact"><span class="compact-fact-label">{label}</span>'
        f'<span class="compact-fact-value">{value}</span>{detail_markup}</div>',
        unsafe_allow_html=True,
    )


def style_chart(fig: go.Figure, height: int = 420, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font={"family": "DM Sans, sans-serif", "color": PRIMARY},
        margin={"l": 16, "r": 24, "t": 54, "b": 58},
        showlegend=legend,
        legend={"orientation": "h", "y": -0.22, "x": 0, "font": {"size": 11}},
        hoverlabel={"font": {"family": "DM Sans, sans-serif"}},
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def forecast_chart(history: pd.DataFrame, forecast: pd.DataFrame, winner: str) -> go.Figure:
    recent = history.tail(48)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=recent["data"],
            y=recent["vendas_saar_milhoes"],
            mode="lines",
            name="Histórico",
            line={"color": BLUE, "width": 2.25},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["data"],
            y=forecast["cenario_conservador"],
            mode="lines",
            name="Faixa p10–p90",
            line={"color": "rgba(232,117,50,.26)", "width": 1},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["data"],
            y=forecast["cenario_otimista"],
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(232,117,50,.17)",
            line={"color": "rgba(232,117,50,.26)", "width": 1},
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["data"],
            y=forecast["cenario_base"],
            mode="lines+markers",
            name="Projeção base",
            line={"color": ORANGE, "width": 2.6},
            marker={"size": 5},
        )
    )
    fig.add_vline(x=history["data"].max(), line_dash="dot", line_color=PRIMARY, line_width=1)
    fig.update_layout(title=f"Projeção de mercado · {winner}", yaxis_title="Milhões de unidades SAAR")
    return style_chart(fig, 430)


def brand_bar_chart(summary: pd.DataFrame) -> go.Figure:
    display = summary.nlargest(15, "configuracoes").sort_values("configuracoes")
    fig = px.bar(
        display,
        x="configuracoes",
        y="make",
        orientation="h",
        color="mpg_medio",
        color_continuous_scale=["#BFD3E6", BLUE, ORANGE],
        labels={"make": "Marca EPA", "configuracoes": "Configurações", "mpg_medio": "MPG/MPGe médio"},
        title="Amplitude de portfólio no universo filtrado",
    )
    fig.update_layout(coloraxis_colorbar={"title": "MPG/MPGe", "len": 0.7})
    return style_chart(fig, 520, legend=False)


def brand_position_chart(summary: pd.DataFrame) -> go.Figure:
    display = (
        summary.dropna(subset=["mpg_medio", "co2_medio_g_milha"])
        .query("configuracoes >= 3")
        .nlargest(55, "configuracoes")
    )
    fig = px.scatter(
        display,
        x="co2_medio_g_milha",
        y="mpg_medio",
        size="configuracoes",
        color="participacao_eletrificada_pct",
        hover_name="make",
        hover_data={
            "modelos": True,
            "segmentos": True,
            "ano_final": True,
            "co2_medio_g_milha": ":.0f",
            "mpg_medio": ":.1f",
            "participacao_eletrificada_pct": ":.1f",
        },
        color_continuous_scale=["#C8D8E8", TEAL, PURPLE],
        labels={
            "co2_medio_g_milha": "CO₂ de escapamento (g/mi)",
            "mpg_medio": "MPG/MPGe médio",
            "participacao_eletrificada_pct": "Mix eletrificado (%)",
        },
        title="Posicionamento técnico por marca",
    )
    fig.update_traces(marker={"opacity": 0.78, "line": {"color": "white", "width": 0.5}})
    return style_chart(fig, 500, legend=False)


def segment_chart(summary: pd.DataFrame) -> go.Figure:
    display = summary.nlargest(15, "configuracoes").sort_values("mpg_medio")
    fig = px.bar(
        display,
        x="mpg_medio",
        y="VClass",
        orientation="h",
        color="co2_medio_g_milha",
        color_continuous_scale="YlOrRd",
        labels={"VClass": "Segmento EPA", "mpg_medio": "MPG/MPGe médio", "co2_medio_g_milha": "CO₂ (g/mi)"},
        title="Eficiência por segmento",
    )
    return style_chart(fig, 540, legend=False)


def price_index_chart(index_data: pd.DataFrame) -> go.Figure:
    fig = px.line(
        index_data,
        x="data",
        y="indice_base_100",
        color="energia",
        color_discrete_map={
            "Gasolina regular": ENERGY_COLORS["Gasolina"],
            "Diesel": ENERGY_COLORS["Diesel"],
            "Eletricidade": ENERGY_COLORS["Eletricidade"],
        },
        labels={"data": "Data", "indice_base_100": "Índice (início = 100)", "energia": "Energia"},
        title="Variação relativa de preços de energia · últimos 48 meses",
    )
    fig.add_hline(y=100, line_dash="dot", line_color=MUTED, line_width=1)
    fig.update_traces(line={"width": 2.2})
    return style_chart(fig, 440)


def energy_cost_chart(summary: pd.DataFrame) -> go.Figure:
    display = summary.dropna(subset=["custo_energia_100mi_mediano_usd"]).sort_values("custo_energia_100mi_mediano_usd")
    fig = px.bar(
        display,
        x="custo_energia_100mi_mediano_usd",
        y="fonte_energia",
        orientation="h",
        color="fonte_energia",
        color_discrete_map=ENERGY_COLORS,
        text="custo_energia_100mi_mediano_usd",
        labels={"fonte_energia": "Fonte de energia", "custo_energia_100mi_mediano_usd": "US$ por 100 milhas"},
        title="Custo energético de referência por 100 milhas",
    )
    fig.update_traces(texttemplate="US$ %{x:.2f}", textposition="outside", cliponaxis=False)
    fig.update_xaxes(title="US$ por 100 milhas")
    fig.update_yaxes(title=None)
    return style_chart(fig, 410, legend=False)


def correlation_chart(correlations: pd.DataFrame) -> go.Figure:
    labels = list(correlations.columns)
    fig = go.Figure(
        go.Heatmap(
            z=correlations.values,
            x=labels,
            y=labels,
            zmin=-1,
            zmax=1,
            colorscale=[[0, "#C43D3D"], [0.5, "#F4F6F8"], [1, "#1F4E79"]],
            colorbar={"title": "ρ"},
            text=np.round(correlations.values, 2),
            texttemplate="%{text}",
            textfont={"size": 11},
            hovertemplate="%{x}<br>%{y}<br>ρ Spearman: %{z:.2f}<extra></extra>",
        )
    )
    fig.update_layout(title="Associações entre eficiência, custo, emissões e motorização")
    return style_chart(fig, 520, legend=False)


def history_chart(data: pd.DataFrame) -> go.Figure:
    data_start = pd.Timestamp(data["data"].min())
    data_end = pd.Timestamp(data["data"].max())
    decade_years = list(range(((data_start.year // 10) + 1) * 10, data_end.year, 10))
    tick_values = [pd.Timestamp(year=year, month=1, day=1) for year in decade_years] + [data_end]
    tick_labels = [str(year) for year in decade_years] + [data_end.strftime("%b/%Y")]
    fig = px.line(
        data,
        x="data",
        y="vendas_saar_milhoes",
        labels={"data": "Data", "vendas_saar_milhoes": "Milhões SAAR"},
        title=f"Mercado agregado de veículos leves · histórico até {data_end:%b/%Y}",
    )
    fig.update_traces(line={"color": BLUE, "width": 2.25})
    fig.update_xaxes(range=[data_start, data_end], tickmode="array", tickvals=tick_values, ticktext=tick_labels)
    return style_chart(fig, 440, legend=False)


def backtest_chart(summary: pd.DataFrame, winner: str) -> go.Figure:
    colors = [ORANGE if value == winner else "#B8C2D1" for value in summary["modelo"]]
    fig = go.Figure(
        go.Bar(
            x=summary["modelo"],
            y=summary["mape_medio"],
            error_y={"type": "data", "array": summary["mape_desvio"].fillna(0)},
            marker_color=colors,
            text=[f"{value:.2f}%" for value in summary["mape_medio"]],
            textposition="outside",
        )
    )
    fig.update_layout(title="Erro médio fora da amostra", xaxis_title=None, yaxis_title="MAPE (%)")
    return style_chart(fig, 410, legend=False)


def residual_chart(residuals: np.ndarray) -> go.Figure:
    fig = px.histogram(
        x=residuals,
        nbins=14,
        labels={"x": "Resíduo (milhões SAAR)", "count": "Frequência"},
        title="Distribuição dos resíduos fora da amostra",
    )
    fig.update_traces(marker_color=TEAL, marker_line_color="white", marker_line_width=1)
    fig.add_vline(x=0, line_color=PRIMARY, line_width=1)
    return style_chart(fig, 360, legend=False)


def acf_chart(values: pd.DataFrame) -> go.Figure:
    display = values.iloc[:25]
    fig = px.bar(
        display, x="lag", y="acf", labels={"lag": "Defasagem", "acf": "Autocorrelação"}, title="ACF dos resíduos"
    )
    fig.update_traces(marker_color=TEAL)
    fig.add_hline(y=0, line_color=PRIMARY, line_width=1)
    return style_chart(fig, 360, legend=False)


def production_chart(plan: pd.DataFrame, capacity: int) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.15,
        subplot_titles=["Demanda de referência e produção", "Estoque e demanda pendente"],
    )
    fig.add_trace(
        go.Bar(x=plan["data"], y=plan["demanda_planejada_veiculos"], name="Demanda", marker_color="#BFD3E6"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=plan["data"],
            y=plan["producao_recomendada"],
            name="Produção",
            mode="lines+markers",
            line={"color": ORANGE, "width": 2.4},
        ),
        row=1,
        col=1,
    )
    fig.add_hline(y=capacity, line_dash="dash", line_color=PRIMARY, row=1, col=1)
    fig.add_trace(
        go.Scatter(
            x=plan["data"],
            y=plan["estoque_final"],
            name="Estoque",
            mode="lines+markers",
            line={"color": BLUE, "width": 2},
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=plan["data"],
            y=plan["demanda_pendente"],
            name="Pendente",
            mode="lines+markers",
            line={"color": RED, "width": 2, "dash": "dot"},
        ),
        row=2,
        col=1,
    )
    fig.update_yaxes(title_text="Veículos", row=1, col=1)
    fig.update_yaxes(title_text="Veículos", row=2, col=1)
    fig.update_layout(title="Cenário operacional parametrizado")
    return style_chart(fig, 650)


def sensitivity_chart(sensitivity: pd.DataFrame) -> go.Figure:
    display = sensitivity.copy()
    display.index = [fmt_int(index) for index in display.index]
    display.columns = [f"{float(column):.0%}" for column in display.columns]
    fig = px.imshow(
        display,
        text_auto=".0f",
        aspect="auto",
        color_continuous_scale="YlOrRd",
        labels={"x": "Participação de mercado", "y": "Capacidade mensal", "color": "Backlog"},
        title="Sensibilidade do backlog acumulado",
    )
    fig.update_traces(textfont={"size": 11})
    return style_chart(fig, 410, legend=False)


def econometric_validation_chart(validation: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=validation["data"],
            y=validation["vendas_saar_milhoes"],
            mode="lines+markers",
            name="Observado",
            line={"color": BLUE, "width": 2.4},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=validation["data"],
            y=validation["previsto_ols"],
            mode="lines+markers",
            name="OLS com energia",
            line={"color": ORANGE, "width": 2.4, "dash": "dash"},
        )
    )
    fig.update_layout(title="Validação temporal do modelo econométrico", yaxis_title="Milhões de unidades SAAR")
    return style_chart(fig, 440)


def neural_validation_chart(validation: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        validation,
        x="comb08",
        y="previsto_mlp",
        color="erro_abs",
        color_continuous_scale="YlOrRd",
        opacity=0.55,
        labels={
            "comb08": "Eficiência EPA observada (MPG/MPGe)",
            "previsto_mlp": "Eficiência prevista pela rede neural",
            "erro_abs": "Erro absoluto",
        },
        title="Rede neural: eficiência prevista versus observada",
    )
    maximum = max(float(validation["comb08"].max()), float(validation["previsto_mlp"].max()))
    fig.add_trace(
        go.Scatter(
            x=[0, maximum],
            y=[0, maximum],
            mode="lines",
            name="Previsão perfeita",
            line={"color": PRIMARY, "dash": "dot"},
        )
    )
    fig.update_traces(marker={"size": 6})
    return style_chart(fig, 500)


try:
    raw_vehicles, energy_prices, vehicle_data = load_product_layer(
        EPA_SNAPSHOT.stat().st_mtime, ENERGY_SNAPSHOT.stat().st_mtime
    )
    artifact_mtime = max(path.stat().st_mtime for path in MODEL_ARTIFACTS_DIR.glob("*.csv"))
    artifacts = load_model_artifacts(artifact_mtime)
    model_summary_data = artifacts["summary"]
    econometric_coefficients = artifacts["coefficients"]
    econometric_validation = artifacts["econometric_validation"]
    neural_validation = artifacts["neural_validation"]
    econometric_vif = artifacts["vif"]
    neural_importance = artifacts["importance"]
    neural_error_by_powertrain = artifacts["error_by_powertrain"]
    data_health = pd.read_json(ROOT / "data" / "data_health.json")
except Exception as error:
    st.error(f"Não foi possível carregar a camada de dados: {error}")
    st.stop()

metadata = vehicle_universe_metadata(vehicle_data)
year_bounds = (metadata["ano_inicial"], metadata["ano_final"])
feature_manifest = DATA_DIR / "feature_store" / "manifest.json"
feature_manifest_mtime = feature_manifest.stat().st_mtime if feature_manifest.exists() else 0.0
feature_status = load_feature_source_status(feature_manifest_mtime)
nhtsa_risk_snapshot = load_nhtsa_risk_snapshot(feature_manifest_mtime)

with st.sidebar:
    st.markdown("## QUANT")
    st.caption("Automotive Intelligence & Planning")

    # --- Status das fontes de dados (topo da sidebar) ---
    health_mtime = _API_HEALTH_PATH.stat().st_mtime if _API_HEALTH_PATH.exists() else 0.0
    api_health_rows = load_api_health_status(health_mtime)
    if api_health_rows:
        status_line = " · ".join(f"{r['icon']} {r['fonte']}" for r in api_health_rows)
        st.caption(status_line)
    if feature_manifest.exists():
        import zoneinfo  # noqa: PLC0415

        _tz_sp = zoneinfo.ZoneInfo("America/Sao_Paulo")
        _last_update = (
            datetime.datetime.fromtimestamp(feature_manifest_mtime, tz=datetime.UTC)
            .astimezone(_tz_sp)
            .strftime("%d/%m/%Y %H:%M")
        )
        st.caption(f"⏱ Features: {_last_update} (SP)")

    # Botão de atualização de features — usa chaves do Streamlit Cloud.
    if st.button(
        "↺ Atualizar features",
        key="refresh_features_btn",
        help="Executa health check e atualiza FRED · EIA · News · NHTSA com as chaves do Streamlit Cloud Secrets.",
        use_container_width=True,
    ):
        with st.spinner("Verificando APIs e atualizando feature store..."):
            try:
                summary = run_feature_refresh_from_secrets()
                st.success(
                    f"Atualizado — {summary['market_feature_rows']} linhas de mercado, "
                    f"{summary['event_feature_rows']} de eventos."
                )
                load_api_health_status.clear()
                load_feature_source_status.clear()
                load_nhtsa_risk_snapshot.clear()
                st.rerun()
            except Exception as _refresh_err:
                st.error(f"Falha: {_refresh_err}")

    st.markdown("---")

    # --- Formulário de produto (EPA) — colapsável ---
    with st.expander("🔍 Universo de produto", expanded=False):
        with st.form("product_filters"):
            selected_years = st.slider(
                "Ano-modelo", min_value=year_bounds[0], max_value=year_bounds[1], value=year_bounds
            )
            selected_makes = st.multiselect(
                "Marcas EPA", sorted(vehicle_data["make"].unique()), placeholder="Todo o catálogo"
            )
            selected_powertrains = st.multiselect(
                "Tecnologia", sorted(vehicle_data["powertrain"].unique()), placeholder="Todas"
            )
            selected_segments = st.multiselect(
                "Segmento EPA", sorted(vehicle_data["VClass"].unique()), placeholder="Todos"
            )
            product_updated = st.form_submit_button("Aplicar recorte de produto", width="stretch")
            st.caption("Atualiza Resumo, Portfólio e Energia & Combustível.")
            if product_updated:
                st.success("Recorte EPA aplicado.")

    # --- Formulário de forecast e planejamento — colapsável ---
    robust_planning_enabled = False
    robust_paths = 50
    with st.expander("📈 Forecast & Planejamento", expanded=False):
        with st.form("market_and_planning"):
            st.markdown("**Forecast**")
            horizon = st.slider("Horizonte de projeção", 3, 18, 6)
            n_folds = st.slider("Dobras walk-forward", 2, 8, 4)
            test_size = st.slider("Meses por dobra", 3, 12, 6)
            allow_online = st.checkbox(
                "Consultar FRED online",
                value=False,
                help="A fonte é consultada somente ao atualizar este bloco. Se falhar, o snapshot versionado é usado.",
            )
            st.markdown("**Planejamento · ASSUMPTIONS**")
            participation_pct = st.slider("Participação assumida", 1, 20, 8, 1, format="%d%%")
            capacity = st.number_input("Capacidade regular mensal", 10_000, 300_000, 110_000, 5_000)
            overtime_capacity = st.number_input("Capacidade extra mensal", 0, 150_000, 0, 5_000)
            initial_inventory = st.number_input("Estoque inicial", 0, 500_000, 15_000, 5_000)
            safety_stock = st.number_input("Estoque de segurança", 0, 300_000, 0, 5_000)
            with st.expander("Custos (US$ por veículo / período)"):
                production_cost = st.number_input("Produção regular", 0, 100_000, 25_000, 500)
                overtime_cost = st.number_input("Produção extra", 0, 120_000, 30_000, 500)
                inventory_cost = st.number_input("Estoque", 0, 10_000, 350, 50)
                backlog_cost = st.number_input("Backlog", 0, 200_000, 45_000, 500)
                safety_stock_penalty = st.number_input("Desvio de segurança", 0, 50_000, 1_000, 100)
                setup_cost = st.number_input("Setup mensal", 0, 1_000_000, 0, 5_000)
            st.markdown("**Risco e otimização robusta**")
            robust_planning_enabled = st.checkbox(
                "Resolver amostra de caminhos com PuLP",
                value=False,
                help="Ativa a integração Monte Carlo → PuLP. O custo computacional cresce com o número de caminhos.",
            )
            robust_paths = st.slider("Caminhos a otimizar", 10, 200, 50, 10, disabled=not robust_planning_enabled)
            market_updated = st.form_submit_button("Atualizar forecast e planejamento", width="stretch")
            if market_updated:
                st.session_state["market_analysis_run_id"] = st.session_state.get("market_analysis_run_id", 0) + 1
                st.success("Forecast e planejamento atualizados.")

    st.markdown("---")
    st.markdown(f"[Mercado · FRED]({FRED_SERIES_URL})")
    st.markdown(f"[Produto · EPA]({EPA_DOWNLOAD_PAGE})")
    st.caption(
        "Filtros EPA não são convertidos em vendas por marca. Mercado agregado, artefatos de modelos e método mantêm seus próprios contratos de dados."
    )

filtered = filter_vehicles(vehicle_data, selected_years, selected_makes, selected_powertrains, selected_segments)
if filtered.empty:
    st.warning("Os filtros atuais não retornaram configurações EPA. Ajuste o recorte na lateral.")
    st.stop()
kpis = portfolio_kpis(filtered)
brands = brand_summary(filtered)
segments = segment_summary(filtered)
energy_by_source = energy_summary(filtered)
correlations, pair_counts = spearman_correlation_matrix(filtered)
strong_pairs = strongest_spearman_pairs(correlations, pair_counts)
price_latest = latest_energy_snapshot(energy_prices)
price_index = energy_price_index(energy_prices)
registry = brand_registry(vehicle_data)
energy_sensitivity = energy_price_sensitivity(filtered, energy_prices)

try:
    with st.spinner("Consultando FRED e reutilizando a modelagem quando a série não mudou..."):
        market_source = load_market_source_cached(
            MARKET_SOURCE_CACHE_SCHEMA_VERSION,
            st.session_state.get("market_analysis_run_id", 0),
            MARKET_SNAPSHOT.stat().st_mtime,
            allow_online,
        )
        market_model = run_forecast_cached(market_source["data"], n_folds, test_size, horizon)
        participation = participation_pct / 100
        production = run_planning_cached(
            market_model["forecast"],
            participation,
            int(capacity),
            int(initial_inventory),
            float(production_cost),
            float(inventory_cost),
            float(backlog_cost),
            int(overtime_capacity),
            float(overtime_cost),
            int(safety_stock),
            float(safety_stock_penalty),
            float(setup_cost),
        )
        risk = run_risk_cached(
            market_model["simulations"],
            participation,
            int(capacity),
            int(initial_inventory),
            float(backlog_cost),
            int(overtime_capacity),
        )
        robust = (
            run_robust_planning_cached(
                market_model["simulations"],
                participation,
                int(capacity),
                int(initial_inventory),
                float(production_cost),
                float(inventory_cost),
                float(backlog_cost),
                int(overtime_capacity),
                float(overtime_cost),
                int(safety_stock),
                float(safety_stock_penalty),
                float(setup_cost),
                int(robust_paths),
            )
            if robust_planning_enabled
            else None
        )
        market = {
            **market_source,
            **market_model,
            "production": production,
            "risk": risk,
            "robust_planning": robust,
            "parameters": {"bootstrap_method": market_model["forecast"].attrs.get("bootstrap_method")},
        }
except Exception as error:
    st.error(f"Não foi possível executar a camada de mercado: {error}")
    st.stop()

history = market["data"]
backtest = market["backtest"]
forecast = market["forecast"]
production = market["production"]
plan = production["plan"]
scenarios = production["scenarios"]
summary = backtest["summary"]
winner = backtest["winner"]
summary_display = summary.copy()
winner_metrics = summary.loc[summary["modelo"].eq(winner)].iloc[0]
base_scenario = scenarios.loc[scenarios["Cenário"] == "Base"].iloc[0]
planning_decision = production["decision"]
market_refresh = market["market_refresh"]
risk = market["risk"]
robust_planning = market["robust_planning"]
decision_intelligence = build_decision_intelligence(
    forecast_metrics={
        "mape_pct": float(winner_metrics["mape_medio"]),
        "coverage_p10_p90": backtest["prequential_interval_quality"].get("coverage_p10_p90"),
    },
    risk_metrics=risk["metrics"],
    robust_metrics=robust_planning["metrics"]
    if robust_planning is not None
    else {"optimization_status": "not_integrated"},
    scenario_table=scenarios,
    assumptions={"market_share_status": "assumed"},
)
market_source_caption = (
    f"Série FRED em uso: {market_refresh['source_label']} · "
    f"{fmt_int(market_refresh['observations'])} observações · "
    f"cobertura {market_refresh['data_start']}–{market_refresh['data_end']}."
)
product_scope_terms = [f"anos {selected_years[0]}–{selected_years[1]}"]
if selected_makes:
    product_scope_terms.append(f"{len(selected_makes)} marca(s)")
if selected_powertrains:
    product_scope_terms.append(f"{len(selected_powertrains)} tecnologia(s)")
if selected_segments:
    product_scope_terms.append(f"{len(selected_segments)} segmento(s)")
product_scope_caption = (
    f"Recorte EPA aplicado: {fmt_int(kpis['configuracoes'])} configurações · "
    f"{' · '.join(product_scope_terms)}. Atualiza Resumo, Portfólio e Energia & Combustível."
)

st.markdown(
    """
    <div class="hero">
      <h1>Automotive Intelligence</h1>
      <p>Mercado, produto, energia e planejamento quantitativo.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
if market_refresh["source_status"] == "ONLINE":
    source_status = (
        f"FRED · online · {fmt_int(market_refresh['observations'])} observações · "
        f"{market_refresh['data_start']}–{market_refresh['data_end']}"
    )
else:
    source_status = (
        f"FRED · snapshot local · {fmt_int(market_refresh['observations'])} observações · "
        f"{market_refresh['data_start']}–{market_refresh['data_end']}"
    )
with st.expander(source_status):
    if market_refresh["source_status"] == "ONLINE":
        refreshed_at = pd.Timestamp(market_refresh["retrieved_at_utc"]).strftime("%d/%m/%Y %H:%M UTC")
        variation = (
            f"{fmt_int(market_refresh['new_observations'])} observações novas e "
            f"{fmt_int(market_refresh['revised_observations'])} revisadas frente ao snapshot."
            if market_refresh["new_observations"] or market_refresh["revised_observations"]
            else "A fonte online coincide com o snapshot; por isso os resultados permanecem iguais."
        )
        st.caption(
            f"Consulta concluída em {market_refresh['fetch_duration_seconds']:.1f}s, às {refreshed_at}. {variation}"
        )
    else:
        reason = market_refresh["fallback_reason"] or "Atualização online não solicitada nesta execução."
        st.caption(f"Motivo do snapshot: {reason}")
    st.caption("A série FRED alimenta Resumo, Mercado & Forecast e Planejamento.")
st.caption(product_scope_caption)

tab_decision, tab_summary, tab_portfolio, tab_energy, tab_market, tab_models, tab_risk, tab_planning, tab_method = (
    st.tabs(
        [
            "Decisão",
            "Resumo",
            "Portfólio",
            "Energia & Combustível",
            "Mercado & Forecast",
            "Modelos integrados",
            "Risco & Cenários",
            "Planejamento",
            "Método & Dados",
        ]
    )
)

with tab_decision:
    st.markdown("### Decisão executiva")
    vertical_metric("Status decisório", decision_intelligence["decision_status"].upper())
    vertical_metric(
        "Confiança da leitura",
        str(decision_intelligence["confidence"]["level"]).upper(),
        fmt_decimal(decision_intelligence["confidence"]["score"], 2)
        if decision_intelligence["confidence"]["score"] is not None
        else None,
    )
    st.markdown(
        f'<div class="insight"><strong>Leitura.</strong> {decision_intelligence["decision_label"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("#### Sinais quantitativos")
    signal_display = decision_intelligence["signals"].copy()
    st.dataframe(
        signal_display[["label", "status", "value", "threshold", "unit", "source"]].rename(
            columns={
                "label": "Sinal",
                "status": "Status",
                "value": "Valor",
                "threshold": "Limiar",
                "unit": "Unidade",
                "source": "Origem",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.markdown("#### Ações condicionais")
    for action in decision_intelligence["actions"]:
        st.markdown(
            f'<div class="note"><strong>{action["priority"].upper()}.</strong> {action["action"]}<br>'
            f"<span>{action['basis']}</span></div>",
            unsafe_allow_html=True,
        )
    st.markdown("#### Limitações de interpretação")
    for limitation in decision_intelligence["limitations"]:
        st.caption(f"• {limitation}")

with tab_summary:
    st.markdown("### Resumo executivo")
    compact_fact(
        "Configurações EPA",
        fmt_int(metadata["observacoes"]),
        f"{metadata['ano_inicial']}–{metadata['ano_final']}",
    )
    compact_fact("Marcas EPA", fmt_int(metadata["marcas"]))
    compact_fact("Modelos EPA", fmt_int(metadata["modelos"]))
    compact_fact("Configurações no filtro", fmt_int(kpis["configuracoes"]))
    st.markdown("#### Mercado")
    st.caption(market_source_caption)
    compact_fact("Modelo selecionado", winner)
    compact_fact("MAPE fora da amostra", f"{winner_metrics['mape_medio']:.2f}%")
    compact_fact("Mix eletrificado", fmt_pct(kpis["eletrificados_pct"]))
    st.plotly_chart(
        forecast_chart(history, forecast, winner), width="stretch", config=PLOT_CONFIG, key="summary_forecast"
    )
    st.plotly_chart(brand_bar_chart(brands), width="stretch", config=PLOT_CONFIG, key="summary_brand_bar")
    st.markdown(
        '<div class="note"><strong>Escopo.</strong> O forecast representa mercado agregado. O gráfico de marcas conta configurações EPA no filtro; não mede vendas nem participação comercial.</div>',
        unsafe_allow_html=True,
    )

with tab_portfolio:
    st.markdown("### Portfólio e posicionamento técnico")
    vertical_metric("Marcas EPA no filtro", fmt_int(kpis["marcas"]))
    vertical_metric("Modelos no filtro", fmt_int(kpis["modelos"]))
    vertical_metric("Segmentos EPA no filtro", fmt_int(filtered["VClass"].nunique()))
    vertical_metric("Eficiência média no filtro", f"{fmt_decimal(kpis['mpg_medio'])} MPG/MPGe")
    st.plotly_chart(brand_position_chart(brands), width="stretch", config=PLOT_CONFIG, key="portfolio_position")
    st.plotly_chart(segment_chart(segments), width="stretch", config=PLOT_CONFIG, key="portfolio_segments")
    st.markdown("#### Scorecard de marcas")
    brand_display = brands.nlargest(20, "configuracoes").rename(
        columns={
            "make": "Marca EPA",
            "configuracoes": "Configurações",
            "modelos": "Modelos",
            "segmentos": "Segmentos",
            "ano_inicial": "Primeiro ano",
            "ano_final": "Último ano",
            "mpg_medio": "MPG/MPGe",
            "co2_medio_g_milha": "CO₂ (g/mi)",
            "participacao_eletrificada_pct": "Mix eletrificado (%)",
        }
    )[
        [
            "Marca EPA",
            "Configurações",
            "Modelos",
            "Segmentos",
            "Último ano",
            "MPG/MPGe",
            "CO₂ (g/mi)",
            "Mix eletrificado (%)",
        ]
    ]
    st.dataframe(
        brand_display.style.format(
            {
                "Configurações": "{:,.0f}",
                "Modelos": "{:,.0f}",
                "Segmentos": "{:,.0f}",
                "Último ano": "{:.0f}",
                "MPG/MPGe": "{:.1f}",
                "CO₂ (g/mi)": "{:.0f}",
                "Mix eletrificado (%)": "{:.1f}%",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.markdown("#### Monitoramento de risco NHTSA")
    if nhtsa_risk_snapshot.empty:
        st.caption("A watchlist NHTSA ainda não possui eventos persistidos.")
    else:
        nhtsa_display = nhtsa_risk_snapshot.rename(
            columns={
                "marca": "Marca",
                "modelo": "Modelo",
                "ano_modelo": "Ano-modelo",
                "recalls": "Recalls",
                "reclamacoes": "Reclamações",
                "indice_risco": "Índice de risco",
                "ultimo_evento": "Último evento",
            }
        )
        nhtsa_display = format_temporal_display(nhtsa_display, daily_columns=["Último evento"])
        st.dataframe(
            nhtsa_display.style.format(
                {
                    "Ano-modelo": "{:.0f}",
                    "Recalls": "{:.0f}",
                    "Reclamações": "{:.0f}",
                    "Índice de risco": "{:.0f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "Watchlist pública por marca, modelo e ano-modelo. O índice soma 2 × recalls e 1 × reclamações; ele prioriza monitoramento e não mede taxa de defeito, qualidade, vendas ou risco financeiro."
        )

    with st.expander("Registro temporal completo de marcas EPA"):
        registry_display = registry.rename(
            columns={
                "make": "Marca EPA",
                "configuracoes": "Configurações",
                "modelos": "Modelos",
                "ano_inicial": "Primeiro ano",
                "ano_final": "Último ano",
                "presenca_no_snapshot": "Presença temporal",
            }
        )
        st.dataframe(
            registry_display.style.format(
                {"Configurações": "{:,.0f}", "Modelos": "{:,.0f}", "Primeiro ano": "{:.0f}", "Último ano": "{:.0f}"}
            ),
            width="stretch",
            hide_index=True,
            height=440,
        )
        st.caption(
            "Os nomes são valores literais do campo `make` da EPA. O status temporal não indica atividade comercial, propriedade ou participação de mercado."
        )

with tab_energy:
    st.markdown("### Energia, combustível e custo de uso")
    latest_map = {row["energia"]: row for _, row in price_latest.iterrows()}
    gasoline = latest_map["Gasolina regular"]
    diesel = latest_map["Diesel"]
    electricity = latest_map["Eletricidade"]
    vertical_metric("Gasolina regular", fmt_usd(gasoline["preco"], 3) + "/gal", fmt_month_display(gasoline["data"]))
    vertical_metric("Diesel", fmt_usd(diesel["preco"], 3) + "/gal", fmt_month_display(diesel["data"]))
    vertical_metric("Eletricidade", fmt_usd(electricity["preco"], 3) + "/kWh", fmt_month_display(electricity["data"]))
    vertical_metric(
        "Configurações comparáveis para custo por 100 milhas",
        fmt_int(int(filtered["custo_energia_100mi_usd"].notna().sum())),
        "Gasolina, diesel e elétricos a bateria",
    )
    st.markdown(
        '<div class="note"><strong>Unidades e escopo.</strong> Gasolina e diesel usam séries nacionais em US$/galão. Elétricos a bateria usam preço médio urbano nacional em US$/kWh e o consumo `combE` da EPA. Híbridos plug-in e combustíveis sem série harmonizada permanecem fora do cálculo por 100 milhas para não introduzir premissas artificiais.</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(price_index_chart(price_index), width="stretch", config=PLOT_CONFIG, key="energy_price_index")
    st.plotly_chart(energy_cost_chart(energy_by_source), width="stretch", config=PLOT_CONFIG, key="energy_cost_100mi")
    st.markdown("#### Sensibilidade a choque de preço de energia")
    sensitivity_energy_display = energy_sensitivity.rename(
        columns={
            "choque_preco_pct": "Choque de preço (%)",
            "fonte_energia": "Fonte",
            "custo_mediano_100mi_usd": "Custo mediano por 100 mi (US$)",
        }
    )
    st.dataframe(
        sensitivity_energy_display.style.format(
            {"Choque de preço (%)": "{:.0f}%", "Custo mediano por 100 mi (US$)": "US$ {:.2f}"}
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Os choques de −20%, 0% e +20% são hipóteses explícitas aplicadas às últimas observações nacionais de preço; não são previsões de preço de combustível."
    )
    st.markdown("#### Estrutura por fonte de energia")
    energy_display = energy_by_source.rename(
        columns={
            "fonte_energia": "Fonte",
            "configuracoes": "Configurações",
            "marcas": "Marcas",
            "modelos": "Modelos",
            "eficiencia_mediana": "Eficiência mediana (MPG/MPGe)",
            "co2_mediano_g_milha": "CO₂ mediano (g/mi)",
            "custo_epa_anual_mediano_usd": "Custo EPA anual mediano (US$)",
            "custo_energia_100mi_mediano_usd": "Energia por 100 mi (US$)",
        }
    )
    st.dataframe(
        energy_display.style.format(
            {
                "Configurações": "{:,.0f}",
                "Marcas": "{:,.0f}",
                "Modelos": "{:,.0f}",
                "Eficiência mediana (MPG/MPGe)": "{:.1f}",
                "CO₂ mediano (g/mi)": "{:.0f}",
                "Custo EPA anual mediano (US$)": "US$ {:,.0f}",
                "Energia por 100 mi (US$)": "US$ {:.2f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.plotly_chart(correlation_chart(correlations), width="stretch", config=PLOT_CONFIG, key="energy_correlation")
    st.markdown("#### Associações mais fortes")
    pair_display = strong_pairs.rename(
        columns={
            "indicador_a": "Indicador A",
            "indicador_b": "Indicador B",
            "rho_spearman": "ρ Spearman",
            "n": "Observações válidas",
        }
    )
    st.dataframe(
        pair_display.style.format({"ρ Spearman": "{:.2f}", "Observações válidas": "{:,.0f}"}),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "ρ de Spearman mede associação monotônica no recorte filtrado. Não implica causalidade; os pares usam somente observações com ambos os campos disponíveis."
    )
    st.markdown("#### Comparação controlada de configurações")
    comparison_source = filtered.dropna(subset=["comb08"]).copy()
    comparison_source["opcao"] = (
        comparison_source["make"]
        + " · "
        + comparison_source["model"]
        + " · "
        + comparison_source["year"].astype(int).astype(str)
        + " · "
        + comparison_source["fonte_energia"]
    )
    selected_options = st.multiselect(
        "Selecione até quatro configurações",
        options=comparison_source["opcao"].drop_duplicates().sort_values().tolist(),
        max_selections=4,
        placeholder="Escolha configurações para comparar",
    )
    if selected_options:
        selected_rows = (
            comparison_source[comparison_source["opcao"].isin(selected_options)]
            .sort_values(["opcao", "id"])
            .drop_duplicates("opcao")
        )
        comparison = selected_rows.rename(
            columns={
                "make": "Marca",
                "model": "Modelo",
                "year": "Ano",
                "fonte_energia": "Energia",
                "comb08": "MPG/MPGe",
                "combE": "Consumo elétrico combinado",
                "custo_energia_100mi_usd": "Energia por 100 mi (US$)",
                "co2_valido": "CO₂ (g/mi)",
                "custo_anual_valido": "Custo EPA anual (US$)",
            }
        )[
            [
                "Marca",
                "Modelo",
                "Ano",
                "Energia",
                "MPG/MPGe",
                "Consumo elétrico combinado",
                "Energia por 100 mi (US$)",
                "CO₂ (g/mi)",
                "Custo EPA anual (US$)",
            ]
        ]
        st.dataframe(
            comparison.style.format(
                {
                    "Ano": "{:.0f}",
                    "MPG/MPGe": "{:.1f}",
                    "Consumo elétrico combinado": "{:.1f}",
                    "Energia por 100 mi (US$)": "US$ {:.2f}",
                    "CO₂ (g/mi)": "{:.0f}",
                    "Custo EPA anual (US$)": "US$ {:,.0f}",
                }
            ),
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption(
            "A comparação foi limitada a quatro configurações para manter leitura direta, como em ferramentas públicas de comparação de veículos."
        )

with tab_market:
    st.markdown("### Mercado agregado, validação temporal e incerteza")
    st.caption(f"{market_source_caption} O eixo histórico destaca explicitamente o último mês disponível.")
    vertical_metric("Modelo selecionado", winner)
    vertical_metric("MAPE médio", f"{winner_metrics['mape_medio']:.2f}%")
    vertical_metric("MAE médio", f"{winner_metrics['mae_medio']:.3f} milhões SAAR")
    vertical_metric("Horizonte", f"{horizon} meses")
    st.plotly_chart(history_chart(history), width="stretch", config=PLOT_CONFIG, key="market_history")
    st.plotly_chart(backtest_chart(summary, winner), width="stretch", config=PLOT_CONFIG, key="market_backtest")
    st.dataframe(
        summary_display.style.format(
            {
                "mape_medio": "{:.2f}%",
                "mape_desvio": "{:.2f} p.p.",
                "smape_medio": "{:.2f}%",
                "wape_medio": "{:.2f}%",
                "mae_medio": "{:.3f}",
                "rmse_medio": "{:.3f}",
                "mase_medio": "{:.3f}",
                "tempo_medio_s": "{:.3f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    prequential_quality = backtest["prequential_interval_quality"]
    calibration_detail = (
        f"{prequential_quality['observacoes_avaliadas']} observações em "
        f"{prequential_quality['dobras_avaliadas']} dobras; bootstrap {market['parameters']['bootstrap_method']}"
    )
    vertical_metric(
        "Cobertura prequential p10–p90",
        fmt_pct(prequential_quality["coverage_p10_p90"] * 100),
        calibration_detail,
    )
    vertical_metric(
        "Pinball loss prequential",
        f"{prequential_quality['pinball_loss_medio']:.3f}",
        "Cada dobra é avaliada apenas com resíduos de dobras anteriores.",
    )
    with st.expander("Diagnóstico residual e decomposição"):
        st.plotly_chart(
            residual_chart(backtest["residuals"]), width="stretch", config=PLOT_CONFIG, key="market_residuals"
        )
        st.plotly_chart(acf_chart(backtest["residual_acf"]), width="stretch", config=PLOT_CONFIG, key="market_acf")
        st.dataframe(
            backtest["ljung_box"]
            .rename(columns={"lb_stat": "Estatística Ljung-Box", "lb_pvalue": "p-valor"})
            .style.format({"Estatística Ljung-Box": "{:.3f}", "p-valor": "{:.4f}"}),
            width="stretch",
            hide_index=True,
        )
        residual_info = backtest["residual_diagnostics"]
        diagnostics_display = pd.DataFrame(
            [
                {
                    "Diagnóstico": "Durbin-Watson",
                    "Valor": residual_info["durbin_watson"],
                    "Leitura": "Autocorrelação residual; próximo de 2 é referência descritiva.",
                },
                {
                    "Diagnóstico": "Jarque-Bera p-valor",
                    "Valor": residual_info["jarque_bera"].get("pvalue"),
                    "Leitura": "Normalidade residual; não determina sozinho a qualidade do forecast.",
                },
                {
                    "Diagnóstico": "ARCH p-valor",
                    "Valor": residual_info["arch"].get("pvalue"),
                    "Leitura": "Heterocedasticidade residual; interpretação exploratória com poucas dobras.",
                },
            ]
        )
        st.dataframe(diagnostics_display.style.format({"Valor": "{:.4f}"}), width="stretch", hide_index=True)

    # Gráfico de coeficientes padronizados do OLS, usado somente para diagnóstico.
    with st.expander("Drivers diagnósticos — OLS Newey-West"):
        st.caption(
            "Este OLS estima a contribuição relativa dos drivers e seus resíduos. "
            "Ele não alimenta o forecast principal nem o planejamento operacional; "
            "o forecast usado no app permanece a Regressão com defasagens do Forecast Engine."
        )
        try:
            import sys as _sys  # noqa: PLC0415

            _sys.path.insert(0, str(ROOT / "src"))
            from forecast_model import build_regression_matrix, walk_forward_ols  # noqa: PLC0415

            @st.cache_data(show_spinner=False)
            def _load_ols_coefficients(snapshot_mtime: float, feature_store_mtime: float) -> dict:
                """Treina o OLS diagnóstico e invalida o cache quando dados de mercado mudam."""
                matrix = build_regression_matrix()
                results = walk_forward_ols(matrix)
                return {
                    "coeficientes": results["coeficientes_padronizados"],
                    "regressores": results.get("regressores", []),
                    "drivers_ausentes": results.get("drivers_configurados_mas_ausentes", []),
                    "mape": results["mape_medio"],
                    "dw_medio": results["durbin_watson_medio"],
                    "dw_ultima_dobra": results["durbin_watson_ultima_dobra"],
                    "coverage": results["coverage_p10_p90"],
                    "fold_diagnostics": results["fold_metrics"],
                }

            _snapshot_mtime = MARKET_SNAPSHOT.stat().st_mtime if MARKET_SNAPSHOT.exists() else 0.0
            _feature_store_manifest = DATA_DIR / "feature_store" / "manifest.json"
            _feature_store_mtime = _feature_store_manifest.stat().st_mtime if _feature_store_manifest.exists() else 0.0
            ols_diagnostic = _load_ols_coefficients(_snapshot_mtime, _feature_store_mtime)
            coef_df = ols_diagnostic["coeficientes"]
            st.markdown("#### Status do artefato diagnóstico")
            vertical_metric("Papel no aplicativo", "Diagnóstico de drivers")
            vertical_metric("Uso operacional", "Não alimenta forecast nem planejamento")
            vertical_metric("Regressores efetivos", ", ".join(ols_diagnostic["regressores"]))
            vertical_metric(
                "Drivers configurados, mas ausentes",
                ", ".join(ols_diagnostic["drivers_ausentes"]) or "Nenhum",
            )
            st.caption(
                "Não há candidatos avaliados e descartados persistidos; drivers ausentes foram omitidos por indisponibilidade no feature store."
            )
            vertical_metric("MAPE walk-forward", f"{ols_diagnostic['mape']:.2f}%")
            vertical_metric("Durbin–Watson médio", f"{ols_diagnostic['dw_medio']:.3f}")
            vertical_metric("Durbin–Watson última dobra", f"{ols_diagnostic['dw_ultima_dobra']:.3f}")
            vertical_metric("Cobertura P10–P90", f"{ols_diagnostic['coverage']:.2%}")
            st.markdown("#### Resíduos: treino versus OOS")
            vertical_metric(
                "Ljung–Box treino, lag 12",
                "; ".join(
                    f"D{fold['fold']}: p={fold['ljung_box_pvalue_train_lag12']:.2g}"
                    for fold in ols_diagnostic["fold_diagnostics"]
                ),
            )
            vertical_metric(
                "ARCH treino, lag 12",
                "; ".join(
                    f"D{fold['fold']}: p={fold['arch_pvalue_train_lag12']:.2g}"
                    for fold in ols_diagnostic["fold_diagnostics"]
                ),
            )
            vertical_metric(
                "DW OOS centrado",
                "; ".join(f"D{fold['fold']}: {fold['dw_centered']:.3f}" for fold in ols_diagnostic["fold_diagnostics"]),
            )
            st.caption(
                "Ljung–Box e ARCH usam os resíduos do treino; DW e ACF/PACF OOS usam somente os seis meses de cada dobra."
            )
            st.warning(
                "Artefato não aprovado para uso operacional: os critérios de DW médio e MAPE não foram atingidos. "
                "A seção abaixo é interpretativa e não substitui o forecast principal."
            )
            if not coef_df.empty:
                fig_coef = go.Figure()
                colors = [ORANGE if v >= 0 else RED for v in coef_df["coef_norm"]]
                fig_coef.add_trace(
                    go.Bar(
                        x=coef_df["coef_norm"],
                        y=coef_df["variavel"],
                        orientation="h",
                        marker_color=colors,
                        customdata=coef_df[["coeficiente", "pvalue"]].values,
                        hovertemplate="%{y}<br>Coef. norm.: %{x:.3f}<br>Coef. bruto: %{customdata[0]:.4f}<br>p-valor: %{customdata[1]:.4f}<extra></extra>",
                    )
                )
                fig_coef.update_layout(
                    title="Coeficientes padronizados — OLS Newey-West",
                    xaxis_title="Magnitude relativa (normalizada pelo maior coeficiente)",
                    yaxis_title="",
                    height=max(280, 40 * len(coef_df) + 80),
                )
                fig_coef = style_chart(fig_coef, height=max(280, 40 * len(coef_df) + 80), legend=False)
                st.plotly_chart(fig_coef, width="stretch", config=PLOT_CONFIG, key="ols_coef_chart")
                # Tabela de coeficientes com p-valores.
                coef_display = coef_df[["variavel", "coeficiente", "ic_lo95", "ic_hi95", "pvalue"]].copy()
                coef_display.columns = ["Variável", "Coeficiente", "IC 95% inferior", "IC 95% superior", "p-valor"]
                st.dataframe(
                    coef_display.style.format(
                        {
                            "Coeficiente": "{:.4f}",
                            "IC 95% inferior": "{:.4f}",
                            "IC 95% superior": "{:.4f}",
                            "p-valor": "{:.4f}",
                        }
                    ),
                    width="stretch",
                    hide_index=True,
                )
        except Exception as _ols_err:
            st.caption(f"Modelo OLS Newey-West indisponível: {_ols_err}")

with tab_models:
    st.markdown("### Modelos integrados: energia, mercado e eficiência")
    econ = model_summary_data["econometria_energia"]
    neural = model_summary_data["rede_neural_eficiencia"]
    st.markdown("#### Econometria temporal com preços de energia")
    vertical_metric(
        "Observações na validação OLS", fmt_int(econ["observacoes"]), f"{econ['inicio_teste']}–{econ['fim_teste']}"
    )
    vertical_metric("MAE OLS fora da amostra", f"{econ['mae']:.3f} milhões SAAR")
    vertical_metric("R² OLS fora da amostra", f"{econ['r2']:.2f}")
    st.markdown(
        '<div class="note"><strong>Resultado honesto.</strong> O modelo OLS conecta demanda, defasagens e preços de energia observados, mas o R² fora da amostra é negativo neste período. Ele é mantido como análise econométrica explicativa, não como substituto do forecast operacional. Isso evita transformar uma regressão estatisticamente fraca em recomendação.</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        econometric_validation_chart(econometric_validation),
        width="stretch",
        config=PLOT_CONFIG,
        key="models_econometric_validation",
    )
    st.markdown("#### Coeficientes padronizados e significância")
    coefficient_display = econometric_coefficients.rename(
        columns={"variavel": "Variável", "coeficiente_padronizado": "Coeficiente padronizado", "p_valor": "p-valor"}
    )
    st.dataframe(
        coefficient_display.style.format({"Coeficiente padronizado": "{:.3f}", "p-valor": "{:.4f}"}),
        width="stretch",
        hide_index=True,
    )
    st.markdown("#### Diagnóstico de multicolinearidade")
    vif_display = econometric_vif.rename(columns={"variavel": "Variável", "vif": "VIF"})
    st.dataframe(vif_display.style.format({"VIF": "{:.2f}"}), width="stretch", hide_index=True)
    st.caption(
        "VIF alto sinaliza que coeficientes individuais podem ser instáveis. Por isso, a OLS é exibida como análise explicativa e não como mecanismo de previsão operacional."
    )
    st.markdown("#### Rede neural para eficiência EPA")
    vertical_metric(
        "Treinamento da rede neural",
        f"{fmt_int(model_summary_data['amostras']['neural_treino'])} configurações",
        f"{neural['inicio_treino']}–{neural['fim_treino']}",
    )
    vertical_metric(
        "Validação temporal",
        f"{fmt_int(neural['observacoes'])} configurações",
        f"{neural['inicio_teste']}–{neural['fim_teste']}",
    )
    vertical_metric("MAE da rede neural", f"{neural['mae']:.2f} MPG/MPGe")
    vertical_metric("R² da rede neural", f"{neural['r2']:.3f}")
    st.markdown(
        '<div class="note"><strong>Alvo e proteção contra vazamento.</strong> A rede prevê `comb08` usando ano-modelo, cilindros, cilindrada, segmento, combustível, tecnologia alternativa, transmissão, tração, turbo, supercharger e start-stop. Não usa MPG urbano/rodoviário, CO₂ ou custo anual como entrada.</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        neural_validation_chart(neural_validation),
        width="stretch",
        config=PLOT_CONFIG,
        key="models_neural_validation",
    )
    st.markdown("#### Importância por permutação")
    importance_display = neural_importance.rename(
        columns={
            "variavel": "Variável",
            "incremento_mae_permutacao": "Incremento de MAE",
            "desvio_mae_permutacao": "Desvio",
        }
    )
    st.dataframe(
        importance_display.style.format({"Incremento de MAE": "{:.3f}", "Desvio": "{:.3f}"}),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "A importância por permutação mede o aumento do erro quando uma variável é embaralhada no conjunto temporal de teste; não implica causalidade."
    )
    st.markdown("#### Erro por tecnologia de propulsão")
    error_powertrain_display = neural_error_by_powertrain.rename(
        columns={
            "powertrain": "Propulsão",
            "configuracoes": "Configurações",
            "mae": "MAE",
            "mediana_erro": "Mediana do erro",
        }
    )
    st.dataframe(
        error_powertrain_display.style.format(
            {"Configurações": "{:,.0f}", "MAE": "{:.2f}", "Mediana do erro": "{:.2f}"}
        ),
        width="stretch",
        hide_index=True,
    )
    st.markdown("#### Maiores erros de validação da rede neural")
    neural_display = neural_validation.nlargest(25, "erro_abs").rename(
        columns={
            "id": "ID EPA",
            "make": "Marca",
            "model": "Modelo",
            "year": "Ano",
            "comb08": "MPG/MPGe observado",
            "previsto_mlp": "MPG/MPGe previsto",
            "erro_abs": "Erro absoluto",
        }
    )
    st.dataframe(
        neural_display.style.format(
            {"Ano": "{:.0f}", "MPG/MPGe observado": "{:.1f}", "MPG/MPGe previsto": "{:.1f}", "Erro absoluto": "{:.1f}"}
        ),
        width="stretch",
        hide_index=True,
    )

with tab_risk:
    st.markdown("### Risco & Cenários")
    risk_metrics = risk["metrics"]
    vertical_metric("Probabilidade de stockout", fmt_pct(float(risk_metrics["stockout_probability"]) * 100))
    vertical_metric("Backlog esperado", fmt_int(risk_metrics["expected_backlog_units"]))
    vertical_metric("Capacity-at-risk P95", fmt_int(risk_metrics["capacity_at_risk_units"]))
    vertical_metric("VaR 95%", fmt_usd(risk_metrics["VaR_95"]))
    vertical_metric("CVaR 95%", fmt_usd(risk_metrics["CVaR_95"]))
    st.caption(
        "Risco calculado sobre caminhos de forecast; market share é hipótese assumida. "
        "VaR/CVaR representam custo de backlog sob a política de capacidade declarada."
    )
    st.dataframe(risk["risk_table"], width="stretch", hide_index=True)
    if robust_planning is None:
        st.info(
            "A otimização robusta está desativada. Ative-a no expander Forecast & Planejamento para resolver caminhos com PuLP."
        )
    else:
        st.markdown("#### Resultado da otimização robusta")
        vertical_metric("Caminhos resolvidos", fmt_int(robust_planning["metrics"]["n_paths_optimized"]))
        vertical_metric(
            "Probabilidade de backlog final",
            fmt_pct(float(robust_planning["metrics"]["probability_backlog_final"]) * 100),
        )
        vertical_metric("Utilização P95", fmt_pct(float(robust_planning["metrics"]["capacity_at_risk_pct"])))
        st.dataframe(robust_planning["summary"], width="stretch", hide_index=True)

with tab_planning:
    st.markdown("### Capacidade, estoque e nível de serviço")
    st.caption(
        f"Demanda e plano derivados da série FRED em uso: {market_refresh['source_label']} · "
        f"{fmt_int(market_refresh['observations'])} observações · "
        f"cobertura {market_refresh['data_start']}–{market_refresh['data_end']}."
    )
    vertical_metric("Demanda Base", fmt_int(base_scenario["Demanda total (veículos)"]))
    vertical_metric("Produção regular Base", fmt_int(base_scenario["Produção regular (veículos)"]))
    vertical_metric("Produção extra Base", fmt_int(base_scenario["Produção extra (veículos)"]))
    vertical_metric("Backlog final Base", fmt_int(base_scenario["Demanda pendente final"]))
    st.markdown(
        f'<div class="insight"><strong>Ação sugerida.</strong> {planning_decision["acao_recomendada"]}<br><strong>Risco.</strong> {planning_decision["risco_principal"]}</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        production_chart(plan, int(capacity)), width="stretch", config=PLOT_CONFIG, key="planning_production"
    )
    st.plotly_chart(
        sensitivity_chart(production["sensitivity"]),
        width="stretch",
        config=PLOT_CONFIG,
        key="planning_sensitivity",
    )
    st.markdown("#### Cenários de operação")
    scenario_display = scenarios[
        [
            "Cenário",
            "Choque de demanda (%)",
            "Demanda total (veículos)",
            "Produção regular (veículos)",
            "Produção extra (veículos)",
            "Produção total (veículos)",
            "Utilização média (%)",
            "Demanda pendente final",
            "Desvio acumulado de segurança",
            "Custo total (US$)",
        ]
    ]
    st.dataframe(
        scenario_display.style.format(
            {
                "Choque de demanda (%)": "{:.0f}%",
                "Demanda total (veículos)": "{:,.0f}",
                "Produção regular (veículos)": "{:,.0f}",
                "Produção extra (veículos)": "{:,.0f}",
                "Produção total (veículos)": "{:,.0f}",
                "Utilização média (%)": "{:.1f}%",
                "Demanda pendente final": "{:,.0f}",
                "Desvio acumulado de segurança": "{:,.0f}",
                "Custo total (US$)": "US$ {:,.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    with st.expander("Hipóteses operacionais e plano mensal"):
        assumptions_display = pd.DataFrame(
            [{"Hipótese": key, "Valor": value} for key, value in production["assumptions"].__dict__.items()]
        )
        st.dataframe(assumptions_display, width="stretch", hide_index=True)
        plan_display = plan.rename(
            columns={
                "data": "Data",
                "demanda_planejada_veiculos": "Demanda",
                "producao_regular": "Produção regular",
                "producao_extra": "Produção extra",
                "producao_recomendada": "Produção total",
                "estoque_final": "Estoque final",
                "demanda_pendente": "Pendente",
                "desvio_seguranca": "Desvio de segurança",
                "utilizacao_capacidade_pct": "Utilização regular (%)",
            }
        )[
            [
                "Data",
                "Demanda",
                "Produção regular",
                "Produção extra",
                "Produção total",
                "Estoque final",
                "Pendente",
                "Desvio de segurança",
                "Utilização regular (%)",
            ]
        ]
        plan_display = format_temporal_display(plan_display, monthly_columns=["Data"])
        st.dataframe(
            plan_display.style.format(
                {
                    "Demanda": "{:,.0f}",
                    "Produção regular": "{:,.0f}",
                    "Produção extra": "{:,.0f}",
                    "Produção total": "{:,.0f}",
                    "Estoque final": "{:,.0f}",
                    "Pendente": "{:,.0f}",
                    "Desvio de segurança": "{:,.0f}",
                    "Utilização regular (%)": "{:.1f}%",
                }
            ),
            width="stretch",
            hide_index=True,
        )
        st.download_button(
            "Exportar plano em CSV",
            plan_display.to_csv(index=False).encode("utf-8"),
            "plano_operacional.csv",
            "text/csv",
        )

with tab_method:
    st.markdown("### Fontes, cobertura e limites")
    source_table = pd.DataFrame(
        {
            "Fonte": [
                "FRED — TOTALSA",
                "EPA / FuelEconomy.gov",
                "EIA / FRED — energia",
                "NHTSA — recalls e reclamações",
            ],
            "Cobertura": [
                "Mercado agregado mensal de veículos leves nos EUA.",
                f"{fmt_int(metadata['observacoes'])} configurações, {metadata['ano_inicial']}–{metadata['ano_final']}, por marca, modelo, classe, combustível, eficiência e emissões.",
                "Gasolina e diesel nacionais semanais, consolidados mensalmente; eletricidade média urbana mensal.",
                "Watchlist pública de seis combinações de marca, modelo e ano-modelo; eventos datados desde 2023.",
            ],
            "Uso": [
                "Previsão e cenário de demanda.",
                "Portfólio, tecnologia, eficiência, emissões e rede neural.",
                "Preço energético, econometria e custo de referência por 100 milhas.",
                "Monitoramento de eventos de segurança; não mede vendas, qualidade relativa ou risco financeiro.",
            ],
        }
    )
    st.dataframe(source_table, width="stretch", hide_index=True)
    st.markdown("### Saúde e proveniência dos snapshots")
    health_display = data_health.rename(
        columns={
            "dataset": "Dataset",
            "source_status": "Status",
            "rows": "Linhas",
            "columns": "Colunas",
            "period_start": "Início",
            "period_end": "Fim",
            "last_observation": "Última observação",
            "missing_rate_pct": "Ausência (%)",
            "duplicate_rows": "Duplicatas",
            "invalid_rows": "Inválidas",
            "outlier_rows": "Outliers IQR",
            "frequency_gaps": "Lacunas mensais",
            "snapshot_modified_utc": "Snapshot modificado (UTC)",
            "snapshot_sha256": "SHA-256",
            "notes": "Notas",
        }
    )
    health_display = format_temporal_display(
        health_display,
        daily_columns=["Início", "Fim", "Última observação"],
        utc_columns=["Snapshot modificado (UTC)"],
    )
    health_columns = [
        "Dataset",
        "Status",
        "Linhas",
        "Início",
        "Fim",
        "Ausência (%)",
        "Duplicatas",
        "Inválidas",
        "Lacunas mensais",
    ]
    st.dataframe(
        health_display[health_columns].style.format(
            {
                "Linhas": "{:,.0f}",
                "Ausência (%)": "{:.2f}%",
                "Duplicatas": "{:,.0f}",
                "Inválidas": "{:,.0f}",
                "Lacunas mensais": "{:.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Outliers IQR são sinalizados, não removidos automaticamente. Ausências em energia refletem diferença de cobertura histórica entre séries e permanecem sem imputação."
    )
    with st.expander("Detalhes de proveniência e qualidade"):
        provenance_columns = [
            "Dataset",
            "Colunas",
            "Última observação",
            "Outliers IQR",
            "Snapshot modificado (UTC)",
            "SHA-256",
            "Notas",
        ]
        st.dataframe(
            health_display[provenance_columns].style.format({"Colunas": "{:,.0f}", "Outliers IQR": "{:,.0f}"}),
            width="stretch",
            hide_index=True,
        )
    st.markdown("### Fórmulas e interpretação")
    st.latex(r"Custo_{100mi}^{gas/diesel} = \frac{Preço\; (US\$/gal)}{MPG} \times 100")
    st.latex(r"Custo_{100mi}^{BEV} = combE\; (kWh/100mi) \times Preço\; (US\$/kWh)")
    st.markdown(
        "A correlação usa Spearman para resumir associações monotônicas entre atributos comparáveis no recorte filtrado. A regressão OLS usa o período comum entre mercado e energia; a rede neural separa anos-modelo de treino e teste. Nenhum desses procedimentos infere causalidade, venda por marca ou desempenho individual de combustível."
    )
    st.markdown("### Documentação disponível")
    st.markdown(
        "[Diagnóstico técnico](docs/DIAGNOSTICO_TECNICO_INICIAL.md) · [Arquitetura-alvo](docs/ARQUITETURA_ALVO.md) · [Auditoria da integração total](docs/AUDITORIA_INTEGRACAO_TOTAL.md) · [Auditoria do catálogo EPA](docs/AUDITORIA_CATALOGO_EPA.md) · [Pesquisa de referências e dados](docs/PESQUISA_REFERENCIAS_E_DADOS.md) · [Proveniência das fontes](data/SOURCES.md)"
    )
    st.markdown("### Referências")
    st.markdown(
        f"[1] [FRED — Total Vehicle Sales]({FRED_SERIES_URL})  \n[2] [EPA — Download Fuel Economy Data]({EPA_DOWNLOAD_PAGE})  \n[3] [EIA — Gasoline and Diesel Fuel Update](https://www.eia.gov/petroleum/gasdiesel/)  \n[4] [FRED / BLS — Electricity per Kilowatt-Hour](https://fred.stlouisfed.org/series/APU000072610)  \n[5] [AFDC — Alternative Fuel Price Report](https://afdc.energy.gov/fuels/prices.html)"
    )

st.markdown(
    '<div class="footer">QUANT AUTOMOTIVE INTELLIGENCE · Mercado, produto, energia e modelagem com fontes públicas rastreáveis</div>',
    unsafe_allow_html=True,
)
