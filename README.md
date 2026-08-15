# Quant Automotive Intelligence & Planning

A **Quant Automotive Intelligence & Planning** é uma plataforma Streamlit para análise integrada de mercado, produto, energia, modelagem e planejamento operacional no setor automotivo. O projeto transforma fontes públicas rastreáveis em uma leitura quantitativa sequencial, com separação explícita entre fatos observados, modelos estimados e hipóteses operacionais.

A plataforma integra a série mensal agregada `TOTALSA` do FRED, o catálogo público da U.S. Environmental Protection Agency (EPA) e séries observadas de preços de gasolina, diesel e eletricidade da EIA/FRED/BLS. Ela utiliza *snapshots* versionados, contratos point-in-time, validação de esquema, hash de versão, monitoramento de frescor, proveniência e contingência local para preservar reprodutibilidade mesmo quando uma fonte externa está indisponível.

> **Limite de interpretação.** O FRED mede o mercado agregado de veículos leves dos Estados Unidos; não contém vendas por marca. A EPA descreve configurações técnicas de produto; não contém participação de mercado, unidades vendidas ou rentabilidade. A interface preserva essa separação e não cria inferências por marca, modelo ou combustível que os dados não suportam.

## Capacidades

| Camada | Entrega quantitativa |
|---|---|
| **Resumo** | Cobertura do universo completo, leitura da composição de produto, intervalo preditivo e distinção entre dado observado e cenário. |
| **Portfólio EPA** | Análise por marca, modelo, segmento e tecnologia; posicionamento de eficiência e emissões; auditoria temporal do campo `make`. |
| **Energia & combustível** | Séries reais de energia, custo de referência por 100 milhas, sensibilidade a choques de preço, correlação de Spearman e comparação tecnológica controlada. |
| **Mercado & forecast** | Forecast Engine modular com regressão de defasagens como modelo principal, benchmarks, walk-forward por horizonte, seleção de lags OOS e intervalos calibrados por resíduos OOS. |
| **Modelos integrados** | OLS temporal v2.3 como diagnóstico de drivers, com diferenças percentuais de CPI/produção industrial, lags explícitos, Newey–West, contingência GLSAR e diagnósticos econométricos; MLP de eficiência com validação temporal. O OLS v2.3 não alimenta o forecast principal. |
| **Risco & cenários** | Monte Carlo reprodutível, stockout probability, backlog risk, capacity-at-risk, VaR, CVaR, cenários parametrizados e sensibilidade com status de transmissão. |
| **Planejamento** | Programação linear com capacidade regular e extra, estoque inicial e de segurança, backlog, setup, custo e otimização PuLP por caminhos amostrados. |
| **Decisão** | Sinais green/amber/red/unavailable, confiança de disponibilidade das evidências, ações condicionais e limitações explícitas. |
| **Método & dados** | Saúde e proveniência de snapshots, contratos point-in-time, schema drift, staleness, fórmulas, escopo e limitações. |

## Fontes de dados

| Fonte | Cobertura | Uso na plataforma |
|---|---|---|
| [FRED — Total Vehicle Sales (`TOTALSA`)](https://fred.stlouisfed.org/series/TOTALSA) | Série mensal agregada de veículos leves, em milhões SAAR | Dinâmica de mercado, forecast e demanda de referência. |
| [EPA / FuelEconomy.gov](https://www.fueleconomy.gov/feg/download.shtml) | Catálogo de configurações por marca, modelo, ano-modelo, classe, combustível, consumo, emissões e autonomia | Inteligência de portfólio, tecnologia, eficiência, emissões e rede neural. |
| [EIA / FRED — gasolina e diesel](https://www.eia.gov/petroleum/gasdiesel/) | Séries nacionais semanais, consolidadas para frequência mensal | Preços por galão, custo energético e econometria temporal. |
| [BLS / FRED — eletricidade (`APU000072610`)](https://fred.stlouisfed.org/series/APU000072610) | Preço médio urbano mensal de eletricidade por kWh | Custo de referência de BEVs, econometria e sensibilidade. |
| [FRED — Consumer Price Index (`CPIAUCSL`)](https://fred.stlouisfed.org/series/CPIAUCSL) | Índice mensal de preços ao consumidor | Variação percentual mensal com lags 1 e 3 no OLS quando disponível no feature store. |
| [FRED — Industrial Production (`INDPRO`)](https://fred.stlouisfed.org/series/INDPRO) | Índice mensal de produção industrial | Variação percentual mensal com lag 2 no OLS quando disponível no feature store. |

Os dados locais em `data/` preservam os *snapshots* utilizados. O artefato `data/data_health.json` registra cobertura, campos, ausências, duplicidades, integridade e hash SHA-256. Consulte [`data/SOURCES.md`](data/SOURCES.md) para a proveniência detalhada.

## Metodologia

### Mercado e forecast probabilístico

O motor de mercado valida esquema e frequência, consolida a série em base mensal e executa diagnósticos de estacionariedade, decomposição STL e autocorrelação. O `src/analysis.py` é a **fonte de verdade operacional atualmente executada pelo app**: ele roda o benchmark, seleciona a Regressão com defasagens e entrega forecast e simulações às camadas de planejamento e risco. O `src/forecast_engine.py` formaliza um contrato modular `fit/predict/forecast/evaluate/diagnostics`, mas permanece **planejado, não integrado** à cadeia executada; seus testes preservam uma implementação candidata para integração futura controlada. O walk-forward por horizonte cobre 1, 3, 6 e 12 meses; conjuntos de lags são comparados por erro fora da amostra, nunca por R² de treino. Esse forecast operacional é distinto do OLS Newey–West v2.3, que permanece no painel de drivers para diagnóstico econométrico.

O modelo escolhido é reajustado sobre o histórico. O módulo `probabilistic_forecast.py` compara Normal, Student-t, bootstrap iid e moving block usando coverage e Pinball Loss em calibração prequential. Somente resíduos de dobras anteriores à dobra avaliada entram na calibração. O método, seed, origem dos resíduos, horizonte, período de treino e métricas de validação são persistidos nos metadados do forecast. O intervalo representa incerteza empírica de previsão, e não um limite causal ou garantia operacional.

A política única de aceite distingue pisos operacionais de alvos nominais exploratórios. Qualquer variante que altere o ponto, a distribuição de erro ou as simulações deve preservar, contra o baseline vigente, `VaR_95`, `CVaR_95`, `stockout_probability` e `expected_backlog_units`. Essa regra está formalizada em `src/acceptance_policy.py` e é serializada nos artefatos para impedir que uma redução aparente de risco seja tratada como melhoria sem evidência estatística robusta.

### OLS Newey–West v2.3 e autocorrelação residual

O OLS v2.3 é um **artefato diagnóstico**, não o motor de previsão utilizado no planejamento. Ele serve para avaliar persistência residual, contribuição relativa de drivers e adequação econométrica. O forecast operacional segue a implementação ativa da Regressão com defasagens em `src/analysis.py`. O `src/forecast_engine.py` é planejado, não integrado, e não deve ser interpretado como fonte de resultados da interface até que exista uma integração explícita e validada.

O `src/forecast_model.py` monta uma matriz mensal point-in-time a partir do snapshot `TOTALSA` e do feature store agregado. No artefato atual, os regressores usados são `y_lag1`, `y_lag2`, `y_lag3`, `y_lag6`, `y_lag9`, `y_lag12`, `X_CPI_diff_lag1`, `X_CPI_diff_lag3` e `X_PRODIND_diff_lag2`. Drivers macro opcionais, como FEDFUNDS, GASREG, desemprego, financiamento auto, confiança do consumidor e emprego total, só entram quando as respectivas colunas estão disponíveis; quando ausentes, são registrados separadamente como drivers configurados, mas não presentes na matriz. O JSON não os chama de candidatos avaliados e não selecionados porque o código atual não executa uma seleção stepwise documentada.

A validação é walk-forward em três dobras de seis meses. O estimador padrão é OLS com erros-padrão HAC de Newey–West. Para dependência serial fora da amostra, o critério primário é o Ljung–Box aplicado aos 18 resíduos OOS agrupados, em `lag=3`, com meta de p-valor `≥0,05`. O DW por dobra continua reportado apenas como informação descritiva, pois a janela de seis pontos é instável diante de erro de nível e ponto extremo. Para autocorrelação residual persistente, o mesmo contrato expõe `GLSAR` iterativo AR(1) como contingência e permite comparar ambos sem misturar amostras ou horizontes. A decisão de promover o fallback depende de Ljung–Box agrupado, MAPE, RMSE, cobertura P10–P90 e Pinball Loss simultaneamente, nunca de uma única métrica. O diagnóstico por dobra de ACF/PACF, Ljung–Box, ARCH, CUSUM, `y_lag12`, DW centrado e GLSAR está em [`docs/DIAGNOSTICO_AUTOCORRELACAO_OLS.md`](docs/DIAGNOSTICO_AUTOCORRELACAO_OLS.md). A conclusão é dupla: o DW OOS da primeira dobra é instável por viés de nível e erro extremo, enquanto os resíduos de treino ainda apresentam dependência serial e heterocedasticidade significativas. GLSAR permanece como contingência, não como forecast principal.

### Auditoria de integração operacional

A auditoria foi feita por imports e chamadas efetivas, não por nomes de módulos ou declarações. O resultado encontrado foi:

```text
./scripts/train_advanced_models.py:20: from forecast_model import run_ols_forecast
./scripts/train_advanced_models.py:32:     ols = run_ols_forecast()
./app.py:1527: from forecast_model import build_regression_matrix, walk_forward_ols
./app.py:1532:     matrix = build_regression_matrix()
./app.py:1533:     results = walk_forward_ols(matrix)
```

Não foram encontrados imports ou chamadas efetivas de `forecast_engine` em `app.py`, `analysis.py`, `risk_engine.py`, `scenario_engine.py`, `decision_intelligence.py` ou `robust_planning.py`; os imports localizados estão restritos aos testes do módulo. O encadeamento operacional do app é `analysis_module.run_backtest → analysis_module.make_forecast → analysis_module.build_production_plan`, seguido de `run_risk_engine`, `optimize_under_uncertainty` e `build_decision_intelligence`. Portanto, `src/forecast_engine.py` está documentado como **planejado, não integrado**, `src/analysis.py` é a fonte de verdade operacional e o OLS v2.3 é um **painel explicativo de drivers, não utilizado no forecast operacional**. O artefato pode estar aprovado nos pisos diagnósticos sem ser promovido para a cadeia operacional.

### Produto, tecnologia e energia

O catálogo EPA recebe validação de colunas e taxonomia de propulsão. As métricas de "configurações" representam registros técnicos no catálogo oficial, nunca unidades vendidas. As marcas correspondem literalmente ao campo `make` da EPA, incluindo nomes históricos quando presentes.

A camada de energia mantém unidades separadas: gasolina e diesel em US$/galão; eletricidade em US$/kWh. O custo de referência por 100 milhas é calculado somente em tecnologias para as quais consumo e preço são harmonizáveis. Correlação de Spearman resume associações monotônicas no recorte selecionado e não deve ser interpretada como causalidade.

### Modelos integrados e interpretabilidade

A OLS usa a janela mensal comum entre mercado e energia e reserva os 24 meses finais para teste. Seus diagnósticos incluem VIF, Durbin–Watson, Breusch–Pagan e desempenho fora da amostra. Quando o R² de teste é fraco ou negativo, o painel o declara como limitação e trata o resultado como descritivo, não preditivo.

A rede neural MLP estima a eficiência EPA `comb08` com atributos técnicos do catálogo. O corte por ano-modelo separa treino e teste, eliminando vazamento temporal. Além de MAE, RMSE e R² fora da amostra, os artefatos registram importância por permutação e erro por classe de propulsão para tornar a interpretação auditável.

### Planejamento operacional

O planejamento resolve um problema linear com PuLP/CBC. Participação assumida, horizonte, capacidade regular, capacidade extra, estoque inicial, estoque de segurança, custos de produção, manutenção, backlog, desvio de segurança e setup são todos controles explícitos. Os cenários **Downside**, **Base**, **Upside** e **Stress** aplicam choques declarados à demanda e retornam produção, estoque e backlog por período. A recomendação é uma regra transparente baseada no resultado do plano, não uma previsão oculta.

## Arquitetura e contratos de dados

```text
.
├── app.py                                  # Interface Streamlit vertical e cache de artefatos
├── src/
│   ├── config.py                            # Dataclasses imutáveis de fontes, forecast e planejamento
│   ├── ingestion.py                         # Timeout, retry, validação e fallback local
│   ├── data_quality.py                      # Perfis, hashes e saúde de snapshots
│   ├── analysis.py                          # Compatibilidade do pipeline de mercado e planejamento
│   ├── forecast_engine.py                   # Contrato modular, benchmarks e walk-forward por horizonte
│   ├── probabilistic_forecast.py            # Resíduos OOS, calibração e intervalos probabilísticos
│   ├── forecast_model.py                    # OLS Newey–West v2.3, lags conjuntos e GLSAR
│   ├── econometric_diagnostics.py           # Diagnósticos econométricos consolidados
│   ├── planning.py                          # Programação linear de produção, estoque e backlog
│   ├── robust_planning.py                   # PuLP por caminhos Monte Carlo e planos representativos
│   ├── risk_engine.py                       # Monte Carlo, stockout, VaR, CVaR e capacity-at-risk
│   ├── scenario_engine.py                   # Market share, cenários e sensibilidade parametrizados
│   ├── decision_intelligence.py             # Sinais, confiança, ações e limitações quantitativas
│   ├── scenarios.py                         # Compatibilidade de cenários legados e energia
│   ├── vehicle_intelligence.py              # Catálogo EPA, propulsão, marca, segmento e produto
│   ├── energy_intelligence.py               # Séries de energia, custo por 100 mi e Spearman
│   └── advanced_models.py                   # OLS temporal legado, diagnósticos e MLP de eficiência
├── data/
│   ├── TOTALSA_snapshot.csv                 # Snapshot FRED de contingência
│   ├── EPA_vehicles_snapshot.csv            # Snapshot EPA por configuração
│   ├── energy_price_snapshot.csv            # Snapshot mensal de energia
│   ├── data_health.json / .csv              # Saúde, integridade e proveniência
│   └── advanced_models/                     # Métricas, coeficientes e interpretabilidade
├── scripts/
│   ├── fetch_energy_prices.py                # Atualização reprodutível de energia
│   ├── build_data_health.py                  # Geração do perfil de saúde dos snapshots
│   ├── train_advanced_models.py              # Reexecução de OLS e rede neural
│   ├── materialize_fred_macro.py             # Materialização rastreável de CPIAUCSL e INDPRO
│   └── evaluate_risk_engine.py               # Avaliação reproduzível com snapshot FRED real
├── tests/                                   # Testes unitários e de integração
├── docs/                                    # Arquitetura, diagnóstico, auditorias e referências
├── pyproject.toml                           # Configuração Ruff
├── requirements.txt                         # Dependências de execução e qualidade
└── docs/ci/quality.yml                      # Template GitHub Actions de qualidade
```

A arquitetura detalhada está em [`docs/ARQUITETURA_ALVO.md`](docs/ARQUITETURA_ALVO.md); o diagnóstico da versão de origem, em [`docs/DIAGNOSTICO_TECNICO_INICIAL.md`](docs/DIAGNOSTICO_TECNICO_INICIAL.md). A evolução arquitetural seletiva orientada por padrões do ETIL está registrada em [`docs/RELATORIO_EVOLUCAO_ETIL.md`](docs/RELATORIO_EVOLUCAO_ETIL.md). A governança de risco e decisão está em [`docs/DECISION_INTELLIGENCE.md`](docs/DECISION_INTELLIGENCE.md), a auditoria da evolução v2 em [`docs/AUDITORIA_EVOLUCAO_V2.md`](docs/AUDITORIA_EVOLUCAO_V2.md), e a validação do OLS v2.3 em [`docs/VALIDACAO_OLS_V23.md`](docs/VALIDACAO_OLS_V23.md).

## Execução local

Use Python 3.11 ou superior. Em um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

O Streamlit normalmente abre em `http://localhost:8501`.

## Atualização e reprodutibilidade

```bash
# Atualiza o snapshot de energia quando as fontes públicas estiverem acessíveis.
python scripts/fetch_energy_prices.py

# Recalcula a saúde e a proveniência dos snapshots versionados.
python scripts/build_data_health.py

# Materializa CPIAUCSL e INDPRO reais e reconstrói o feature store macroeconômico.
PYTHONPATH=src python scripts/materialize_fred_macro.py

# Reexecuta OLS temporal e a rede neural com os snapshots locais.
python scripts/train_advanced_models.py

# Avalia risco Monte Carlo e imprime VaR/CVaR sobre o snapshot FRED local.
python scripts/evaluate_risk_engine.py
```

A ingestão utiliza timeout, tentativas com espera exponencial, validação de esquema e *fallback* local. O painel apresenta o status da fonte utilizada, evitando que uma indisponibilidade de rede silenciosamente altere a origem dos resultados.

## Testes e qualidade

```bash
python -m compileall -q app.py src scripts tests
ruff check .
ruff format --check .
pytest -q
```

O projeto possui **85 testes aprovados** cobrindo ingestão, governança temporal, schema drift, forecast, walk-forward por horizonte, calibração probabilística, diferenças macroeconômicas, OLS/GLSAR, diagnósticos econométricos, planejamento, cenários, risco Monte Carlo, otimização robusta, Decision Intelligence, integração, catálogo EPA, energia e modelos avançados. O template de CI está em `docs/ci/quality.yml`; para ativá-lo, copie o arquivo para `.github/workflows/quality.yml` em um *commit* autorizado a criar ou atualizar *workflows* no GitHub.

## Referências

- [1] [FRED — Total Vehicle Sales (`TOTALSA`)](https://fred.stlouisfed.org/series/TOTALSA)
- [2] [U.S. EPA / FuelEconomy.gov — Download Fuel Economy Data](https://www.fueleconomy.gov/feg/download.shtml)
- [3] [U.S. EIA — Gasoline and Diesel Fuel Update](https://www.eia.gov/petroleum/gasdiesel/)
- [4] [FRED / BLS — Electricity per Kilowatt-Hour](https://fred.stlouisfed.org/series/APU000072610)
- [5] [Cleveland et al. (1990) — STL](https://www.wessa.net/download/stl.pdf)
- [6] [Efron (1979) — Bootstrap Methods](https://doi.org/10.1214/aos/1176344552)
- [7] [FRED — Consumer Price Index (`CPIAUCSL`)](https://fred.stlouisfed.org/series/CPIAUCSL)
- [8] [FRED — Industrial Production Index (`INDPRO`)](https://fred.stlouisfed.org/series/INDPRO)

### Backtest conjunto de lags e intervalos condicionais

O backtest controlado da especificação conjunta `y_lag1`, `y_lag2`, `y_lag3`, `y_lag6`, `y_lag9` e `y_lag12` está documentado em [`docs/BACKTEST_LAGS_VOLATILIDADE.md`](docs/BACKTEST_LAGS_VOLATILIDADE.md) e pode ser reproduzido por `PYTHONPATH=src python3 scripts/evaluate_joint_lags_volatility.py`. O desafiante reduziu o MAPE de 3,6613% para 3,0936%, o RMSE de 0,7776 para 0,6988 e elevou o p-valor do Ljung–Box OOS agrupado de 0,0390 para 0,1070. Pela [`política única de aceite`](docs/POLITICA_ACEITE_MODELOS.md), ele passa os pisos de MAPE 4,00%, cobertura 75,00% e Ljung–Box; permanece acima dos alvos nominais exploratórios de MAPE 2,87% e cobertura 80% e foi promovido apenas como padrão do painel diagnóstico.

A calibração P10–P90 condicionada à volatilidade residual recente também foi implementada em `src/analysis.py` e avaliada sem vazamento temporal. Ela reduziu a cobertura para 58,33% tanto no baseline quanto na especificação conjunta; por isso, a abordagem fixa prequential permanece o padrão do painel. A promoção dos lags conjuntos é restrita ao OLS diagnóstico e não altera o forecast operacional.
