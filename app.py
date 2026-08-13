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

analysis_module = importlib.reload(analysis_module)
FRED_SERIES_URL = analysis_module.FRED_SERIES_URL
run_full_analysis = analysis_module.run_full_analysis


st.set_page_config(
    page_title="Quant Automotive Planning",
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
MUTED = "#667085"
GRID = "#E7ECF3"

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
        .block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1500px; }}
        .hero {{ background: linear-gradient(110deg, #14213D 0%, #1F4E79 68%, #2F75B5 100%); border-radius: 18px; padding: 34px 40px 31px 40px; color: white; margin-bottom: 23px; box-shadow: 0 12px 28px rgba(20,33,61,.14); }}
        .hero .eyebrow {{ text-transform: uppercase; letter-spacing: .16em; font-size: .72rem; font-weight: 700; opacity: .78; margin-bottom: 9px; }}
        .hero h1 {{ color: white; font-size: 2.05rem; margin: 0; line-height: 1.13; }}
        .hero p {{ color: rgba(255,255,255,.82); font-size: 1rem; margin: 12px 0 0 0; max-width: 910px; line-height: 1.55; }}
        .section-kicker {{ color: var(--quant-orange); text-transform: uppercase; letter-spacing: .13em; font-size: .72rem; font-weight: 700; margin: 20px 0 5px 0; }}
        .section-title {{ font-family: 'Space Grotesk', sans-serif; color: var(--quant-navy); font-size: 1.42rem; font-weight: 700; margin-bottom: 8px; }}
        .insight {{ background: #FFFFFF; border: 1px solid #E4E9F0; border-left: 4px solid var(--quant-orange); border-radius: 10px; padding: 17px 19px; margin: 10px 0 18px 0; color: #344054; line-height: 1.55; }}
        .method-card {{ background: #FFFFFF; border: 1px solid #E4E9F0; border-radius: 13px; padding: 17px 19px; min-height: 135px; box-shadow: 0 5px 14px rgba(20,33,61,.035); }}
        .method-card .step {{ color: var(--quant-orange); font-size: .7rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }}
        .method-card strong {{ display: block; color: var(--quant-navy); font-family: 'Space Grotesk', sans-serif; font-size: 1.02rem; margin: 6px 0; }}
        .method-card span {{ color: #667085; font-size: .88rem; line-height: 1.4; }}
        .source-note {{ font-size: .79rem; color: #667085; margin-top: 4px; }}
        .small-note {{ color: #667085; font-size: .84rem; line-height: 1.5; }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 8px; border-bottom: 1px solid #DCE2EA; }}
        .stTabs [data-baseweb="tab"] {{ height: 47px; padding: 0 15px; font-weight: 600; color: #667085; }}
        .stTabs [aria-selected="true"] {{ color: var(--quant-navy); border-bottom-color: var(--quant-orange); }}
        div[data-testid="stMetric"] {{ background: #FFFFFF; border: 1px solid #E4E9F0; border-radius: 12px; padding: 15px 16px; box-shadow: 0 4px 12px rgba(20,33,61,.03); }}
        div[data-testid="stMetricLabel"] {{ color: #667085; }}
        div[data-testid="stMetricValue"] {{ color: var(--quant-navy); font-family: 'Space Grotesk', sans-serif; }}
        .footer {{ color: #98A2B3; border-top: 1px solid #E4E9F0; padding-top: 16px; margin-top: 34px; font-size: .78rem; }}
        .quant-tag {{ display: inline-block; background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.18); border-radius: 999px; padding: 5px 10px; margin-top: 17px; font-size: .74rem; letter-spacing: .03em; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value: float) -> str:
    return f"US$ {value:,.0f}".replace(",", ".")


def integer(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def percent(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")


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
    fig.update_traces(line={"color": BLUE, "width": 2.3}, name="TOTALSA")
    fig.update_layout(title="Série histórica de vendas totais de veículos")
    return chart_layout(fig, 420)


def stl_chart(stl: pd.DataFrame) -> go.Figure:
    labels = [("observada", "Série observada", BLUE), ("tendencia", "Tendência", ORANGE), ("sazonalidade", "Sazonalidade", TEAL), ("residuo", "Resíduo", "#667085")]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.055, subplot_titles=[label[1] for label in labels])
    for row, (column, _, color) in enumerate(labels, start=1):
        fig.add_trace(go.Scatter(x=stl["data"], y=stl[column], mode="lines", line={"color": color, "width": 1.7}, showlegend=False), row=row, col=1)
    fig.update_layout(title="Decomposição STL: observado, tendência, sazonalidade e resíduo", height=760, margin={"l": 12, "r": 18, "t": 66, "b": 15}, template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", font={"family": "DM Sans, sans-serif", "color": PRIMARY})
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    return fig


def seasonal_chart(profile: pd.DataFrame) -> go.Figure:
    fig = px.bar(profile, x="nome_mes", y="vendas_saar_milhoes", labels={"nome_mes": "Mês", "vendas_saar_milhoes": "Média de milhões SAAR"}, title="Perfil médio de sazonalidade")
    fig.update_traces(marker_color=TEAL)
    return chart_layout(fig, 360)


def yoy_chart(data: pd.DataFrame) -> go.Figure:
    recent = data.tail(72).dropna(subset=["variacao_anual_pct"])
    fig = px.bar(recent, x="data", y="variacao_anual_pct", labels={"data": "Data", "variacao_anual_pct": "YoY (%)"}, title="Variação anual da série")
    fig.update_traces(marker_color=BLUE)
    fig.add_hline(y=0, line_color=PRIMARY, line_width=1)
    return chart_layout(fig, 360)


def acf_chart(values: pd.DataFrame, column: str, title: str, color: str) -> go.Figure:
    plot_data = values.iloc[:37]
    fig = px.bar(plot_data, x="lag", y=column, labels={"lag": "Defasagem", column: "Correlação"}, title=title)
    fig.update_traces(marker_color=color)
    fig.add_hline(y=0, line_color=PRIMARY, line_width=1)
    return chart_layout(fig, 350)


def backtest_chart(summary: pd.DataFrame, winner: str) -> go.Figure:
    colors = [ORANGE if model == winner else "#B8C2D1" for model in summary["modelo"]]
    fig = go.Figure(go.Bar(x=summary["modelo"], y=summary["mape_medio"], error_y={"type": "data", "array": summary["mape_desvio"].fillna(0)}, marker_color=colors, text=[f"{value:.2f}%" for value in summary["mape_medio"]], textposition="outside"))
    fig.update_layout(title="MAPE médio por modelo, com desvio-padrão entre dobras", yaxis_title="MAPE (%)", xaxis_title="Modelo")
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
    fig.add_trace(go.Scatter(x=forecast["data"], y=forecast["cenario_conservador"], mode="lines", name="Cenário conservador (p10)", line={"color": "rgba(232,117,50,.25)", "width": 1}))
    fig.add_trace(go.Scatter(x=forecast["data"], y=forecast["cenario_otimista"], mode="lines", name="Faixa p10–p90", fill="tonexty", fillcolor="rgba(232,117,50,.18)", line={"color": "rgba(232,117,50,.25)", "width": 1}))
    fig.add_trace(go.Scatter(x=forecast["data"], y=forecast["cenario_base"], mode="lines+markers", name="Cenário base", line={"color": ORANGE, "width": 2.6}))
    fig.add_vline(x=data["data"].max(), line_dash="dot", line_color=PRIMARY, annotation_text="Corte histórico", annotation_position="top left")
    fig.update_layout(title=f"Previsão dos próximos {len(forecast)} meses — modelo selecionado: {winner}", yaxis_title="Milhões de unidades SAAR", xaxis_title="Data")
    return chart_layout(fig, 500)


def production_chart(plan: pd.DataFrame, capacity: int) -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.13, subplot_titles=["Demanda versus produção recomendada", "Estoque final e demanda pendente"])
    fig.add_trace(go.Bar(x=plan["data"], y=plan["demanda_planejada_veiculos"], name="Demanda planejada", marker_color="#A9C7E3"), row=1, col=1)
    fig.add_trace(go.Scatter(x=plan["data"], y=plan["producao_recomendada"], name="Produção recomendada", mode="lines+markers", line={"color": ORANGE, "width": 2.4}), row=1, col=1)
    fig.add_hline(y=capacity, line_dash="dash", line_color=PRIMARY, annotation_text="Capacidade", row=1, col=1)
    fig.add_trace(go.Scatter(x=plan["data"], y=plan["estoque_final"], name="Estoque final", mode="lines+markers", line={"color": BLUE, "width": 2}), row=2, col=1)
    fig.add_trace(go.Scatter(x=plan["data"], y=plan["demanda_pendente"], name="Demanda pendente", mode="lines+markers", line={"color": RED, "width": 2, "dash": "dot"}), row=2, col=1)
    fig.update_yaxes(title_text="Veículos", row=1, col=1)
    fig.update_yaxes(title_text="Veículos", row=2, col=1)
    fig.update_layout(title="Plano de produção — cenário base", height=700)
    return chart_layout(fig, 700)


def sensitivity_chart(sensitivity: pd.DataFrame) -> go.Figure:
    display_data = sensitivity.copy()
    display_data.index = [integer(index) for index in display_data.index]
    display_data.columns = [f"{float(column):.0%}" for column in display_data.columns]
    fig = px.imshow(display_data, text_auto=".0f", aspect="auto", color_continuous_scale="YlOrRd", labels={"x": "Participação hipotética", "y": "Capacidade mensal", "color": "Backlog acumulado"}, title="Sensibilidade do backlog acumulado")
    fig.update_traces(textfont={"size": 12})
    return chart_layout(fig, 410)


def load_analysis(
    n_folds: int,
    test_size: int,
    horizon: int,
    bootstrap_replicas: int,
    seed: int,
    participation: float,
    capacity: int,
    initial_inventory: int,
    production_cost: float,
    inventory_cost: float,
    backlog_cost: float,
) -> dict:
    return run_full_analysis(
        fallback_path=ROOT / "data" / "TOTALSA_snapshot.csv",
        n_folds=n_folds,
        test_size=test_size,
        horizon=horizon,
        bootstrap_replicas=bootstrap_replicas,
        seed=seed,
        participation=participation,
        capacity=capacity,
        initial_inventory=initial_inventory,
        production_cost=production_cost,
        inventory_cost=inventory_cost,
        backlog_cost=backlog_cost,
    )


with st.sidebar:
    st.markdown("## QUANT")
    st.caption("Automotive Planning Lab")
    st.markdown("---")
    st.markdown("### Parâmetros do estudo")
    n_folds = st.slider("Dobras do backtest", min_value=2, max_value=8, value=4, help="Número de janelas temporais expansivas.")
    test_size = st.slider("Meses por dobra", min_value=3, max_value=12, value=6, help="Tamanho do período de teste em cada janela.")
    horizon = st.slider("Horizonte de previsão", min_value=3, max_value=12, value=6, help="Meses futuros para o planejamento.")
    bootstrap_replicas = st.select_slider("Réplicas de bootstrap", options=[500, 1000, 2000, 5000], value=2000)
    seed = st.number_input("Semente aleatória", min_value=0, max_value=9999, value=42, step=1)
    st.markdown("### Premissas operacionais")
    participation_pct = st.slider("Participação de mercado hipotética", min_value=2, max_value=20, value=8, step=1, format="%d%%")
    participation = participation_pct / 100
    capacity = st.number_input("Capacidade mensal (veículos)", min_value=10_000, max_value=300_000, value=110_000, step=5_000)
    initial_inventory = st.number_input("Estoque inicial (veículos)", min_value=0, max_value=100_000, value=15_000, step=1_000)
    production_cost = st.number_input("Custo de produção (US$/veículo)", min_value=0, max_value=100_000, value=25_000, step=500)
    inventory_cost = st.number_input("Custo de estoque (US$/veículo/mês)", min_value=0, max_value=10_000, value=350, step=50)
    backlog_cost = st.number_input("Custo de ruptura (US$/veículo)", min_value=0, max_value=200_000, value=45_000, step=500)
    st.markdown("---")
    st.markdown(f"[Fonte oficial: FRED — TOTALSA]({FRED_SERIES_URL})")
    st.caption("A aplicação tenta consultar a fonte online e utiliza o snapshot versionado em caso de indisponibilidade.")

try:
    with st.spinner("Executando diagnóstico, backtest, previsão e otimização..."):
        result = load_analysis(n_folds, test_size, horizon, bootstrap_replicas, int(seed), participation, int(capacity), int(initial_inventory), float(production_cost), float(inventory_cost), float(backlog_cost))
except Exception as error:
    st.error(f"Não foi possível executar a análise: {error}")
    st.info("Verifique as dependências instaladas e a disponibilidade do snapshot em data/TOTALSA_snapshot.csv.")
    st.stop()


data = result["data"]
quality = result["quality"]
diagnostics = result["diagnostics"]
backtest = result["backtest"]
forecast = result["forecast"]
production = result["production"]
plan = production["plan"]
scenarios = production["scenarios"]
summary = backtest["summary"]
winner = backtest["winner"]
base_row = scenarios.loc[scenarios["Cenário"] == "Base"].iloc[0]

st.markdown(
    f"""
    <div class="hero">
        <div class="eyebrow">Quantitative decision system · automotive</div>
        <h1>Previsão de demanda e planejamento de produção</h1>
        <p>Um fluxo quantitativo completo que conecta dados públicos, validação temporal, incerteza empírica e otimização operacional para apoiar decisões de capacidade.</p>
        <div class="quant-tag">CASO DIDÁTICO · NÃO REPRESENTA DADOS OU DECISÕES INTERNAS DE UMA MONTADORA</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-kicker">Visão executiva</div><div class="section-title">Resumo para decisão</div>', unsafe_allow_html=True)
metric_columns = st.columns(5)
metric_columns[0].metric("Modelo selecionado", winner)
metric_columns[1].metric("MAPE médio", f"{summary.iloc[0]['mape_medio']:.2f}%")
metric_columns[2].metric("Demanda base", f"{integer(base_row['Demanda total (veículos)'])} veículos")
metric_columns[3].metric("Utilização média", percent(base_row["Utilização média (%)"]))
metric_columns[4].metric("Backlog final", f"{integer(base_row['Demanda pendente final'])} veículos")

st.markdown(
    f"""
    <div class="insight"><strong>Leitura executiva.</strong> O modelo <strong>{winner}</strong> foi selecionado pelo menor MAPE médio em {n_folds} dobras de validação walk-forward. A decisão de produção é apresentada no cenário base e testada contra cenários conservador/otimista, além de uma grade de capacidade e participação de mercado. O estudo não trata a previsão como um número certo: a faixa p10–p90 deriva do bootstrap dos resíduos observados fora da amostra.</div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-kicker">Raciocínio quantitativo</div><div class="section-title">Do dado público à decisão operacional</div>', unsafe_allow_html=True)
method_columns = st.columns(5)
method_steps = [("01", "Qualidade", "Checagem de lacunas, duplicidades e outliers."), ("02", "Diagnóstico", "ADF, STL, ACF e PACF para ler a série."), ("03", "Validação", "Backtest temporal sem vazamento do futuro."), ("04", "Incerteza", "Bootstrap dos erros para cenários empíricos."), ("05", "Decisão", "Plano linear sob capacidade e custos.")]
for column, (step, title, description) in zip(method_columns, method_steps):
    column.markdown(f'<div class="method-card"><div class="step">Etapa {step}</div><strong>{title}</strong><span>{description}</span></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
tab_exec, tab_data, tab_model, tab_forecast, tab_production, tab_method = st.tabs(["Visão executiva", "Dados & diagnóstico", "Modelos & validação", "Previsão & incerteza", "Produção & sensibilidade", "Metodologia"])

with tab_exec:
    left, right = st.columns([1.35, 1])
    with left:
        st.plotly_chart(history_chart(data), use_container_width=True, config={"displaylogo": False})
    with right:
        st.markdown("#### Mensagens que sustentam a análise")
        st.markdown("A série é uma referência pública de mercado; a aproximação mensal é usada apenas para leitura operacional, enquanto o modelo trabalha sobre a unidade SAAR original.")
        st.markdown("A seleção não depende de um único corte temporal. Cada modelo é reestimado em múltiplas janelas, sempre usando apenas dados anteriores ao período testado.")
        st.markdown("A otimização não devolve apenas produção: ela explicita estoque, demanda pendente, utilização de capacidade e custo ilustrativo, permitindo discutir trade-offs.")
        st.markdown(f'<p class="source-note">Fonte consultada: {result["source_label"]}. Período: {data["data"].min():%m/%Y} a {data["data"].max():%m/%Y}. {len(data):,} observações.</p>', unsafe_allow_html=True)
    st.markdown("#### Como defender este projeto em entrevista")
    interview = pd.DataFrame({"Mensagem": ["A validação usa múltiplas dobras walk-forward.", "Complexidade só é mantida se reduzir erro fora da amostra.", "A incerteza vem de resíduos reais do backtest, sem normalidade imposta.", "A decisão é avaliada em três cenários e numa matriz de sensibilidade.", "O próximo passo real seria granularidade por modelo, planta, região e fornecedor."], "Como explicar": ["Um único split pode ser sorte ou azar; as janelas mostram a consistência da conclusão.", "A referência sazonal funciona como benchmark contra o qual métodos mais sofisticados precisam provar valor.", "Reamostrar erros observados comunica risco de modo mais defensável do que usar apenas ± desvios-padrão.", "Não apresento um número único como verdade; mostro como capacidade e participação alteram o backlog.", "Com dados internos, eu substituiria hipóteses didáticas por restrições industriais calibradas."]})
    st.dataframe(interview, use_container_width=True, hide_index=True)

with tab_data:
    st.markdown("### Qualidade da base")
    quality_columns = st.columns(6)
    quality_columns[0].metric("Observações", integer(quality["observacoes"]))
    quality_columns[1].metric("Duplicidades", integer(quality["duplicidades_brutas"]))
    quality_columns[2].metric("Ausentes", integer(quality["valores_ausentes"]))
    quality_columns[3].metric("Intervalos irregulares", integer(quality["intervalos_irregulares"]))
    quality_columns[4].metric("Outliers IQR", integer(quality["outliers_iqr"]))
    quality_columns[5].metric("Fonte", "Online" if "online" in result["source_label"].lower() else "Snapshot")
    st.markdown("Outliers são apresentados como diagnóstico, sem remoção automática. Essa decisão evita apagar choques econômicos potencialmente reais.")
    if len(quality["outliers"]) > 0:
        st.dataframe(quality["outliers"][["data", "vendas_saar_milhoes"]], use_container_width=True, hide_index=True)
    else:
        st.success("Nenhuma observação fora dos limites IQR foi identificada.")
    st.markdown("### Decomposição e sazonalidade")
    st.plotly_chart(stl_chart(diagnostics["stl"]), use_container_width=True, config={"displaylogo": False})
    season_left, season_right = st.columns(2)
    with season_left:
        st.plotly_chart(seasonal_chart(diagnostics["seasonal_profile"]), use_container_width=True, config={"displaylogo": False})
    with season_right:
        st.plotly_chart(yoy_chart(data), use_container_width=True, config={"displaylogo": False})
    st.markdown("### ADF, ACF e PACF")
    adf_table = pd.DataFrame({"Teste": ["ADF em nível", "ADF na primeira diferença"], "Estatística": [diagnostics["adf_level"]["statistic"], diagnostics["adf_diff"]["statistic"]], "p-valor": [diagnostics["adf_level"]["pvalue"], diagnostics["adf_diff"]["pvalue"]]})
    st.dataframe(adf_table.style.format({"Estatística": "{:.3f}", "p-valor": "{:.4f}"}), use_container_width=True, hide_index=True)
    acf_left, acf_right = st.columns(2)
    with acf_left:
        st.plotly_chart(acf_chart(diagnostics["acf"], "acf", "Função de autocorrelação (ACF)", BLUE), use_container_width=True, config={"displaylogo": False})
    with acf_right:
        st.plotly_chart(acf_chart(diagnostics["pacf"], "pacf", "Autocorrelação parcial (PACF)", ORANGE), use_container_width=True, config={"displaylogo": False})

with tab_model:
    st.markdown("### Comparação fora da amostra")
    st.plotly_chart(backtest_chart(summary, winner), use_container_width=True, config={"displaylogo": False})
    st.dataframe(summary.style.format({"mape_medio": "{:.2f}%", "mape_desvio": "{:.2f} p.p."}), use_container_width=True, hide_index=True)
    st.markdown("A escolha é direcional: o vencedor é o modelo com menor MAPE médio. O desvio-padrão entre dobras explicita a estabilidade do resultado.")
    with st.expander("Ver desempenho por dobra"):
        st.dataframe(backtest["results"].style.format({"MAE (milhões SAAR)": "{:.3f}", "RMSE (milhões SAAR)": "{:.3f}", "MAPE (%)": "{:.2f}%"}), use_container_width=True, hide_index=True)
    st.markdown("### Diagnóstico dos resíduos do vencedor")
    residue_left, residue_right = st.columns(2)
    with residue_left:
        st.plotly_chart(residual_chart(backtest["residuals"]), use_container_width=True, config={"displaylogo": False})
    with residue_right:
        st.plotly_chart(acf_chart(backtest["residual_acf"], "acf", "ACF dos resíduos fora da amostra", TEAL), use_container_width=True, config={"displaylogo": False})
    lb_table = backtest["ljung_box"].rename(columns={"lb_stat": "Estatística Ljung-Box", "lb_pvalue": "p-valor"})
    st.dataframe(lb_table.style.format({"Estatística Ljung-Box": "{:.3f}", "p-valor": "{:.4f}"}), use_container_width=True, hide_index=True)
    st.caption(f"Os resíduos agrupam {len(backtest['residuals'])} previsões fora da amostra. O teste de Ljung-Box é evidência complementar, não uma prova definitiva de ausência de autocorrelação.")

with tab_forecast:
    st.markdown("### Cenários de demanda")
    st.plotly_chart(forecast_chart(data, forecast, winner), use_container_width=True, config={"displaylogo": False})
    forecast_display = forecast.rename(columns={"data": "Data", "cenario_conservador": "Conservador — p10", "cenario_base": "Base", "cenario_otimista": "Otimista — p90", "demanda_mensal_base_milhoes": "Base mensal aproximada"})
    st.dataframe(forecast_display.style.format({"Conservador — p10": "{:.3f}", "Base": "{:.3f}", "Otimista — p90": "{:.3f}", "Base mensal aproximada": "{:.3f}"}), use_container_width=True, hide_index=True)
    csv_forecast = forecast_display.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar previsão em CSV", data=csv_forecast, file_name="previsao_demanda_automotiva.csv", mime="text/csv")
    st.markdown("### Como ler a incerteza")
    st.markdown("O cenário base é a previsão pontual do modelo vencedor reajustado com todo o histórico. Os limites conservador e otimista são os percentis 10 e 90 de simulações que reamostram os erros observados no backtest. Portanto, a faixa é empírica e não pressupõe que os erros sejam normais.")

with tab_production:
    st.markdown("### Plano recomendado — cenário base")
    production_columns = st.columns(4)
    production_columns[0].metric("Demanda total", f"{integer(base_row['Demanda total (veículos)'])} veículos")
    production_columns[1].metric("Produção total", f"{integer(base_row['Produção total (veículos)'])} veículos")
    production_columns[2].metric("Custo ilustrativo", money(base_row["Custo total (US$)"]))
    production_columns[3].metric("Backlog final", f"{integer(base_row['Demanda pendente final'])} veículos")
    st.plotly_chart(production_chart(plan, int(capacity)), use_container_width=True, config={"displaylogo": False})
    plan_display = plan.rename(columns={"data": "Data", "demanda_planejada_veiculos": "Demanda planejada", "producao_recomendada": "Produção recomendada", "estoque_final": "Estoque final", "demanda_pendente": "Demanda pendente", "utilizacao_capacidade_pct": "Utilização da capacidade (%)"})[["Data", "Demanda planejada", "Produção recomendada", "Estoque final", "Demanda pendente", "Utilização da capacidade (%)"]]
    st.dataframe(plan_display.style.format({"Demanda planejada": "{:,.0f}", "Produção recomendada": "{:,.0f}", "Estoque final": "{:,.0f}", "Demanda pendente": "{:,.0f}", "Utilização da capacidade (%)": "{:.1f}%"}), use_container_width=True, hide_index=True)
    st.download_button("Baixar plano de produção em CSV", data=plan_display.to_csv(index=False).encode("utf-8"), file_name="plano_producao_automotivo.csv", mime="text/csv")
    st.markdown("### Comparação entre cenários")
    st.dataframe(scenarios.style.format({"Demanda total (veículos)": "{:,.0f}", "Produção total (veículos)": "{:,.0f}", "Utilização média (%)": "{:.1f}%", "Demanda pendente final": "{:,.0f}", "Custo total (US$)": "US$ {:,.0f}"}), use_container_width=True, hide_index=True)
    st.markdown("### Sensibilidade da decisão")
    st.plotly_chart(sensitivity_chart(production["sensitivity"]), use_container_width=True, config={"displaylogo": False})
    st.markdown("Cada célula mostra o backlog acumulado ao longo do horizonte para uma combinação de capacidade mensal e participação de mercado. As duas variáveis são hipóteses didáticas editáveis no painel lateral.")

with tab_method:
    st.markdown("### Pergunta de negócio")
    st.markdown("Como transformar uma previsão mensal de vendas do mercado em um plano de produção que equilibre nível de serviço, estoque e restrição de capacidade — e como comunicar, de forma defensável, o quanto se pode confiar nessa previsão?")
    st.markdown("### Formulação da decisão")
    st.latex(r"D_t = round((SAAR_t / 12) \\times 1.000.000 \\times participação)")
    st.latex(r"min \\sum_t c_p P_t + c_i I_t + c_b B_t")
    st.latex(r"I_t - B_t = I_{t-1} - B_{t-1} + P_t - D_t, \\quad 0 \\le P_t \\le Capacidade")
    st.markdown("A função objetivo minimiza custo de produção, custo de estoque e penalidade de demanda não atendida. O custo de ruptura é configurado acima do custo de estoque para refletir uma prioridade didática de nível de serviço.")
    st.markdown("### Modelos e validação")
    st.markdown("A referência sazonal calcula a média histórica do mesmo mês. O Holt-Winters modela nível, tendência e sazonalidade anual. A regressão Ridge utiliza defasagens de 1 e 12 meses, tendência linear e variáveis indicadoras de mês, com previsão recursiva multi-passo. O backtest walk-forward reestima cada alternativa em uma janela expansiva e nunca embaralha os dados.")
    st.markdown("### Limites de interpretação")
    st.warning("Este é um caso didático para demonstrar raciocínio quantitativo aplicado. Participação, capacidade, estoque e custos não representam uma operação real. Uma implantação industrial exigiria dados por modelo, planta, região, fornecedores, lead times, mix e restrições de recursos.")
    st.markdown("### Referências")
    st.markdown(f"[1] [FRED — Total Vehicle Sales (TOTALSA)]({FRED_SERIES_URL})  \n[2] [Federal Reserve — Seasonal Factors for Motor Vehicle Sales](https://www.federalreserve.gov/releases/g17/mv_sales_sf.htm)  \n[3] [Bureau of Transportation Statistics — Auto Sales](https://catalog.data.gov/dataset/auto-sales)  \n[4] Cleveland et al. (1990), *STL: A Seasonal-Trend Decomposition Procedure Based on Loess*.  \n[5] Ljung & Box (1978), *On a Measure of Lack of Fit in Time Series Models*.  \n[6] Efron (1979), *Bootstrap Methods: Another Look at the Jackknife*.")
    st.markdown("Consulte também o arquivo `docs/ARQUITETURA_E_METODOLOGIA.md` para a descrição acadêmica completa, as equações e o diagrama do fluxo.")

st.markdown('<div class="footer">QUANT AUTOMOTIVE PLANNING · Projeto acadêmico e demonstrativo · Dados públicos FRED · Valores operacionais hipotéticos e editáveis</div>', unsafe_allow_html=True)
