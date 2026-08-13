from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import analysis as analysis_module  # noqa: E402
import vehicle_intelligence as vehicle_module  # noqa: E402

analysis_module = importlib.reload(analysis_module)
vehicle_module = importlib.reload(vehicle_module)

FRED_SERIES_URL = analysis_module.FRED_SERIES_URL
run_full_analysis = analysis_module.run_full_analysis
EPA_DOWNLOAD_PAGE = vehicle_module.EPA_DOWNLOAD_PAGE
EPA_DATA_URL = vehicle_module.EPA_DATA_URL
load_vehicle_data = vehicle_module.load_vehicle_data
filter_vehicles = vehicle_module.filter_vehicles
portfolio_kpis = vehicle_module.portfolio_kpis
brand_summary = vehicle_module.brand_summary
brand_registry = vehicle_module.brand_registry
model_summary = vehicle_module.model_summary
segment_summary = vehicle_module.segment_summary
powertrain_summary = vehicle_module.powertrain_summary
annual_portfolio_trend = vehicle_module.annual_portfolio_trend
vehicle_universe_metadata = vehicle_module.vehicle_universe_metadata

st.set_page_config(
    page_title="Quant Automotive Intelligence",
    page_icon="Q",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRIMARY = "#14213D"
BLUE = "#1F4E79"
ORANGE = "#E87532"
TEAL = "#00A6A6"
GREEN = "#4E9F3D"
RED = "#C43D3D"
PURPLE = "#6A5ACD"
MUTED = "#667085"
GRID = "#E7ECF3"
POWERTRAIN_COLORS = {
    "Combustão": "#607D9B",
    "Diesel": "#495867",
    "Flex / Etanol": "#D68C45",
    "Gás natural": "#8AB17D",
    "Híbrido": "#4E9F3D",
    "Híbrido plug-in": "#00A6A6",
    "Elétrico a bateria": "#6A5ACD",
    "Célula a combustível": "#2F75B5",
}

st.markdown(
    f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
        :root {{ --quant-navy: {PRIMARY}; --quant-blue: {BLUE}; --quant-orange: {ORANGE}; }}
        html, body, [class*="css"] {{ font-family: 'DM Sans', sans-serif; }}
        h1, h2, h3 {{ font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.025em; color: var(--quant-navy); }}
        .stApp {{ background: #F7F9FC; }}
        [data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid #E4E9F0; }}
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: var(--quant-navy); }}
        .block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1520px; }}
        .hero {{ background: linear-gradient(110deg, #14213D 0%, #1F4E79 68%, #2F75B5 100%); border-radius: 18px; padding: 34px 40px 31px; color: white; margin-bottom: 23px; box-shadow: 0 12px 28px rgba(20,33,61,.14); }}
        .hero .eyebrow {{ text-transform: uppercase; letter-spacing: .16em; font-size: .72rem; font-weight: 700; opacity: .78; margin-bottom: 9px; }}
        .hero h1 {{ color: white; font-size: 2.05rem; margin: 0; line-height: 1.13; }}
        .hero p {{ color: rgba(255,255,255,.84); font-size: 1rem; margin: 12px 0 0; max-width: 950px; line-height: 1.55; }}
        .quant-tag {{ display: inline-block; background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.18); border-radius: 999px; padding: 5px 10px; margin-top: 17px; font-size: .74rem; letter-spacing: .03em; }}
        .section-kicker {{ color: var(--quant-orange); text-transform: uppercase; letter-spacing: .13em; font-size: .72rem; font-weight: 700; margin: 20px 0 5px; }}
        .section-title {{ font-family: 'Space Grotesk', sans-serif; color: var(--quant-navy); font-size: 1.42rem; font-weight: 700; margin-bottom: 8px; }}
        .insight {{ background: #FFFFFF; border: 1px solid #E4E9F0; border-left: 4px solid var(--quant-orange); border-radius: 10px; padding: 17px 19px; margin: 10px 0 18px; color: #344054; line-height: 1.55; }}
        .method-card {{ background: #FFFFFF; border: 1px solid #E4E9F0; border-radius: 13px; padding: 17px 19px; min-height: 135px; box-shadow: 0 5px 14px rgba(20,33,61,.035); }}
        .method-card .step {{ color: var(--quant-orange); font-size: .7rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }}
        .method-card strong {{ display: block; color: var(--quant-navy); font-family: 'Space Grotesk', sans-serif; font-size: 1.02rem; margin: 6px 0; }}
        .method-card span {{ color: #667085; font-size: .88rem; line-height: 1.4; }}
        .source-note {{ font-size: .79rem; color: #667085; margin-top: 4px; line-height: 1.45; }}
        .small-note {{ color: #667085; font-size: .84rem; line-height: 1.5; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 8px; border-bottom: 1px solid #DCE2EA; }}
        .stTabs [data-baseweb="tab"] {{ height: 47px; padding: 0 15px; font-weight: 600; color: #667085; }}
        .stTabs [aria-selected="true"] {{ color: var(--quant-navy); border-bottom-color: var(--quant-orange); }}
        div[data-testid="stMetric"] {{ background: #FFFFFF; border: 1px solid #E4E9F0; border-radius: 12px; padding: 15px 16px; box-shadow: 0 4px 12px rgba(20,33,61,.03); }}
        div[data-testid="stMetricLabel"] {{ color: #667085; }}
        div[data-testid="stMetricValue"] {{ color: var(--quant-navy); font-family: 'Space Grotesk', sans-serif; }}
        .footer {{ color: #98A2B3; border-top: 1px solid #E4E9F0; padding-top: 16px; margin-top: 34px; font-size: .78rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def integer(value: float | int) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.0f}".replace(",", ".")


def decimal(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def percent(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:.1f}%".replace(".", ",")


def money(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"US$ {value:,.0f}".replace(",", ".")


def chart_layout(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font={"family": "DM Sans, sans-serif", "color": PRIMARY},
        margin={"l": 12, "r": 18, "t": 50, "b": 12},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def history_chart(data: pd.DataFrame) -> go.Figure:
    fig = px.line(data, x="data", y="vendas_saar_milhoes", labels={"data": "Data", "vendas_saar_milhoes": "Milhões SAAR"})
    fig.update_traces(line={"color": BLUE, "width": 2.3}, name="Vendas totais")
    fig.update_layout(title="Mercado agregado de veículos leves — série mensal")
    return chart_layout(fig, 420)


def brand_volume_chart(summary: pd.DataFrame) -> go.Figure:
    top = summary.nlargest(18, "configuracoes").sort_values("configuracoes")
    fig = px.bar(top, x="configuracoes", y="make", orientation="h", color="mpg_medio", color_continuous_scale=["#C7D7E8", BLUE, ORANGE], labels={"make": "Marca", "configuracoes": "Configurações EPA", "mpg_medio": "MPG/MPGe médio"}, title="Amplitude de portfólio por marca")
    fig.update_layout(coloraxis_colorbar={"title": "MPG/MPGe"})
    return chart_layout(fig, 510)


def brand_positioning_chart(summary: pd.DataFrame) -> go.Figure:
    position = summary.dropna(subset=["mpg_medio", "co2_medio_g_milha"]).copy()
    position = position[position["configuracoes"] >= 5]
    fig = px.scatter(
        position,
        x="co2_medio_g_milha",
        y="mpg_medio",
        size="configuracoes",
        color="participacao_eletrificada_pct",
        hover_name="make",
        hover_data={"modelos": True, "segmentos": True, "configuracoes": True, "participacao_eletrificada_pct": ":.1f", "co2_medio_g_milha": ":.0f", "mpg_medio": ":.1f"},
        color_continuous_scale=["#C7D7E8", TEAL, PURPLE],
        labels={"co2_medio_g_milha": "CO₂ médio de escapamento (g/milha)", "mpg_medio": "MPG/MPGe médio", "participacao_eletrificada_pct": "Mix eletrificado (%)"},
        title="Posicionamento de portfólio: eficiência, emissões e eletrificação",
    )
    return chart_layout(fig, 510)


def segment_chart(summary: pd.DataFrame) -> go.Figure:
    display = summary.nlargest(15, "configuracoes").sort_values("mpg_medio")
    fig = px.bar(display, x="mpg_medio", y="VClass", orientation="h", color="co2_medio_g_milha", color_continuous_scale="YlOrRd", labels={"VClass": "Segmento EPA", "mpg_medio": "MPG/MPGe médio", "co2_medio_g_milha": "CO₂ g/milha"}, title="Eficiência média por segmento")
    return chart_layout(fig, 470)


def powertrain_composition_chart(summary: pd.DataFrame) -> go.Figure:
    """Mostra o mix tecnológico sem sobrepor rótulos em uma pizza pequena."""
    display = summary.sort_values("participacao_pct", ascending=True).copy()
    maximum = float(display["participacao_pct"].max()) if not display.empty else 100.0
    fig = px.bar(
        display,
        x="participacao_pct",
        y="powertrain",
        orientation="h",
        color="powertrain",
        color_discrete_map=POWERTRAIN_COLORS,
        text="participacao_pct",
        labels={"powertrain": "Propulsão", "participacao_pct": "Participação das configurações (%)"},
        title="Composição tecnológica do portfólio filtrado",
    )
    fig.update_traces(
        texttemplate="%{x:.1f}%",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{y}</b><br>Participação: %{x:.1f}%<br><extra></extra>",
    )
    fig.update_xaxes(range=[0, maximum * 1.18], ticksuffix="%", title="Participação das configurações")
    fig.update_yaxes(title=None)
    return chart_layout(fig, 390)


def powertrain_trend_chart(trend: pd.DataFrame) -> go.Figure:
    fig = px.line(trend, x="year", y="configuracoes", color="powertrain", color_discrete_map=POWERTRAIN_COLORS, labels={"year": "Ano-modelo", "configuracoes": "Configurações EPA", "powertrain": "Propulsão"}, title="Evolução anual de configurações por propulsão")
    fig.update_traces(line={"width": 2.1})
    return chart_layout(fig, 450)


def efficiency_trend_chart(trend: pd.DataFrame) -> go.Figure:
    chart_data = trend.dropna(subset=["mpg_medio"])
    fig = px.line(chart_data, x="year", y="mpg_medio", color="powertrain", color_discrete_map=POWERTRAIN_COLORS, labels={"year": "Ano-modelo", "mpg_medio": "MPG/MPGe médio", "powertrain": "Propulsão"}, title="Eficiência média por tecnologia")
    fig.update_traces(line={"width": 2.1})
    return chart_layout(fig, 450)


def model_efficiency_chart(models: pd.DataFrame) -> go.Figure:
    chart_data = models.dropna(subset=["mpg_medio", "co2_medio_g_milha"]).copy()
    chart_data = chart_data[chart_data["configuracoes"] >= 2].nlargest(500, "configuracoes")
    fig = px.scatter(
        chart_data,
        x="co2_medio_g_milha",
        y="mpg_medio",
        color="powertrain",
        size="configuracoes",
        color_discrete_map=POWERTRAIN_COLORS,
        hover_name="model",
        hover_data={"make": True, "VClass": True, "ano_inicial": True, "ano_final": True, "autonomia_max_milhas": True, "co2_medio_g_milha": ":.0f", "mpg_medio": ":.1f"},
        labels={"co2_medio_g_milha": "CO₂ médio de escapamento (g/milha)", "mpg_medio": "MPG/MPGe médio", "powertrain": "Propulsão"},
        title="Mapa de modelos: eficiência e emissões por configuração de produto",
    )
    return chart_layout(fig, 510)


def stl_chart(stl: pd.DataFrame) -> go.Figure:
    labels = [("observada", "Série observada", BLUE), ("tendencia", "Tendência", ORANGE), ("sazonalidade", "Sazonalidade", TEAL), ("residuo", "Resíduo", "#667085")]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.055, subplot_titles=[label[1] for label in labels])
    for row, (column, _, color) in enumerate(labels, start=1):
        fig.add_trace(go.Scatter(x=stl["data"], y=stl[column], mode="lines", line={"color": color, "width": 1.7}, showlegend=False), row=row, col=1)
    fig.update_layout(title="Decomposição STL: observado, tendência, sazonalidade e resíduo", height=760, margin={"l": 12, "r": 18, "t": 66, "b": 15}, template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", font={"family": "DM Sans, sans-serif", "color": PRIMARY})
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def acf_chart(values: pd.DataFrame, column: str, title: str, color: str) -> go.Figure:
    plot_data = values.iloc[:37]
    fig = px.bar(plot_data, x="lag", y=column, labels={"lag": "Defasagem", column: "Correlação"}, title=title)
    fig.update_traces(marker_color=color)
    fig.add_hline(y=0, line_color=PRIMARY, line_width=1)
    return chart_layout(fig, 350)


def backtest_chart(summary: pd.DataFrame, winner: str) -> go.Figure:
    colors = [ORANGE if model == winner else "#B8C2D1" for model in summary["modelo"]]
    fig = go.Figure(go.Bar(x=summary["modelo"], y=summary["mape_medio"], error_y={"type": "data", "array": summary["mape_desvio"].fillna(0)}, marker_color=colors, text=[f"{value:.2f}%" for value in summary["mape_medio"]], textposition="outside"))
    fig.update_layout(title="MAPE médio por modelo, com dispersão entre dobras", yaxis_title="MAPE (%)", xaxis_title="Modelo")
    return chart_layout(fig, 390)


def residual_chart(residuals: np.ndarray) -> go.Figure:
    fig = px.histogram(x=residuals, nbins=12, labels={"x": "Resíduo (milhões SAAR)", "count": "Frequência"}, title="Distribuição dos resíduos fora da amostra")
    fig.update_traces(marker_color=TEAL, marker_line_color="white", marker_line_width=1)
    fig.add_vline(x=0, line_color=PRIMARY, line_width=1)
    return chart_layout(fig, 350)


def forecast_chart(data: pd.DataFrame, forecast: pd.DataFrame, winner: str) -> go.Figure:
    recent = data.tail(48)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=recent["data"], y=recent["vendas_saar_milhoes"], mode="lines", name="Histórico", line={"color": BLUE, "width": 2.2}))
    fig.add_trace(go.Scatter(x=forecast["data"], y=forecast["cenario_conservador"], mode="lines", name="Faixa p10–p90", line={"color": "rgba(232,117,50,.25)", "width": 1}))
    fig.add_trace(go.Scatter(x=forecast["data"], y=forecast["cenario_otimista"], mode="lines", fill="tonexty", fillcolor="rgba(232,117,50,.18)", line={"color": "rgba(232,117,50,.25)", "width": 1}, showlegend=False))
    fig.add_trace(go.Scatter(x=forecast["data"], y=forecast["cenario_base"], mode="lines+markers", name="Previsão base", line={"color": ORANGE, "width": 2.6}))
    fig.add_vline(x=data["data"].max(), line_dash="dot", line_color=PRIMARY, annotation_text="Corte histórico", annotation_position="top left")
    fig.update_layout(title=f"Projeção de mercado — {len(forecast)} meses · {winner}", yaxis_title="Milhões de unidades SAAR", xaxis_title="Data")
    return chart_layout(fig, 500)


def production_chart(plan: pd.DataFrame, capacity: int) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.13, subplot_titles=["Demanda de referência versus produção", "Estoque e demanda pendente"])
    fig.add_trace(go.Bar(x=plan["data"], y=plan["demanda_planejada_veiculos"], name="Demanda de referência", marker_color="#A9C7E3"), row=1, col=1)
    fig.add_trace(go.Scatter(x=plan["data"], y=plan["producao_recomendada"], name="Produção recomendada", mode="lines+markers", line={"color": ORANGE, "width": 2.4}), row=1, col=1)
    fig.add_hline(y=capacity, line_dash="dash", line_color=PRIMARY, annotation_text="Capacidade", row=1, col=1)
    fig.add_trace(go.Scatter(x=plan["data"], y=plan["estoque_final"], name="Estoque final", mode="lines+markers", line={"color": BLUE, "width": 2}), row=2, col=1)
    fig.add_trace(go.Scatter(x=plan["data"], y=plan["demanda_pendente"], name="Demanda pendente", mode="lines+markers", line={"color": RED, "width": 2, "dash": "dot"}), row=2, col=1)
    fig.update_yaxes(title_text="Veículos", row=1, col=1)
    fig.update_yaxes(title_text="Veículos", row=2, col=1)
    fig.update_layout(title="Cenário operacional parametrizado", height=700)
    return chart_layout(fig, 700)


def sensitivity_chart(sensitivity: pd.DataFrame) -> go.Figure:
    display_data = sensitivity.copy()
    display_data.index = [integer(index) for index in display_data.index]
    display_data.columns = [f"{float(column):.0%}" for column in display_data.columns]
    fig = px.imshow(display_data, text_auto=".0f", aspect="auto", color_continuous_scale="YlOrRd", labels={"x": "Participação de mercado", "y": "Capacidade mensal", "color": "Backlog acumulado"}, title="Sensibilidade do backlog acumulado")
    fig.update_traces(textfont={"size": 12})
    return chart_layout(fig, 410)


try:
    vehicle_data = load_vehicle_data(ROOT / "data" / "EPA_vehicles_snapshot.csv")
except Exception as error:
    st.error(f"Não foi possível carregar o catálogo EPA: {error}")
    st.stop()

vehicle_meta = vehicle_universe_metadata(vehicle_data)
year_bounds = (vehicle_meta["ano_inicial"], vehicle_meta["ano_final"])
default_product_years = (max(year_bounds[0], year_bounds[1] - 2), year_bounds[1])

with st.sidebar:
    st.markdown("## QUANT")
    st.caption("Automotive Intelligence")
    st.markdown("---")
    with st.form("parameters_form"):
        st.markdown("### Universo de produto")
        selected_years = st.slider("Ano-modelo", min_value=year_bounds[0], max_value=year_bounds[1], value=default_product_years)
        selected_makes = st.multiselect("Marcas EPA (campo make)", options=sorted(vehicle_data["make"].unique()), placeholder="Todas as marcas do catálogo")
        selected_powertrains = st.multiselect("Propulsão", options=sorted(vehicle_data["powertrain"].unique()), placeholder="Todas as tecnologias")
        selected_segments = st.multiselect("Segmento EPA", options=sorted(vehicle_data["VClass"].unique()), placeholder="Todos os segmentos")
        st.markdown("### Mercado e planejamento")
        n_folds = st.slider("Dobras do backtest", min_value=2, max_value=8, value=4)
        test_size = st.slider("Meses por dobra", min_value=3, max_value=12, value=6)
        horizon = st.slider("Horizonte de projeção", min_value=3, max_value=12, value=6)
        bootstrap_replicas = st.select_slider("Réplicas de bootstrap", options=[500, 1000, 2000, 5000], value=2000)
        participation_pct = st.slider("Participação de mercado de referência", min_value=2, max_value=20, value=8, step=1, format="%d%%")
        capacity = st.number_input("Capacidade mensal (veículos)", min_value=10_000, max_value=300_000, value=110_000, step=5_000)
        initial_inventory = st.number_input("Estoque inicial (veículos)", min_value=0, max_value=100_000, value=15_000, step=1_000)
        production_cost = st.number_input("Custo de produção (US$/veículo)", min_value=0, max_value=100_000, value=25_000, step=500)
        inventory_cost = st.number_input("Custo de estoque (US$/veículo/mês)", min_value=0, max_value=10_000, value=350, step=50)
        backlog_cost = st.number_input("Custo de ruptura (US$/veículo)", min_value=0, max_value=200_000, value=45_000, step=500)
        st.form_submit_button("Atualizar inteligência", use_container_width=True)
    st.markdown("---")
    st.markdown(f"[Mercado agregado — FRED TOTALSA]({FRED_SERIES_URL})")
    st.markdown(f"[Catálogo de produto — EPA]({EPA_DOWNLOAD_PAGE})")
    st.caption("FRED descreve o mercado agregado; EPA descreve especificações e eficiência de configurações de produto.")

filtered_vehicles = filter_vehicles(vehicle_data, selected_years, selected_makes, selected_powertrains, selected_segments)
product_kpis = portfolio_kpis(filtered_vehicles)
brand_data = brand_summary(filtered_vehicles)
brand_registry_data = brand_registry(vehicle_data)
model_data = model_summary(filtered_vehicles)
segment_data = segment_summary(filtered_vehicles)
powertrain_data = powertrain_summary(filtered_vehicles)
portfolio_trend = annual_portfolio_trend(filtered_vehicles)

try:
    with st.spinner("Atualizando mercado, portfólio, eficiência e cenário operacional..."):
        market_result = run_full_analysis(
            fallback_path=ROOT / "data" / "TOTALSA_snapshot.csv",
            n_folds=n_folds,
            test_size=test_size,
            horizon=horizon,
            bootstrap_replicas=bootstrap_replicas,
            seed=42,
            participation=participation_pct / 100,
            capacity=int(capacity),
            initial_inventory=int(initial_inventory),
            production_cost=float(production_cost),
            inventory_cost=float(inventory_cost),
            backlog_cost=float(backlog_cost),
        )
except Exception as error:
    st.error(f"Não foi possível executar a camada de mercado: {error}")
    st.stop()

market_data = market_result["data"]
diagnostics = market_result["diagnostics"]
backtest = market_result["backtest"]
forecast = market_result["forecast"]
production = market_result["production"]
plan = production["plan"]
scenarios = production["scenarios"]
summary = backtest["summary"]
winner = backtest["winner"]
base_row = scenarios.loc[scenarios["Cenário"] == "Base"].iloc[0]

st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">Quantitative intelligence · automotive</div>
        <h1>Automotive Intelligence Platform</h1>
        <p>Uma plataforma integrada para ler o mercado agregado, explorar a arquitetura de portfólio por marca e modelo, acompanhar eficiência tecnológica e estruturar cenários operacionais.</p>
        <div class="quant-tag">DADOS OFICIAIS · FRED / U.S. EPA · MERCADO, PRODUTO E TECNOLOGIA</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-kicker">Visão integrada</div><div class="section-title">Mercado, produto e tecnologia em uma única camada analítica</div>', unsafe_allow_html=True)
metrics = st.columns(6)
metrics[0].metric("Modelo de mercado", winner)
metrics[1].metric("MAPE médio", f"{summary.iloc[0]['mape_medio']:.2f}%")
metrics[2].metric("Configurações EPA", integer(product_kpis["configuracoes"]))
metrics[3].metric("Marcas no filtro", integer(product_kpis["marcas"]))
metrics[4].metric("Modelos no filtro", integer(product_kpis["modelos"]))
metrics[5].metric("Mix eletrificado", percent(product_kpis["eletrificados_pct"]))

st.markdown(
    f"""
    <div class="insight"><strong>Leitura integrada.</strong> A camada de mercado combina série mensal, validação temporal e cenários de demanda. A camada de produto cobre <strong>{integer(vehicle_meta['observacoes'])} configurações</strong>, <strong>{integer(vehicle_meta['marcas'])} marcas</strong> e <strong>{integer(vehicle_meta['modelos'])} modelos</strong> no catálogo EPA, permitindo comparar eficiência, emissões, autonomia e diversidade de portfólio. As fontes são complementares: o FRED mede mercado agregado; a EPA descreve atributos técnicos de produto.</div>
    """,
    unsafe_allow_html=True,
)

method_columns = st.columns(5)
method_steps = [
    ("01", "Mercado", "Série mensal, sazonalidade e dinâmica agregada."),
    ("02", "Produto", "Marca, modelo, segmento e configuração técnica."),
    ("03", "Tecnologia", "Propulsão, eficiência, emissões e autonomia."),
    ("04", "Previsão", "Walk-forward, comparação e incerteza empírica."),
    ("05", "Cenários", "Capacidade, estoque, serviço e sensibilidade."),
]
for column, (step, title, description) in zip(method_columns, method_steps):
    column.markdown(f'<div class="method-card"><div class="step">Camada {step}</div><strong>{title}</strong><span>{description}</span></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
tab_overview, tab_product, tab_efficiency, tab_market, tab_planning, tab_method = st.tabs(["Visão integrada", "Produto & Marcas", "Eficiência & Transição", "Mercado & Validação", "Planejamento", "Metodologia & Dados"])

with tab_overview:
    market_col, portfolio_col = st.columns([1.1, 1])
    with market_col:
        st.plotly_chart(forecast_chart(market_data, forecast, winner), use_container_width=True, config={"displaylogo": False}, key="overview_market_forecast")
    with portfolio_col:
        if brand_data.empty:
            st.info("Os filtros atuais não retornaram configurações de produto.")
        else:
            st.plotly_chart(brand_volume_chart(brand_data), use_container_width=True, config={"displaylogo": False}, key="overview_brand_volume")
    st.markdown("#### Prioridades de inteligência")
    priorities = pd.DataFrame(
        {
            "Domínio": ["Mercado", "Portfólio", "Tecnologia", "Cenário operacional"],
            "Pergunta respondida": ["Qual é a trajetória agregada e a faixa de demanda?", "Quais marcas, modelos e segmentos compõem o universo filtrado?", "Como eficiência, emissões e propulsão se distribuem no portfólio?", "Como uma capacidade parametrizada responde a cenários de demanda?"],
            "Evidência": ["FRED TOTALSA, backtest e bootstrap", "EPA: make, model, VClass e ano-modelo", "EPA: combustível, MPG/MPGe, CO₂, autonomia e custo anual", "Otimização linear, capacidade, estoque e backlog"],
        }
    )
    st.dataframe(priorities, use_container_width=True, hide_index=True)
    st.markdown(f'<p class="source-note">Visão executiva: previsão de mercado p10–p90 e estrutura de portfólio no recorte atual. Mercado: {market_result["source_label"]}, {market_data["data"].min():%m/%Y}–{market_data["data"].max():%m/%Y}. Produto: snapshot EPA {vehicle_meta["ano_inicial"]}–{vehicle_meta["ano_final"]}; filtros ativos: {selected_years[0]}–{selected_years[1]}.</p>', unsafe_allow_html=True)

with tab_product:
    st.markdown("### Arquitetura de portfólio")
    product_metrics = st.columns(5)
    product_metrics[0].metric("Configurações", integer(product_kpis["configuracoes"]))
    product_metrics[1].metric("Fabricantes", integer(product_kpis["marcas"]))
    product_metrics[2].metric("Modelos", integer(product_kpis["modelos"]))
    product_metrics[3].metric("Segmentos", integer(filtered_vehicles["VClass"].nunique() if not filtered_vehicles.empty else 0))
    product_metrics[4].metric("Eficiência média", f"{decimal(product_kpis['mpg_medio'])} MPG/MPGe")
    if brand_data.empty:
        st.warning("Os filtros não retornaram um conjunto de produto para análise.")
    else:
        brand_left, brand_right = st.columns(2)
        with brand_left:
            st.plotly_chart(brand_volume_chart(brand_data), use_container_width=True, config={"displaylogo": False}, key="product_brand_volume")
        with brand_right:
            st.plotly_chart(brand_positioning_chart(brand_data), use_container_width=True, config={"displaylogo": False}, key="product_brand_positioning")
        st.markdown("#### Scorecard por marca")
        brand_display = brand_data.rename(columns={"make": "Marca EPA (make)", "configuracoes": "Configurações", "modelos": "Modelos", "segmentos": "Segmentos", "ano_inicial": "Primeiro ano", "ano_final": "Último ano", "mpg_medio": "MPG/MPGe médio", "co2_medio_g_milha": "CO₂ médio (g/milha)", "custo_anual_medio_usd": "Custo anual médio (US$)", "participacao_eletrificada_pct": "Mix eletrificado (%)", "autonomia_max_milhas": "Autonomia máxima (milhas)"})
        st.dataframe(brand_display.style.format({"Configurações": "{:,.0f}", "Modelos": "{:,.0f}", "Segmentos": "{:,.0f}", "Primeiro ano": "{:.0f}", "Último ano": "{:.0f}", "MPG/MPGe médio": "{:.1f}", "CO₂ médio (g/milha)": "{:.0f}", "Custo anual médio (US$)": "US$ {:,.0f}", "Mix eletrificado (%)": "{:.1f}%", "Autonomia máxima (milhas)": "{:.0f}"}), use_container_width=True, hide_index=True)
        st.markdown("#### Auditoria de nomes de marca")
        st.info("Os nomes são os valores literais do campo `make` publicado pela EPA. O catálogo cobre décadas; por isso, a presença de um nome não equivale a uma marca comercialmente ativa. O indicador abaixo mostra somente o último ano-modelo registrado no snapshot.")
        registry_display = brand_registry_data.rename(columns={"make": "Marca EPA (make)", "configuracoes": "Configurações", "modelos": "Modelos", "ano_inicial": "Primeiro ano", "ano_final": "Último ano", "presenca_no_snapshot": "Presença temporal no snapshot"})
        with st.expander("Abrir registro de marcas e cobertura temporal da EPA"):
            st.dataframe(registry_display.style.format({"Configurações": "{:,.0f}", "Modelos": "{:,.0f}", "Primeiro ano": "{:.0f}", "Último ano": "{:.0f}"}), use_container_width=True, hide_index=True, height=460)
        st.caption("Auditoria reprodutível disponível em `docs/AUDITORIA_CATALOGO_EPA.md`; fonte oficial: FuelEconomy.gov / U.S. EPA.")
        st.markdown("#### Estrutura por segmento")
        segment_left, segment_right = st.columns([1.1, 1])
        with segment_left:
            st.plotly_chart(segment_chart(segment_data), use_container_width=True, config={"displaylogo": False}, key="product_segment_efficiency")
        with segment_right:
            segment_display = segment_data.rename(columns={"VClass": "Segmento EPA", "configuracoes": "Configurações", "marcas": "Marcas", "modelos": "Modelos", "mpg_medio": "MPG/MPGe médio", "co2_medio_g_milha": "CO₂ médio (g/milha)", "custo_anual_medio_usd": "Custo anual médio (US$)"})
            st.dataframe(segment_display.style.format({"Configurações": "{:,.0f}", "Marcas": "{:,.0f}", "Modelos": "{:,.0f}", "MPG/MPGe médio": "{:.1f}", "CO₂ médio (g/milha)": "{:.0f}", "Custo anual médio (US$)": "US$ {:,.0f}"}), use_container_width=True, hide_index=True, height=470)

with tab_efficiency:
    st.markdown("### Transição tecnológica e eficiência de produto")
    if powertrain_data.empty:
        st.warning("Os filtros atuais não retornaram tecnologias de propulsão para análise.")
    else:
        powertrain_left, powertrain_right = st.columns([0.85, 1.15])
        with powertrain_left:
            st.plotly_chart(powertrain_composition_chart(powertrain_data), use_container_width=True, config={"displaylogo": False}, key="efficiency_powertrain_mix")
        with powertrain_right:
            powertrain_display = powertrain_data.rename(columns={"powertrain": "Propulsão", "configuracoes": "Configurações", "marcas": "Marcas", "modelos": "Modelos", "mpg_medio": "MPG/MPGe médio", "co2_medio_g_milha": "CO₂ médio (g/milha)", "autonomia_max_milhas": "Autonomia máxima (milhas)", "participacao_pct": "Participação (%)"})
            st.dataframe(powertrain_display.style.format({"Configurações": "{:,.0f}", "Marcas": "{:,.0f}", "Modelos": "{:,.0f}", "MPG/MPGe médio": "{:.1f}", "CO₂ médio (g/milha)": "{:.0f}", "Autonomia máxima (milhas)": "{:.0f}", "Participação (%)": "{:.1f}%"}), use_container_width=True, hide_index=True, height=420)
        trend_left, trend_right = st.columns(2)
        with trend_left:
            st.plotly_chart(powertrain_trend_chart(portfolio_trend), use_container_width=True, config={"displaylogo": False}, key="efficiency_powertrain_trend")
        with trend_right:
            st.plotly_chart(efficiency_trend_chart(portfolio_trend), use_container_width=True, config={"displaylogo": False}, key="efficiency_mpg_trend")
        st.markdown("### Mapa competitivo por modelo")
        st.plotly_chart(model_efficiency_chart(model_data), use_container_width=True, config={"displaylogo": False}, key="efficiency_model_map")
        ranked_models = model_data.sort_values(["mpg_medio", "configuracoes"], ascending=[False, False]).head(150).rename(columns={"make": "Marca", "model": "Modelo", "VClass": "Segmento EPA", "powertrain": "Propulsão", "configuracoes": "Configurações", "ano_inicial": "Ano inicial", "ano_final": "Ano final", "mpg_medio": "MPG/MPGe médio", "co2_medio_g_milha": "CO₂ médio (g/milha)", "custo_anual_medio_usd": "Custo anual médio (US$)", "autonomia_max_milhas": "Autonomia máxima (milhas)", "cilindros_medios": "Cilindros médios", "motor_medio_litros": "Motor médio (L)"})
        st.dataframe(ranked_models.style.format({"Configurações": "{:,.0f}", "MPG/MPGe médio": "{:.1f}", "CO₂ médio (g/milha)": "{:.0f}", "Custo anual médio (US$)": "US$ {:,.0f}", "Autonomia máxima (milhas)": "{:.0f}", "Cilindros médios": "{:.1f}", "Motor médio (L)": "{:.1f}"}), use_container_width=True, hide_index=True, height=460)
        st.caption("MPG/MPGe, CO₂ de escapamento, autonomia e custo anual são estimativas publicadas para configurações específicas. Métricas não representam participação de vendas ou qualidade de produto.")

with tab_market:
    st.markdown("### Mercado agregado, diagnóstico e validação preditiva")
    st.caption("Esta aba concentra a série histórica, o confronto de modelos e os diagnósticos fora da amostra. A aba Visão integrada mostra somente a projeção executiva e o retrato de portfólio.")
    market_left, market_right = st.columns([1.25, 1])
    with market_left:
        st.plotly_chart(history_chart(market_data), use_container_width=True, config={"displaylogo": False}, key="market_history")
    with market_right:
        st.plotly_chart(backtest_chart(summary, winner), use_container_width=True, config={"displaylogo": False}, key="market_backtest")
    st.dataframe(summary.style.format({"mape_medio": "{:.2f}%", "mape_desvio": "{:.2f} p.p."}), use_container_width=True, hide_index=True)
    diagnostic_left, diagnostic_right = st.columns(2)
    with diagnostic_left:
        st.plotly_chart(residual_chart(backtest["residuals"]), use_container_width=True, config={"displaylogo": False}, key="market_residual_distribution")
    with diagnostic_right:
        st.plotly_chart(acf_chart(backtest["residual_acf"], "acf", "ACF dos resíduos fora da amostra", TEAL), use_container_width=True, config={"displaylogo": False}, key="market_residual_acf")
    adf_table = pd.DataFrame({"Teste": ["ADF em nível", "ADF na primeira diferença"], "Estatística": [diagnostics["adf_level"]["statistic"], diagnostics["adf_diff"]["statistic"]], "p-valor": [diagnostics["adf_level"]["pvalue"], diagnostics["adf_diff"]["pvalue"]]})
    lb_table = backtest["ljung_box"].rename(columns={"lb_stat": "Estatística Ljung-Box", "lb_pvalue": "p-valor"})
    adf_col, lb_col = st.columns(2)
    with adf_col:
        st.markdown("#### Estacionariedade")
        st.dataframe(adf_table.style.format({"Estatística": "{:.3f}", "p-valor": "{:.4f}"}), use_container_width=True, hide_index=True)
    with lb_col:
        st.markdown("#### Resíduos")
        st.dataframe(lb_table.style.format({"Estatística Ljung-Box": "{:.3f}", "p-valor": "{:.4f}"}), use_container_width=True, hide_index=True)
    with st.expander("Abrir decomposição STL e desempenho por dobra"):
        st.plotly_chart(stl_chart(diagnostics["stl"]), use_container_width=True, config={"displaylogo": False}, key="market_stl")
        st.dataframe(backtest["results"].style.format({"MAE (milhões SAAR)": "{:.3f}", "RMSE (milhões SAAR)": "{:.3f}", "MAPE (%)": "{:.2f}%"}), use_container_width=True, hide_index=True)

with tab_planning:
    st.markdown("### Projeção e cenário operacional")
    st.plotly_chart(forecast_chart(market_data, forecast, winner), use_container_width=True, config={"displaylogo": False}, key="planning_forecast")
    forecast_display = forecast.rename(columns={"data": "Data", "cenario_conservador": "Faixa inferior — p10", "cenario_base": "Base", "cenario_otimista": "Faixa superior — p90", "demanda_mensal_base_milhoes": "Base mensal aproximada"})
    st.dataframe(forecast_display.style.format({"Faixa inferior — p10": "{:.3f}", "Base": "{:.3f}", "Faixa superior — p90": "{:.3f}", "Base mensal aproximada": "{:.3f}"}), use_container_width=True, hide_index=True)
    st.download_button("Exportar projeção em CSV", data=forecast_display.to_csv(index=False).encode("utf-8"), file_name="projecao_mercado_automotivo.csv", mime="text/csv")
    st.markdown("### Capacidade, estoque e serviço")
    planning_metrics = st.columns(4)
    planning_metrics[0].metric("Demanda de referência", f"{integer(base_row['Demanda total (veículos)'])} veículos")
    planning_metrics[1].metric("Produção recomendada", f"{integer(base_row['Produção total (veículos)'])} veículos")
    planning_metrics[2].metric("Custo parametrizado", money(base_row["Custo total (US$)"]))
    planning_metrics[3].metric("Backlog final", f"{integer(base_row['Demanda pendente final'])} veículos")
    st.plotly_chart(production_chart(plan, int(capacity)), use_container_width=True, config={"displaylogo": False}, key="planning_production")
    plan_display = plan.rename(columns={"data": "Data", "demanda_planejada_veiculos": "Demanda de referência", "producao_recomendada": "Produção recomendada", "estoque_final": "Estoque final", "demanda_pendente": "Demanda pendente", "utilizacao_capacidade_pct": "Utilização da capacidade (%)"})[["Data", "Demanda de referência", "Produção recomendada", "Estoque final", "Demanda pendente", "Utilização da capacidade (%)"]]
    st.dataframe(plan_display.style.format({"Demanda de referência": "{:,.0f}", "Produção recomendada": "{:,.0f}", "Estoque final": "{:,.0f}", "Demanda pendente": "{:,.0f}", "Utilização da capacidade (%)": "{:.1f}%"}), use_container_width=True, hide_index=True)
    st.download_button("Exportar plano em CSV", data=plan_display.to_csv(index=False).encode("utf-8"), file_name="plano_operacional_automotivo.csv", mime="text/csv")
    scenario_left, scenario_right = st.columns([1.15, 1])
    with scenario_left:
        st.markdown("#### Comparação de cenários")
        st.dataframe(scenarios.style.format({"Demanda total (veículos)": "{:,.0f}", "Produção total (veículos)": "{:,.0f}", "Utilização média (%)": "{:.1f}%", "Demanda pendente final": "{:,.0f}", "Custo total (US$)": "US$ {:,.0f}"}), use_container_width=True, hide_index=True)
    with scenario_right:
        st.plotly_chart(sensitivity_chart(production["sensitivity"]), use_container_width=True, config={"displaylogo": False}, key="planning_sensitivity")
    st.caption("A camada de planejamento usa parâmetros operacionais ajustáveis. Ela estrutura trade-offs de capacidade, estoque, nível de serviço e ruptura; não presume acesso a capacidade, custo ou inventário confidencial de uma empresa.")

with tab_method:
    st.markdown("### Arquitetura de dados")
    sources = pd.DataFrame(
        {
            "Fonte": ["FRED — TOTALSA", "U.S. EPA / FuelEconomy.gov", "Camada quantitativa"],
            "Cobertura": ["Vendas mensais agregadas de veículos leves nos EUA, taxa anual ajustada sazonalmente.", f"{integer(vehicle_meta['observacoes'])} configurações de veículos leves, {vehicle_meta['ano_inicial']}–{vehicle_meta['ano_final']}, com fabricante, modelo, classe, combustível, eficiência, emissões e autonomia.", "Diagnóstico temporal, backtest walk-forward, bootstrap de resíduos e programação linear."],
            "Uso na plataforma": ["Leitura de mercado, previsão e cenários de demanda.", "Exploração por marca, modelo, segmento, propulsão e desempenho técnico.", "Conecta evidência histórica a cenários operacionais parametrizados."],
        }
    )
    st.dataframe(sources, use_container_width=True, hide_index=True)
    st.markdown("### Método de previsão e decisão")
    st.markdown("A série de mercado é submetida a checagens de qualidade, ADF, STL, ACF/PACF e validação temporal com janela expansiva. A referência sazonal, Holt-Winters e Ridge com defasagens são comparados por MAE, RMSE e MAPE fora da amostra. O modelo selecionado é reajustado com todo o histórico, e os resíduos do backtest são reamostrados para compor a faixa empírica p10–p90.")
    st.latex(r"D_t = round((SAAR_t / 12) \times 1.000.000 \times participação)")
    st.latex(r"min \sum_t c_p P_t + c_i I_t + c_b B_t")
    st.latex(r"I_t - B_t = I_{t-1} - B_{t-1} + P_t - D_t, \quad 0 \le P_t \le Capacidade")
    st.markdown("A otimização representa uma política de custo parametrizada para produção, estoque e demanda pendente. A finalidade é tornar explícita a consequência das escolhas de capacidade e nível de serviço sob cenários de mercado.")
    st.markdown("### Escopo de interpretação")
    st.info("A EPA disponibiliza atributos técnicos e estimativas de eficiência por configuração de veículo; a fonte não mede vendas, participação de mercado ou rentabilidade por marca. A comparação entre portfólios deve ser lida como inteligência de produto, não como ranking comercial. O FRED, por sua vez, representa o mercado agregado e não atribui vendas a fabricantes específicos.")
    st.markdown("### Referências")
    st.markdown(f"[1] [FRED — Total Vehicle Sales (TOTALSA)]({FRED_SERIES_URL})  \n[2] [U.S. EPA / FuelEconomy.gov — Download Fuel Economy Data]({EPA_DOWNLOAD_PAGE})  \n[3] [EPA — 50 Years of Automotive Trends Report](https://www.epa.gov/greenvehicles/50-years-epas-automotive-trends-report)  \n[4] Cleveland et al. (1990), *STL: A Seasonal-Trend Decomposition Procedure Based on Loess*.  \n[5] Ljung & Box (1978), *On a Measure of Lack of Fit in Time Series Models*.  \n[6] Efron (1979), *Bootstrap Methods: Another Look at the Jackknife*.")
    st.caption(f"Snapshot EPA incluído no repositório: {EPA_DATA_URL}. A página oficial informa dados para todos os anos-modelo de 1984 a {vehicle_meta['ano_final']}.")

st.markdown('<div class="footer">QUANT AUTOMOTIVE INTELLIGENCE · Mercado agregado, portfólio de produto, eficiência tecnológica e cenários operacionais</div>', unsafe_allow_html=True)
