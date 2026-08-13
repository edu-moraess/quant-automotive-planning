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
import energy_intelligence as energy_module  # noqa: E402
import vehicle_intelligence as vehicle_module  # noqa: E402

analysis_module = importlib.reload(analysis_module)
energy_module = importlib.reload(energy_module)
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
segment_summary = vehicle_module.segment_summary
vehicle_universe_metadata = vehicle_module.vehicle_universe_metadata
load_energy_prices = energy_module.load_energy_prices
latest_energy_snapshot = energy_module.latest_energy_snapshot
energy_price_index = energy_module.energy_price_index
add_energy_cost_estimate = energy_module.add_energy_cost_estimate
energy_summary = energy_module.energy_summary
spearman_correlation_matrix = energy_module.spearman_correlation_matrix
strongest_spearman_pairs = energy_module.strongest_spearman_pairs

st.set_page_config(page_title="Quant Automotive Intelligence", page_icon="Q", layout="wide", initial_sidebar_state="expanded")

PRIMARY = "#14213D"
BLUE = "#1F4E79"
ORANGE = "#E87532"
TEAL = "#008A8A"
GREEN = "#4E9F3D"
RED = "#C43D3D"
PURPLE = "#6959CD"
MUTED = "#667085"
GRID = "#E5EAF0"
ENERGY_COLORS = {
    "Gasolina": "#577590",
    "Diesel": "#495867",
    "Eletricidade": "#6A5ACD",
    "Híbrido plug-in": "#00A6A6",
    "Etanol / E85": "#D68C45",
    "Gás natural": "#8AB17D",
    "Hidrogênio": "#2F75B5",
}

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
      html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
      .stApp { background: #F6F8FB; }
      [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E5EAF0; }
      .block-container { max-width: 1460px; padding-top: 1.75rem; padding-bottom: 3rem; }
      h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; color: #14213D; letter-spacing: -0.025em; }
      .hero { background: linear-gradient(112deg, #14213D 0%, #1F4E79 68%, #2D75B3 100%); border-radius: 16px; color: #fff; padding: 28px 34px; margin-bottom: 20px; box-shadow: 0 12px 28px rgba(20,33,61,.12); }
      .hero .eyebrow { font-size: .68rem; letter-spacing: .16em; text-transform: uppercase; font-weight: 700; opacity: .78; margin-bottom: 8px; }
      .hero h1 { color: #fff; margin: 0; font-size: 2rem; line-height: 1.1; }
      .hero p { margin: 9px 0 0; color: rgba(255,255,255,.85); line-height: 1.52; max-width: 900px; }
      .source-strip { font-size: .8rem; color: #667085; margin: 5px 0 16px; }
      .section-kicker { color: #E87532; font-weight: 700; font-size: .7rem; letter-spacing: .13em; text-transform: uppercase; margin-top: 4px; }
      .section-title { font-family: 'Space Grotesk', sans-serif; color: #14213D; font-size: 1.35rem; font-weight: 700; margin: 4px 0 12px; }
      .insight { background: #FFFFFF; border: 1px solid #E5EAF0; border-left: 4px solid #E87532; border-radius: 10px; padding: 14px 17px; color: #344054; line-height: 1.55; margin: 10px 0 16px; }
      .note { background: #EEF5FC; border: 1px solid #D7E5F4; border-radius: 10px; padding: 13px 15px; color: #294D70; line-height: 1.5; font-size: .9rem; }
      div[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #E5EAF0; border-radius: 11px; padding: 13px 15px; box-shadow: 0 3px 10px rgba(20,33,61,.025); }
      div[data-testid="stMetricLabel"] p { white-space: normal; min-height: 34px; color: #667085; line-height: 1.2; }
      div[data-testid="stMetricValue"] { color: #14213D; font-family: 'Space Grotesk', sans-serif; }
      .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #DCE3EA; }
      .stTabs [data-baseweb="tab"] { height: 45px; padding: 0 13px; color: #667085; font-weight: 600; font-size: .88rem; }
      .stTabs [aria-selected="true"] { color: #14213D; border-bottom-color: #E87532; }
      .footer { color: #98A2B3; border-top: 1px solid #E5EAF0; padding-top: 15px; margin-top: 28px; font-size: .78rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def fmt_int(value: float | int) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.0f}".replace(",", ".")


def fmt_decimal(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_usd(value: float, digits: int = 2) -> str:
    if pd.isna(value):
        return "—"
    return f"US$ {value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:.1f}%".replace(".", ",")


def style_chart(fig: go.Figure, height: int = 410, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        font={"family": "DM Sans, sans-serif", "color": PRIMARY},
        margin={"l": 12, "r": 22, "t": 54, "b": 18},
        showlegend=legend,
        legend={"orientation": "h", "y": 1.1, "x": 0, "font": {"size": 11}},
        hoverlabel={"font": {"family": "DM Sans, sans-serif"}},
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def forecast_chart(history: pd.DataFrame, forecast: pd.DataFrame, winner: str) -> go.Figure:
    recent = history.tail(42)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=recent["data"], y=recent["vendas_saar_milhoes"], mode="lines", name="Histórico", line={"color": BLUE, "width": 2.2}))
    fig.add_trace(go.Scatter(x=forecast["data"], y=forecast["cenario_conservador"], mode="lines", name="Faixa p10–p90", line={"color": "rgba(232,117,50,.26)", "width": 1}))
    fig.add_trace(go.Scatter(x=forecast["data"], y=forecast["cenario_otimista"], mode="lines", fill="tonexty", fillcolor="rgba(232,117,50,.17)", line={"color": "rgba(232,117,50,.26)", "width": 1}, showlegend=False))
    fig.add_trace(go.Scatter(x=forecast["data"], y=forecast["cenario_base"], mode="lines+markers", name="Projeção base", line={"color": ORANGE, "width": 2.6}, marker={"size": 5}))
    fig.add_vline(x=history["data"].max(), line_dash="dot", line_color=PRIMARY, line_width=1)
    fig.update_layout(title=f"Projeção de mercado · {winner}", yaxis_title="Milhões de unidades SAAR")
    return style_chart(fig, 405)


def brand_bar_chart(summary: pd.DataFrame) -> go.Figure:
    display = summary.nlargest(12, "configuracoes").sort_values("configuracoes")
    fig = px.bar(display, x="configuracoes", y="make", orientation="h", color="mpg_medio", color_continuous_scale=["#BFD3E6", BLUE, ORANGE], labels={"make": "Marca EPA", "configuracoes": "Configurações", "mpg_medio": "MPG/MPGe médio"}, title="Amplitude de portfólio no recorte")
    fig.update_layout(coloraxis_colorbar={"title": "MPG/MPGe", "len": 0.75})
    return style_chart(fig, 405, legend=False)


def brand_position_chart(summary: pd.DataFrame) -> go.Figure:
    display = summary.dropna(subset=["mpg_medio", "co2_medio_g_milha"]).query("configuracoes >= 3").nlargest(45, "configuracoes")
    fig = px.scatter(
        display,
        x="co2_medio_g_milha",
        y="mpg_medio",
        size="configuracoes",
        color="participacao_eletrificada_pct",
        hover_name="make",
        hover_data={"modelos": True, "segmentos": True, "ano_final": True, "co2_medio_g_milha": ":.0f", "mpg_medio": ":.1f", "participacao_eletrificada_pct": ":.1f"},
        color_continuous_scale=["#C8D8E8", TEAL, PURPLE],
        labels={"co2_medio_g_milha": "CO₂ de escapamento (g/mi)", "mpg_medio": "MPG/MPGe médio", "participacao_eletrificada_pct": "Mix eletrificado (%)"},
        title="Posicionamento técnico por marca",
    )
    fig.update_traces(marker={"opacity": 0.78, "line": {"color": "white", "width": 0.5}})
    return style_chart(fig, 440, legend=False)


def segment_chart(summary: pd.DataFrame) -> go.Figure:
    display = summary.nlargest(12, "configuracoes").sort_values("mpg_medio")
    fig = px.bar(display, x="mpg_medio", y="VClass", orientation="h", color="co2_medio_g_milha", color_continuous_scale="YlOrRd", labels={"VClass": "Segmento EPA", "mpg_medio": "MPG/MPGe médio", "co2_medio_g_milha": "CO₂ (g/mi)"}, title="Eficiência por segmento")
    return style_chart(fig, 440, legend=False)


def price_index_chart(index_data: pd.DataFrame) -> go.Figure:
    fig = px.line(index_data, x="data", y="indice_base_100", color="energia", color_discrete_map={"Gasolina regular": ENERGY_COLORS["Gasolina"], "Diesel": ENERGY_COLORS["Diesel"], "Eletricidade": ENERGY_COLORS["Eletricidade"]}, labels={"data": "Data", "indice_base_100": "Índice (início = 100)", "energia": "Energia"}, title="Variação relativa de preços de energia · últimos 48 meses")
    fig.add_hline(y=100, line_dash="dot", line_color=MUTED, line_width=1)
    fig.update_traces(line={"width": 2.2})
    return style_chart(fig, 390)


def energy_cost_chart(summary: pd.DataFrame) -> go.Figure:
    display = summary.dropna(subset=["custo_energia_100mi_mediano_usd"]).sort_values("custo_energia_100mi_mediano_usd")
    fig = px.bar(display, x="custo_energia_100mi_mediano_usd", y="fonte_energia", orientation="h", color="fonte_energia", color_discrete_map=ENERGY_COLORS, text="custo_energia_100mi_mediano_usd", labels={"fonte_energia": "Fonte de energia", "custo_energia_100mi_mediano_usd": "US$ por 100 milhas"}, title="Custo energético de referência por 100 milhas")
    fig.update_traces(texttemplate="US$ %{x:.2f}", textposition="outside", cliponaxis=False)
    fig.update_xaxes(title="US$ por 100 milhas")
    fig.update_yaxes(title=None)
    return style_chart(fig, 390, legend=False)


def correlation_chart(correlations: pd.DataFrame) -> go.Figure:
    labels = list(correlations.columns)
    fig = go.Figure(go.Heatmap(z=correlations.values, x=labels, y=labels, zmin=-1, zmax=1, colorscale=[[0, "#C43D3D"], [0.5, "#F4F6F8"], [1, "#1F4E79"]], colorbar={"title": "ρ"}, text=np.round(correlations.values, 2), texttemplate="%{text}", textfont={"size": 11}, hovertemplate="%{x}<br>%{y}<br>ρ Spearman: %{z:.2f}<extra></extra>"))
    fig.update_layout(title="Associações entre eficiência, custo, emissões e motorização")
    return style_chart(fig, 460, legend=False)


def history_chart(data: pd.DataFrame) -> go.Figure:
    fig = px.line(data, x="data", y="vendas_saar_milhoes", labels={"data": "Data", "vendas_saar_milhoes": "Milhões SAAR"}, title="Mercado agregado de veículos leves")
    fig.update_traces(line={"color": BLUE, "width": 2.25})
    return style_chart(fig, 405, legend=False)


def backtest_chart(summary: pd.DataFrame, winner: str) -> go.Figure:
    colors = [ORANGE if value == winner else "#B8C2D1" for value in summary["modelo"]]
    fig = go.Figure(go.Bar(x=summary["modelo"], y=summary["mape_medio"], error_y={"type": "data", "array": summary["mape_desvio"].fillna(0)}, marker_color=colors, text=[f"{value:.2f}%" for value in summary["mape_medio"]], textposition="outside"))
    fig.update_layout(title="Erro médio fora da amostra", xaxis_title=None, yaxis_title="MAPE (%)")
    return style_chart(fig, 405, legend=False)


def residual_chart(residuals: np.ndarray) -> go.Figure:
    fig = px.histogram(x=residuals, nbins=14, labels={"x": "Resíduo (milhões SAAR)", "count": "Frequência"}, title="Distribuição dos resíduos fora da amostra")
    fig.update_traces(marker_color=TEAL, marker_line_color="white", marker_line_width=1)
    fig.add_vline(x=0, line_color=PRIMARY, line_width=1)
    return style_chart(fig, 330, legend=False)


def acf_chart(values: pd.DataFrame) -> go.Figure:
    display = values.iloc[:25]
    fig = px.bar(display, x="lag", y="acf", labels={"lag": "Defasagem", "acf": "Autocorrelação"}, title="ACF dos resíduos")
    fig.update_traces(marker_color=TEAL)
    fig.add_hline(y=0, line_color=PRIMARY, line_width=1)
    return style_chart(fig, 330, legend=False)


def production_chart(plan: pd.DataFrame, capacity: int) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12, subplot_titles=["Demanda de referência e produção", "Estoque e demanda pendente"])
    fig.add_trace(go.Bar(x=plan["data"], y=plan["demanda_planejada_veiculos"], name="Demanda", marker_color="#BFD3E6"), row=1, col=1)
    fig.add_trace(go.Scatter(x=plan["data"], y=plan["producao_recomendada"], name="Produção", mode="lines+markers", line={"color": ORANGE, "width": 2.4}), row=1, col=1)
    fig.add_hline(y=capacity, line_dash="dash", line_color=PRIMARY, row=1, col=1)
    fig.add_trace(go.Scatter(x=plan["data"], y=plan["estoque_final"], name="Estoque", mode="lines+markers", line={"color": BLUE, "width": 2}), row=2, col=1)
    fig.add_trace(go.Scatter(x=plan["data"], y=plan["demanda_pendente"], name="Pendente", mode="lines+markers", line={"color": RED, "width": 2, "dash": "dot"}), row=2, col=1)
    fig.update_yaxes(title_text="Veículos", row=1, col=1)
    fig.update_yaxes(title_text="Veículos", row=2, col=1)
    fig.update_layout(title="Cenário operacional parametrizado")
    return style_chart(fig, 610)


def sensitivity_chart(sensitivity: pd.DataFrame) -> go.Figure:
    display = sensitivity.copy()
    display.index = [fmt_int(index) for index in display.index]
    display.columns = [f"{float(column):.0%}" for column in display.columns]
    fig = px.imshow(display, text_auto=".0f", aspect="auto", color_continuous_scale="YlOrRd", labels={"x": "Participação de mercado", "y": "Capacidade mensal", "color": "Backlog"}, title="Sensibilidade do backlog acumulado")
    fig.update_traces(textfont={"size": 11})
    return style_chart(fig, 360, legend=False)


try:
    raw_vehicles = load_vehicle_data(ROOT / "data" / "EPA_vehicles_snapshot.csv")
    energy_prices = load_energy_prices(ROOT / "data" / "energy_price_snapshot.csv")
    vehicle_data = add_energy_cost_estimate(raw_vehicles, energy_prices)
except Exception as error:
    st.error(f"Não foi possível carregar a camada de dados: {error}")
    st.stop()

metadata = vehicle_universe_metadata(vehicle_data)
year_bounds = (metadata["ano_inicial"], metadata["ano_final"])
default_years = (max(year_bounds[0], year_bounds[1] - 2), year_bounds[1])

with st.sidebar:
    st.markdown("## QUANT")
    st.caption("Automotive Intelligence")
    st.markdown("---")
    with st.form("filters"):
        st.markdown("### Catálogo de produto")
        selected_years = st.slider("Ano-modelo", min_value=year_bounds[0], max_value=year_bounds[1], value=default_years)
        selected_makes = st.multiselect("Marcas EPA (campo make)", sorted(vehicle_data["make"].unique()), placeholder="Todas as marcas")
        selected_powertrains = st.multiselect("Tecnologia", sorted(vehicle_data["powertrain"].unique()), placeholder="Todas as tecnologias")
        selected_segments = st.multiselect("Segmento EPA", sorted(vehicle_data["VClass"].unique()), placeholder="Todos os segmentos")
        st.markdown("### Mercado e cenário")
        horizon = st.slider("Horizonte de projeção", 3, 12, 6)
        n_folds = st.slider("Dobras do backtest", 2, 8, 4)
        test_size = st.slider("Meses por dobra", 3, 12, 6)
        capacity = st.number_input("Capacidade mensal", 10_000, 300_000, 110_000, 5_000)
        participation_pct = st.slider("Participação de referência", 2, 20, 8, 1, format="%d%%")
        apply = st.form_submit_button("Atualizar análise", use_container_width=True)
    st.markdown("---")
    st.markdown(f"[Mercado · FRED]({FRED_SERIES_URL})")
    st.markdown(f"[Produto · EPA]({EPA_DOWNLOAD_PAGE})")
    st.caption("Preço de energia nacional é contexto macro; não representa tarifa local ou contrato de frota.")

filtered = filter_vehicles(vehicle_data, selected_years, selected_makes, selected_powertrains, selected_segments)
kpis = portfolio_kpis(filtered)
brands = brand_summary(filtered)
segments = segment_summary(filtered)
energy_by_source = energy_summary(filtered)
correlations, pair_counts = spearman_correlation_matrix(filtered)
strong_pairs = strongest_spearman_pairs(correlations, pair_counts)
price_latest = latest_energy_snapshot(energy_prices)
price_index = energy_price_index(energy_prices)
registry = brand_registry(vehicle_data)

try:
    with st.spinner("Atualizando mercado, produto, energia e cenário operacional..."):
        market = run_full_analysis(
            fallback_path=ROOT / "data" / "TOTALSA_snapshot.csv",
            n_folds=n_folds,
            test_size=test_size,
            horizon=horizon,
            bootstrap_replicas=2000,
            seed=42,
            participation=participation_pct / 100,
            capacity=int(capacity),
            initial_inventory=15_000,
            production_cost=25_000,
            inventory_cost=350,
            backlog_cost=45_000,
        )
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
metric_summary = (
    backtest["results"].groupby("modelo", as_index=False)
    .agg(mae_medio=("MAE (milhões SAAR)", "mean"), rmse_medio=("RMSE (milhões SAAR)", "mean"))
)
summary_display = summary.merge(metric_summary, on="modelo", how="left")
base_scenario = scenarios.loc[scenarios["Cenário"] == "Base"].iloc[0]

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Quantitative intelligence · automotive</div>
      <h1>Automotive Intelligence Platform</h1>
      <p>Mercado agregado, portfólio de produto e custo de energia integrados em uma leitura objetiva e rastreável.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="section-kicker">Resumo executivo</div><div class="section-title">O retrato recente de mercado, produto e energia</div>', unsafe_allow_html=True)
metric_cols = st.columns(4)
metric_cols[0].metric("Modelo de mercado", winner)
metric_cols[1].metric("MAPE fora da amostra", f"{summary.iloc[0]['mape_medio']:.2f}%")
metric_cols[2].metric("Configurações no recorte", fmt_int(kpis["configuracoes"]))
metric_cols[3].metric("Mix eletrificado", fmt_pct(kpis["eletrificados_pct"]))

if filtered.empty:
    st.warning("Os filtros atuais não retornaram configurações EPA. Ajuste o recorte na lateral.")
    st.stop()

st.markdown(f'<div class="insight"><strong>Leitura do recorte.</strong> O filtro atual cobre <strong>{fmt_int(kpis["marcas"])} marcas EPA</strong> e <strong>{fmt_int(kpis["modelos"])} modelos</strong> entre {selected_years[0]} e {selected_years[1]}. A fonte EPA descreve configurações técnicas; a fonte FRED mede demanda agregada. Preços de energia são referências nacionais para contexto de custo, não dados de abastecimento por empresa.</div>', unsafe_allow_html=True)

tab_summary, tab_portfolio, tab_energy, tab_market, tab_planning, tab_method = st.tabs(["Resumo", "Portfólio", "Energia & Combustível", "Mercado & Forecast", "Planejamento", "Método & Dados"])

with tab_summary:
    left, right = st.columns([1.18, 0.82])
    with left:
        st.plotly_chart(forecast_chart(history, forecast, winner), use_container_width=True, config={"displaylogo": False}, key="summary_forecast")
    with right:
        st.plotly_chart(brand_bar_chart(brands), use_container_width=True, config={"displaylogo": False}, key="summary_brand_bar")
    st.markdown('<div class="note"><strong>Como ler.</strong> A projeção usa o modelo com menor MAPE médio no backtest temporal. A amplitude de portfólio conta configurações EPA, não unidades vendidas. A análise de energia detalha as unidades e fontes na aba própria.</div>', unsafe_allow_html=True)

with tab_portfolio:
    st.markdown("### Portfólio, segmentos e posicionamento técnico")
    pcols = st.columns(4)
    pcols[0].metric("Marcas EPA", fmt_int(kpis["marcas"]))
    pcols[1].metric("Modelos", fmt_int(kpis["modelos"]))
    pcols[2].metric("Segmentos", fmt_int(filtered["VClass"].nunique()))
    pcols[3].metric("Eficiência média", f"{fmt_decimal(kpis['mpg_medio'])} MPG/MPGe")
    top, lower = st.columns(2)
    with top:
        st.plotly_chart(brand_position_chart(brands), use_container_width=True, config={"displaylogo": False}, key="portfolio_position")
    with lower:
        st.plotly_chart(segment_chart(segments), use_container_width=True, config={"displaylogo": False}, key="portfolio_segments")
    st.markdown("#### Scorecard de marcas")
    brand_display = brands.nlargest(15, "configuracoes").rename(columns={"make": "Marca EPA", "configuracoes": "Configurações", "modelos": "Modelos", "segmentos": "Segmentos", "ano_inicial": "Primeiro ano", "ano_final": "Último ano", "mpg_medio": "MPG/MPGe", "co2_medio_g_milha": "CO₂ (g/mi)", "participacao_eletrificada_pct": "Mix eletrificado (%)"})[["Marca EPA", "Configurações", "Modelos", "Segmentos", "Último ano", "MPG/MPGe", "CO₂ (g/mi)", "Mix eletrificado (%)"]]
    st.dataframe(brand_display.style.format({"Configurações": "{:,.0f}", "Modelos": "{:,.0f}", "Segmentos": "{:,.0f}", "Último ano": "{:.0f}", "MPG/MPGe": "{:.1f}", "CO₂ (g/mi)": "{:.0f}", "Mix eletrificado (%)": "{:.1f}%"}), use_container_width=True, hide_index=True)
    with st.expander("Registro temporal de marcas EPA"):
        registry_display = registry.rename(columns={"make": "Marca EPA", "configuracoes": "Configurações", "modelos": "Modelos", "ano_inicial": "Primeiro ano", "ano_final": "Último ano", "presenca_no_snapshot": "Presença temporal"})
        st.dataframe(registry_display.style.format({"Configurações": "{:,.0f}", "Modelos": "{:,.0f}", "Primeiro ano": "{:.0f}", "Último ano": "{:.0f}"}), use_container_width=True, hide_index=True, height=420)
        st.caption("Os nomes são valores literais do campo `make` da EPA. O status temporal não indica atividade comercial, propriedade ou participação de mercado.")

with tab_energy:
    st.markdown("### Energia, combustível e custo de uso")
    latest_map = {row["energia"]: row for _, row in price_latest.iterrows()}
    ecols = st.columns(4)
    gasoline = latest_map.get("Gasolina regular")
    diesel = latest_map.get("Diesel")
    electricity = latest_map.get("Eletricidade")
    ecols[0].metric("Gasolina regular", fmt_usd(gasoline["preco"], 3) + "/gal", gasoline["data"].strftime("%m/%Y"))
    ecols[1].metric("Diesel", fmt_usd(diesel["preco"], 3) + "/gal", diesel["data"].strftime("%m/%Y"))
    ecols[2].metric("Eletricidade", fmt_usd(electricity["preco"], 3) + "/kWh", electricity["data"].strftime("%m/%Y"))
    comparable_count = int(filtered["custo_energia_100mi_usd"].notna().sum())
    ecols[3].metric("Configurações comparáveis", fmt_int(comparable_count), "Gasolina, diesel e BEV")
    st.markdown('<div class="note"><strong>Unidades e escopo.</strong> Gasolina e diesel usam séries nacionais em US$/galão. Elétricos a bateria usam preço médio nacional em US$/kWh e o consumo combinado `combE` da EPA. Híbridos plug-in e combustíveis sem série harmonizada permanecem fora do cálculo por 100 milhas para não introduzir premissas artificiais.</div>', unsafe_allow_html=True)
    price_col, cost_col = st.columns(2)
    with price_col:
        st.plotly_chart(price_index_chart(price_index), use_container_width=True, config={"displaylogo": False}, key="energy_price_index")
    with cost_col:
        st.plotly_chart(energy_cost_chart(energy_by_source), use_container_width=True, config={"displaylogo": False}, key="energy_cost_100mi")
    st.markdown("#### Estrutura por fonte de energia")
    energy_display = energy_by_source.rename(columns={"fonte_energia": "Fonte", "configuracoes": "Configurações", "marcas": "Marcas", "modelos": "Modelos", "eficiencia_mediana": "Eficiência mediana (MPG/MPGe)", "co2_mediano_g_milha": "CO₂ mediano (g/mi)", "custo_epa_anual_mediano_usd": "Custo EPA anual mediano (US$)", "custo_energia_100mi_mediano_usd": "Energia por 100 mi (US$)"})
    st.dataframe(energy_display.style.format({"Configurações": "{:,.0f}", "Marcas": "{:,.0f}", "Modelos": "{:,.0f}", "Eficiência mediana (MPG/MPGe)": "{:.1f}", "CO₂ mediano (g/mi)": "{:.0f}", "Custo EPA anual mediano (US$)": "US$ {:,.0f}", "Energia por 100 mi (US$)": "US$ {:.2f}"}), use_container_width=True, hide_index=True)
    corr_col, pairs_col = st.columns([1.15, 0.85])
    with corr_col:
        st.plotly_chart(correlation_chart(correlations), use_container_width=True, config={"displaylogo": False}, key="energy_correlation")
    with pairs_col:
        st.markdown("#### Associações mais fortes")
        pair_display = strong_pairs.rename(columns={"indicador_a": "Indicador A", "indicador_b": "Indicador B", "rho_spearman": "ρ Spearman", "n": "Observações válidas"})
        st.dataframe(pair_display.style.format({"ρ Spearman": "{:.2f}", "Observações válidas": "{:,.0f}"}), use_container_width=True, hide_index=True, height=360)
        st.caption("ρ de Spearman mede associação monotônica no recorte filtrado. Não implica causalidade; os pares usam somente observações com ambos os campos disponíveis.")
    st.markdown("#### Comparação controlada de configurações")
    comparison_source = filtered.dropna(subset=["comb08"]).copy()
    comparison_source["opcao"] = comparison_source["make"] + " · " + comparison_source["model"] + " · " + comparison_source["year"].astype(int).astype(str) + " · " + comparison_source["fonte_energia"]
    selected_options = st.multiselect("Selecione até quatro configurações", options=comparison_source["opcao"].drop_duplicates().sort_values().tolist(), max_selections=4, placeholder="Escolha configurações para comparar")
    if selected_options:
        selected_rows = comparison_source[comparison_source["opcao"].isin(selected_options)].sort_values(["opcao", "id"]).drop_duplicates("opcao")
        comparison = selected_rows.rename(columns={"make": "Marca", "model": "Modelo", "year": "Ano", "fonte_energia": "Energia", "comb08": "MPG/MPGe", "combE": "Consumo elétrico combinado", "custo_energia_100mi_usd": "Energia por 100 mi (US$)", "co2_valido": "CO₂ (g/mi)", "custo_anual_valido": "Custo EPA anual (US$)"})[["Marca", "Modelo", "Ano", "Energia", "MPG/MPGe", "Consumo elétrico combinado", "Energia por 100 mi (US$)", "CO₂ (g/mi)", "Custo EPA anual (US$)"]]
        st.dataframe(comparison.style.format({"Ano": "{:.0f}", "MPG/MPGe": "{:.1f}", "Consumo elétrico combinado": "{:.1f}", "Energia por 100 mi (US$)": "US$ {:.2f}", "CO₂ (g/mi)": "{:.0f}", "Custo EPA anual (US$)": "US$ {:,.0f}"}), use_container_width=True, hide_index=True)
    else:
        st.caption("A comparação foi limitada a quatro configurações para manter leitura direta, como em ferramentas públicas de comparação de veículos.")

with tab_market:
    st.markdown("### Mercado agregado, validação temporal e incerteza")
    mcols = st.columns(4)
    mcols[0].metric("Modelo selecionado", winner)
    mcols[1].metric("MAPE médio", f"{summary.iloc[0]['mape_medio']:.2f}%")
    mcols[2].metric("MAE médio", f"{summary_display.iloc[0]['mae_medio']:.3f} mi SAAR")
    mcols[3].metric("Horizonte", f"{horizon} meses")
    hist_col, test_col = st.columns(2)
    with hist_col:
        st.plotly_chart(history_chart(history), use_container_width=True, config={"displaylogo": False}, key="market_history")
    with test_col:
        st.plotly_chart(backtest_chart(summary, winner), use_container_width=True, config={"displaylogo": False}, key="market_backtest")
    st.dataframe(summary_display.style.format({"mape_medio": "{:.2f}%", "mape_desvio": "{:.2f} p.p.", "mae_medio": "{:.3f}", "rmse_medio": "{:.3f}"}), use_container_width=True, hide_index=True)
    with st.expander("Diagnóstico residual e decomposição"):
        diag_left, diag_right = st.columns(2)
        with diag_left:
            st.plotly_chart(residual_chart(backtest["residuals"]), use_container_width=True, config={"displaylogo": False}, key="market_residuals")
        with diag_right:
            st.plotly_chart(acf_chart(backtest["residual_acf"]), use_container_width=True, config={"displaylogo": False}, key="market_acf")
        st.dataframe(backtest["ljung_box"].rename(columns={"lb_stat": "Estatística Ljung-Box", "lb_pvalue": "p-valor"}).style.format({"Estatística Ljung-Box": "{:.3f}", "p-valor": "{:.4f}"}), use_container_width=True, hide_index=True)

with tab_planning:
    st.markdown("### Capacidade, estoque e nível de serviço")
    pc = st.columns(4)
    pc[0].metric("Demanda de referência", fmt_int(base_scenario["Demanda total (veículos)"]))
    pc[1].metric("Produção recomendada", fmt_int(base_scenario["Produção total (veículos)"]))
    pc[2].metric("Backlog final", fmt_int(base_scenario["Demanda pendente final"]))
    pc[3].metric("Utilização média", fmt_pct(base_scenario["Utilização média (%)"]))
    st.plotly_chart(production_chart(plan, int(capacity)), use_container_width=True, config={"displaylogo": False}, key="planning_production")
    left, right = st.columns([1.05, 0.95])
    with left:
        st.plotly_chart(sensitivity_chart(production["sensitivity"]), use_container_width=True, config={"displaylogo": False}, key="planning_sensitivity")
    with right:
        scenario_display = scenarios[["Cenário", "Demanda total (veículos)", "Produção total (veículos)", "Utilização média (%)", "Demanda pendente final", "Custo total (US$)"]]
        st.dataframe(scenario_display.style.format({"Demanda total (veículos)": "{:,.0f}", "Produção total (veículos)": "{:,.0f}", "Utilização média (%)": "{:.1f}%", "Demanda pendente final": "{:,.0f}", "Custo total (US$)": "US$ {:,.0f}"}), use_container_width=True, hide_index=True, height=360)
    with st.expander("Plano mensal e exportação"):
        plan_display = plan.rename(columns={"data": "Data", "demanda_planejada_veiculos": "Demanda", "producao_recomendada": "Produção", "estoque_final": "Estoque final", "demanda_pendente": "Pendente", "utilizacao_capacidade_pct": "Utilização (%)"})[["Data", "Demanda", "Produção", "Estoque final", "Pendente", "Utilização (%)"]]
        st.dataframe(plan_display.style.format({"Demanda": "{:,.0f}", "Produção": "{:,.0f}", "Estoque final": "{:,.0f}", "Pendente": "{:,.0f}", "Utilização (%)": "{:.1f}%"}), use_container_width=True, hide_index=True)
        st.download_button("Exportar plano em CSV", plan_display.to_csv(index=False).encode("utf-8"), "plano_operacional.csv", "text/csv")

with tab_method:
    st.markdown("### Fontes, cobertura e limites")
    source_table = pd.DataFrame(
        {
            "Fonte": ["FRED — TOTALSA", "EPA / FuelEconomy.gov", "EIA / FRED — energia"],
            "Cobertura": ["Mercado agregado mensal de veículos leves nos EUA.", f"{fmt_int(metadata['observacoes'])} configurações, {metadata['ano_inicial']}–{metadata['ano_final']}, por marca, modelo, classe, combustível, eficiência e emissões.", "Gasolina e diesel nacionais semanais, consolidados mensalmente; eletricidade média urbana mensal."],
            "Uso": ["Previsão e cenário de demanda.", "Portfólio, tecnologia, eficiência e emissões.", "Contexto de preço energético e custo de referência por 100 milhas."],
        }
    )
    st.dataframe(source_table, use_container_width=True, hide_index=True)
    st.markdown("### Fórmulas e interpretação")
    st.latex(r"Custo_{100mi}^{gas/diesel} = \frac{Preço\; (US\$/gal)}{MPG} \times 100")
    st.latex(r"Custo_{100mi}^{BEV} = combE\; (kWh/100mi) \times Preço\; (US\$/kWh)")
    st.markdown("A correlação usa Spearman para resumir associações monotônicas entre atributos comparáveis no recorte filtrado. Ela não substitui análise causal, nem transforma o campo `make` em participação de mercado. Preços de energia são nacionais e podem diferir de preços regionais, tarifários ou contratuais.")
    st.markdown("### Documentação disponível")
    st.markdown("[Auditoria do catálogo EPA](docs/AUDITORIA_CATALOGO_EPA.md) · [Pesquisa de referências e dados](docs/PESQUISA_REFERENCIAS_E_DADOS.md) · [Arquitetura refinada](docs/ARQUITETURA_DE_INFORMACAO_REFINADA.md) · [Proveniência das fontes](data/SOURCES.md)")
    st.markdown("### Referências")
    st.markdown(f"[1] [FRED — Total Vehicle Sales]({FRED_SERIES_URL})  \n[2] [EPA — Download Fuel Economy Data]({EPA_DOWNLOAD_PAGE})  \n[3] [EIA — Gasoline and Diesel Fuel Update](https://www.eia.gov/petroleum/gasdiesel/)  \n[4] [FRED / BLS — Electricity per Kilowatt-Hour](https://fred.stlouisfed.org/series/APU000072610)  \n[5] [AFDC — Alternative Fuel Price Report](https://afdc.energy.gov/fuels/prices.html)")

st.markdown('<div class="footer">QUANT AUTOMOTIVE INTELLIGENCE · Mercado, produto, energia e decisão operacional com fontes públicas rastreáveis</div>', unsafe_allow_html=True)
