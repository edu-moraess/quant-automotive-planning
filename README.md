# Quant Automotive Intelligence & Planning

A **Quant Automotive Intelligence & Planning** é uma plataforma Streamlit para análise integrada de mercado, produto, energia, modelagem e planejamento operacional no setor automotivo. O projeto transforma fontes públicas rastreáveis em uma leitura quantitativa sequencial, com separação explícita entre fatos observados, modelos estimados e hipóteses operacionais.

A plataforma integra a série mensal agregada `TOTALSA` do FRED, o catálogo público da U.S. Environmental Protection Agency (EPA) e séries observadas de preços de gasolina, diesel e eletricidade da EIA/FRED/BLS. Ela utiliza *snapshots* versionados, validação de esquema, proveniência e contingência local para preservar reprodutibilidade mesmo quando uma fonte externa está indisponível.

> **Limite de interpretação.** O FRED mede o mercado agregado de veículos leves dos Estados Unidos; não contém vendas por marca. A EPA descreve configurações técnicas de produto; não contém participação de mercado, unidades vendidas ou rentabilidade. A interface preserva essa separação e não cria inferências por marca, modelo ou combustível que os dados não suportam.

## Capacidades

| Camada | Entrega quantitativa |
|---|---|
| **Resumo** | Cobertura do universo completo, leitura da composição de produto, intervalo preditivo e distinção entre dado observado e cenário. |
| **Portfólio EPA** | Análise por marca, modelo, segmento e tecnologia; posicionamento de eficiência e emissões; auditoria temporal do campo `make`. |
| **Energia & combustível** | Séries reais de energia, custo de referência por 100 milhas, sensibilidade a choques de preço, correlação de Spearman e comparação tecnológica controlada. |
| **Mercado & forecast** | Diagnósticos temporais, *backtest* walk-forward, comparação de quatro modelos, métricas múltiplas e intervalo empírico p10–p90. |
| **Modelos integrados** | OLS temporal com diagnóstico de VIF, Durbin–Watson e Breusch–Pagan; MLP de eficiência com validação temporal, importância por permutação e erro por propulsão. |
| **Planejamento** | Programação linear com capacidade regular e extra, estoque inicial e de segurança, backlog, setup, custo e cenários Downside/Base/Upside/Stress. |
| **Método & dados** | Saúde e proveniência de snapshots, fórmulas, escopo, limitações e documentação técnica. |

## Fontes de dados

| Fonte | Cobertura | Uso na plataforma |
|---|---|---|
| [FRED — Total Vehicle Sales (`TOTALSA`)](https://fred.stlouisfed.org/series/TOTALSA) | Série mensal agregada de veículos leves, em milhões SAAR | Dinâmica de mercado, forecast e demanda de referência. |
| [EPA / FuelEconomy.gov](https://www.fueleconomy.gov/feg/download.shtml) | Catálogo de configurações por marca, modelo, ano-modelo, classe, combustível, consumo, emissões e autonomia | Inteligência de portfólio, tecnologia, eficiência, emissões e rede neural. |
| [EIA / FRED — gasolina e diesel](https://www.eia.gov/petroleum/gasdiesel/) | Séries nacionais semanais, consolidadas para frequência mensal | Preços por galão, custo energético e econometria temporal. |
| [BLS / FRED — eletricidade (`APU000072610`)](https://fred.stlouisfed.org/series/APU000072610) | Preço médio urbano mensal de eletricidade por kWh | Custo de referência de BEVs, econometria e sensibilidade. |

Os dados locais em `data/` preservam os *snapshots* utilizados. O artefato `data/data_health.json` registra cobertura, campos, ausências, duplicidades, integridade e hash SHA-256. Consulte [`data/SOURCES.md`](data/SOURCES.md) para a proveniência detalhada.

## Metodologia

### Mercado e forecast probabilístico

O motor de mercado valida esquema e frequência, consolida a série em base mensal e executa diagnósticos de estacionariedade, decomposição STL e autocorrelação. Quatro candidatos são comparados em validação temporal *walk-forward*: **referência sazonal**, **Holt–Winters aditivo**, **Ridge com defasagens** e **AutoReg sazonal**. Cada dobra é avaliada por MAPE, sMAPE, WAPE, MASE e RMSE; a seleção é feita com a métrica configurada de forma explícita.

O modelo escolhido é reajustado sobre o histórico. Seus erros fora da amostra alimentam reamostragem *bootstrap* iid ou em blocos móveis, conforme configuração, para construir cenários probabilísticos p10, p50 e p90. Portanto, o intervalo representa incerteza empírica de previsão, e não um limite causal ou garantia operacional.

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
│   ├── analysis.py                          # Mercado, backtest, forecast e diagnóstico temporal
│   ├── planning.py                          # Programação linear de produção, estoque e backlog
│   ├── scenarios.py                         # Cenários de demanda e sensibilidade de energia
│   ├── vehicle_intelligence.py              # Catálogo EPA, propulsão, marca, segmento e produto
│   ├── energy_intelligence.py               # Séries de energia, custo por 100 mi e Spearman
│   └── advanced_models.py                   # OLS temporal, diagnósticos e MLP de eficiência
├── data/
│   ├── TOTALSA_snapshot.csv                 # Snapshot FRED de contingência
│   ├── EPA_vehicles_snapshot.csv            # Snapshot EPA por configuração
│   ├── energy_price_snapshot.csv            # Snapshot mensal de energia
│   ├── data_health.json / .csv              # Saúde, integridade e proveniência
│   └── advanced_models/                     # Métricas, coeficientes e interpretabilidade
├── scripts/
│   ├── fetch_energy_prices.py                # Atualização reprodutível de energia
│   ├── build_data_health.py                  # Geração do perfil de saúde dos snapshots
│   └── train_advanced_models.py              # Reexecução de OLS e rede neural
├── tests/                                   # Testes unitários e de integração
├── docs/                                    # Arquitetura, diagnóstico, auditorias e referências
├── pyproject.toml                           # Configuração Ruff
├── requirements.txt                         # Dependências de execução e qualidade
└── docs/ci/quality.yml                      # Template GitHub Actions de qualidade
```

A arquitetura detalhada está em [`docs/ARQUITETURA_ALVO.md`](docs/ARQUITETURA_ALVO.md); o diagnóstico da versão de origem, em [`docs/DIAGNOSTICO_TECNICO_INICIAL.md`](docs/DIAGNOSTICO_TECNICO_INICIAL.md).

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

# Reexecuta OLS temporal e a rede neural com os snapshots locais.
python scripts/train_advanced_models.py
```

A ingestão utiliza timeout, tentativas com espera exponencial, validação de esquema e *fallback* local. O painel apresenta o status da fonte utilizada, evitando que uma indisponibilidade de rede silenciosamente altere a origem dos resultados.

## Testes e qualidade

```bash
python -m compileall -q app.py src scripts tests
ruff check .
ruff format --check .
pytest -q
```

O projeto possui testes de ingestão e qualidade, forecast, planejamento, cenários, integração, catálogo EPA, energia e modelos avançados. O template de CI está em `docs/ci/quality.yml`; para ativá-lo, copie o arquivo para `.github/workflows/quality.yml` em um *commit* autorizado a criar ou atualizar *workflows* no GitHub.

## Referências

- [1] [FRED — Total Vehicle Sales (`TOTALSA`)](https://fred.stlouisfed.org/series/TOTALSA)
- [2] [U.S. EPA / FuelEconomy.gov — Download Fuel Economy Data](https://www.fueleconomy.gov/feg/download.shtml)
- [3] [U.S. EIA — Gasoline and Diesel Fuel Update](https://www.eia.gov/petroleum/gasdiesel/)
- [4] [FRED / BLS — Electricity per Kilowatt-Hour](https://fred.stlouisfed.org/series/APU000072610)
- [5] [Cleveland et al. (1990) — STL](https://www.wessa.net/download/stl.pdf)
- [6] [Efron (1979) — Bootstrap Methods](https://doi.org/10.1214/aos/1176344552)
