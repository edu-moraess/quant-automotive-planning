# Relatório de Estado — Quant Automotive Intelligence & Planning

**Data de referência:** 14/08/2026  
**Repositório:** [edu-moraess/quant-automotive-planning](https://github.com/edu-moraess/quant-automotive-planning)  
**Commit HEAD:** `c5936bc`  
**Plataforma:** Streamlit Cloud (deploy público)

---

## 1. Visão Geral

O projeto transforma um notebook de planejamento quantitativo automotivo em uma plataforma analítica profissional com sete abas temáticas, dados reais de múltiplas fontes públicas e privadas, modelos de forecast probabilístico, otimização linear de produção e monitoramento regulatório de segurança veicular.

A arquitetura é modular, versionada e orientada a contratos de dados — cada fonte tem seu cliente dedicado, schema de validação, fallback local e rastreabilidade de proveniência.

---

## 2. Datasets Integrados

| Fonte | Tipo | Volume | Cobertura | Chave |
|---|---|---|---|---|
| **FRED TOTALSA** | Série mensal de vendas SAAR | 607 observações | 1976-01 a 2026-07 | Sim |
| **EPA FuelEconomy.gov** | Catálogo técnico de veículos | 50.242 configurações | 1984–2027 | Não |
| **EIA / BLS** | Preços de energia (gasolina, diesel, eletricidade) | 574 observações | Mensal | Sim |
| **NHTSA** | Recalls e reclamações de segurança | 1.343 eventos | 2023-08 a 2026-08 | Não |
| **News API** | Artigos sobre mercado automotivo | Atualização contínua | Configurável | Sim |

O catálogo EPA cobre **146 marcas** distintas com dados de eficiência (MPG/MPGe), emissões de CO₂ e classificação de tecnologia de propulsão. O FRED TOTALSA é a série-alvo de todos os modelos de forecast.

---

## 3. Arquitetura de Software

### 3.1 Estrutura de módulos

```
src/
├── analysis.py            # Motor de mercado: ingestão FRED, backtest, forecast
├── config.py              # Configuração centralizada: ForecastSettings, PlanningAssumptions
├── data_quality.py        # Validação de schema, detecção de anomalias
├── energy_intelligence.py # Correlação energia–vendas, OLS padronizado
├── forecast_model.py      # OLS Newey-West, walk-forward, coeficientes padronizados
├── ingestion.py           # Ingestão resiliente com retry, timeout e fallback
├── planning.py            # Otimização PuLP: produção, estoque, backlog
├── presentation.py        # Formatação temporal centralizada
├── scenarios.py           # Cenários explícitos: Downside/Base/Upside/Stress
├── vehicle_intelligence.py # Análise EPA: portfólio, segmentos, marcas
└── data/
    ├── api_health.py      # Health check das 4 fontes externas
    ├── contracts.py       # Contratos Pydantic: TimeWindow, NHTSATarget, SourcePayload
    ├── feature_builder.py # Orquestrador: FRED + EIA + News + NHTSA → feature store
    ├── feature_store.py   # Parquet particionado com manifesto operacional
    ├── settings.py        # FeatureSettings (chaves seguras), FeatureSourceConfig
    ├── temporal.py        # Higiene point-in-time, enforce_point_in_time
    └── sources/
        ├── base.py        # HTTP assíncrono: retry, cache, logging seguro
        ├── eia.py         # Cliente EIA v2
        ├── epa.py         # Leitor do snapshot EPA local
        ├── fred.py        # Cliente FRED com vintage cutoff
        ├── news.py        # Cliente News API com deduplicação
        └── nhtsa.py       # Cliente NHTSA: recalls + reclamações, índice de risco
```

**25 módulos Python** em `src/` — **11 arquivos de teste** em `tests/`.

### 3.2 Feature store

Parquet particionado por `source=X/month=YYYY-MM/[marca=X/modelo=X/ano_modelo=X/]data.parquet`. O manifesto `manifest.json` registra estado, cobertura, latência e mensagem de cada fonte após cada execução.

---

## 4. Modelos Analíticos

### 4.1 Forecast de vendas SAAR

Quatro candidatos avaliados em backtest walk-forward com métricas MAPE, sMAPE, WAPE, MASE e RMSE:

| Modelo | MAPE médio | Seleção |
|---|---|---|
| Ridge com defasagens | 3,97% | **Vencedor atual** |
| Referência sazonal | — | Baseline |
| Holt-Winters | — | Candidato |
| AutoReg sazonal | — | Candidato |

O modelo vencedor é selecionado automaticamente por score composto de ranking multi-métrica com penalidade de complexidade. Intervalos de confiança p10–p90 são gerados por bootstrap moving-block com 2.000 réplicas.

### 4.2 OLS Newey-West (v2)

Modelo econométrico com erros-padrão HAC para lidar com autocorrelação residual em séries mensais:

| Métrica | Valor atual | Meta | Status |
|---|---|---|---|
| MAPE médio | 3,04% | ≤ 3,0% | Próximo — melhora com séries macro |
| Durbin-Watson médio | 1,42 | ≥ 1,60 | Melhora ao popular o feature store |
| Cobertura p10–p90 | 83,3% | ≥ 75% | **Atingida** |
| Pinball Loss médio | 0,178 | — | Referência |

> **Nota:** O modelo atualmente usa apenas defasagens do target (y_lag1, y_lag2, y_lag12) porque o feature store ainda não foi populado com as séries macroeconômicas via API. Após a primeira execução do botão "Atualizar features" no Streamlit Cloud, os regressores FEDFUNDS, G18, UNRATE, CPIAUCSL, GASREG, UMCSENT, PAYEMS e INDPRO entrarão na matriz e o DW deve atingir ≥ 1,60.

### 4.3 Econometria de energia

OLS padronizado com preços de gasolina, diesel e eletricidade como regressores. Coeficientes padronizados permitem comparação direta de magnitude entre variáveis de escalas distintas.

### 4.4 Rede neural de eficiência (MLP)

Treinada sobre o catálogo EPA com features de tecnologia de propulsão, cilindrada, peso e ano-modelo. Métricas: **MAE = 4,33 MPG**, **R² = 0,947**. Usada para estimar eficiência de configurações hipotéticas e analisar a transição energética da frota.

### 4.5 Planejamento operacional

Otimização linear (PuLP/CBC) com variáveis de produção regular, produção extra, estoque e backlog. Resolve o plano ótimo para os cenários Downside, Base, Upside e Stress com participação de mercado configurável pelo usuário.

---

## 5. Camada de Features Gratuitas

### 5.1 Health check de APIs

Módulo `src/data/api_health.py` executa probes leves antes de qualquer ingestão:

| Fonte | Endpoint de probe | Chave | Timeout |
|---|---|---|---|
| FRED | `/fred/series/observations?series_id=TOTALSA&limit=1` | Sim | 12 s |
| EIA | `/v2/seriesid/PET.WRG0_EPM0_PTE_DPG.W?length=1` | Sim | 12 s |
| News API | `/v2/everything?q=car&pageSize=1` | Sim | 12 s |
| NHTSA | `/recalls/recallsByVehicle?make=TOYOTA&model=RAV4&modelYear=2024` | Não | 25 s |

O relatório é salvo em `data/feature_store/api_health.json` e exibido na sidebar com ícones 🟢/🟡/🔴.

### 5.2 Séries FRED configuradas (11 séries)

| Série | Descrição | Lag point-in-time |
|---|---|---|
| TOTALSA | Vendas SAAR mensais (target) | — |
| FEDFUNDS | Taxa de juros do Fed | t-1 |
| G18 | Taxa de financiamento auto 48 meses | t-1 |
| UNRATE | Taxa de desemprego | t-1 |
| CPIAUCSL | Índice de preços ao consumidor | t-1 |
| GASREG | Preço da gasolina regular | t-1 |
| UMCSENT | Índice de confiança do consumidor | t-1 |
| PAYEMS | Total de empregados não-agrícolas | t-1 |
| INDPRO | Produção industrial | t-1 |
| MORTGAGE30US | Taxa de hipoteca 30 anos | t-1 |
| RSAFS | Vendas no varejo de peças automotivas | t-1 |

### 5.3 Monitoramento NHTSA

Watchlist de 6 modelos 2024 monitorados continuamente:

| Veículo | Recalls | Reclamações |
|---|---|---|
| Ford Maverick 2024 | — | — |
| Chevrolet Silverado 1500 2024 | — | — |
| Toyota RAV4 2024 | — | — |
| Honda CR-V 2024 | — | — |
| Tesla Model 3 2024 | — | — |
| Hyundai IONIQ 5 2024 | — | — |

**Total materializado:** 1.343 eventos (29 recalls + 1.314 reclamações) · Cobertura: 2023-08 a 2026-08.

**Índice de risco:** `2 × recalls + 1 × reclamações` — métrica de triagem para priorização de monitoramento, não representa qualidade de marca ou risco financeiro.

---

## 6. Interface Streamlit

### 6.1 Abas

| Aba | Conteúdo principal |
|---|---|
| Resumo | KPIs de mercado, eficiência média da frota, alerta de transição energética |
| Portfólio | Análise EPA por marca/segmento/tecnologia, scorecard NHTSA |
| Mercado & Forecast | Série TOTALSA, backtest walk-forward, forecast p10–p90, drivers OLS NW |
| Energia & Combustível | Correlação energia–vendas, OLS padronizado, análise de sensibilidade |
| Modelos | Sumário técnico de todos os modelos: econometria, rede neural, OLS NW |
| Planejamento | Plano de produção ótimo, cenários, análise de capacidade |
| Cenários | Comparação explícita Downside/Base/Upside/Stress |

### 6.2 Sidebar

- **Formulário "Universo de produto":** filtros EPA por ano-modelo, marca, tecnologia e segmento
- **Formulário "Forecast e planejamento":** horizonte, dobras walk-forward, hipóteses operacionais
- **Expander "Camada de features gratuitas":** status das 4 APIs, data da última atualização, botão de atualização integrado ao Streamlit Cloud

### 6.3 Padrões de design

- Layout estritamente vertical — nenhum gráfico ou tabela lado a lado
- Paleta: PRIMARY=#14213D, BLUE=#1F4E79, ORANGE=#E87532, TEAL=#008A8A
- Fontes: DM Sans (corpo) + Space Grotesk (títulos e métricas)
- Controles Plotly (modebar): invisíveis até hover, posicionados verticalmente, transparentes

---

## 7. Qualidade de Código

| Critério | Status |
|---|---|
| Testes automatizados | **55 aprovados** (pytest) |
| Lint | **Limpo** (ruff check) |
| Formatação | **Conforme** (ruff format) |
| Credenciais em código | **Nenhuma** — lidas de st.secrets ou variáveis de ambiente |
| Dados simulados | **Nenhum** — apenas fontes públicas e APIs reais |
| Commits semânticos | feat / fix / docs / refactor / data |

---

## 8. Histórico de Commits Recentes

| Hash | Descrição |
|---|---|
| `c5936bc` | fix: corrigir health check do EIA e NHTSA |
| `7b71e99` | feat: botão de atualização do feature store integrado ao Streamlit Cloud |
| `40bfe75` | feat: health check de APIs, OLS Newey-West, drivers do forecast e séries macro FRED |
| `cebd6d3` | feat: integrar monitoramento NHTSA ao feature store |
| `a0d96ba` | docs: registrar ativação pendente da automação |
| `fd2a1c4` | feat: adicionar camada gratuita de features automotivas |

---

## 9. Pendências e Próximos Passos

### 9.1 Imediato — popular o feature store com séries macro

Após o deploy do commit `c5936bc` no Streamlit Cloud, clicar em **"Atualizar features (FRED · EIA · News · NHTSA)"** na sidebar. Isso vai:

1. Buscar FEDFUNDS, G18, UNRATE, CPIAUCSL, GASREG, UMCSENT, PAYEMS, INDPRO via FRED API
2. Enriquecer a matriz do OLS Newey-West com 8 regressores macroeconômicos
3. Elevar o Durbin-Watson para ≥ 1,60 e o MAPE para ≤ 3,0%
4. Exibir o gráfico de coeficientes padronizados com os drivers reais do forecast

### 9.2 Automação futura

O workflow `refresh-free-features.yml` está preparado em `/home/ubuntu/deliverables/` mas aguarda permissão `workflows` no token GitHub para ser publicado. Ele executa:

- **Diariamente:** News API + NHTSA (fontes sem custo de cota)
- **Mensalmente:** FRED + EIA (séries macro com atualização mensal)
- **Manual:** dispatch por modo (`fred`, `eia`, `news`, `nhtsa`, `all`)

### 9.3 Expansões possíveis

- **Modelo de demanda por marca:** requer dados de vendas por marca (Ward's Automotive, Wards Intelligence) — fontes pagas não integradas
- **Previsão de preços de veículos:** integração com Edmunds ou CarGurus API
- **Análise de sentimento:** expansão do pipeline News API com NLP sobre artigos coletados
- **Forecast por segmento:** desagregação do TOTALSA por tipo de veículo (SUV, sedan, pickup)

---

## 10. Configuração para Streamlit Cloud

O arquivo `.streamlit/secrets.example.toml` documenta o formato esperado:

```toml
[feature_sources]
FRED_API_KEY = "sua_chave_fred"
EIA_API_KEY  = "sua_chave_eia"
NEWS_API_KEY = "sua_chave_news"
```

As chaves são lidas via `FeatureSettings.from_streamlit_secrets(st.secrets)` e nunca aparecem em logs, commits ou mensagens de erro.

---

*Relatório gerado automaticamente a partir do estado do repositório em 14/08/2026.*
