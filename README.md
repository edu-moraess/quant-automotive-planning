# Quant Automotive Intelligence

A **Quant Automotive Intelligence** é uma plataforma Streamlit para análise integrada de mercado, produto, eficiência tecnológica e cenários operacionais no setor automotivo. Ela conecta uma série mensal agregada de veículos leves com um catálogo público de configurações por fabricante e modelo, transformando dados oficiais em uma experiência de análise navegável e auditável.

A plataforma combina o FRED `TOTALSA`, série de vendas agregadas de veículos leves nos Estados Unidos, com a base pública da U.S. Environmental Protection Agency (EPA), que descreve veículos por fabricante, modelo, ano-modelo, segmento, combustível, eficiência, emissões, autonomia e custo anual estimado [1] [2].

> As fontes possuem papéis distintos. O FRED mede o mercado agregado, sem vendas por marca. A EPA descreve atributos técnicos de configurações de produto, sem vendas, participação de mercado ou rentabilidade. A interface preserva essa separação para evitar inferências incorretas.

## Capacidades

| Módulo | Capacidades analíticas |
|---|---|
| Visão integrada | KPIs de mercado, produto e transição tecnológica em uma única camada. |
| Produto & Marcas | Comparação de fabricantes, modelos, segmentos EPA, amplitude de portfólio, posicionamento técnico e auditoria temporal do campo `make`. |
| Eficiência & Transição | Propulsão, MPG/MPGe, CO₂ de escapamento, autonomia, custo anual publicado e evolução por ano-modelo. |
| Mercado & Forecast | Qualidade, ADF, STL, ACF/PACF, backtest walk-forward, resíduos e seleção de modelo. |
| Planejamento | Previsão com faixa p10–p90, cenário operacional, capacidade, estoque, backlog e sensibilidade. |
| Metodologia & Dados | Arquitetura, fontes, formulações, escopo e referências. |

## Fontes de dados

| Fonte | Cobertura | Utilização |
|---|---|---|
| [FRED — Total Vehicle Sales (`TOTALSA`)](https://fred.stlouisfed.org/series/TOTALSA) | Série mensal agregada de veículos leves em milhões SAAR | Dinâmica de mercado, previsão e cenários. |
| [U.S. EPA / FuelEconomy.gov](https://www.fueleconomy.gov/feg/download.shtml) | Configurações de veículos leves por fabricante, modelo, classe, combustível, consumo, emissões e autonomia | Inteligência de produto e tecnologia. |
| [EPA Automotive Trends](https://www.epa.gov/greenvehicles/50-years-epas-automotive-trends-report) | Contexto histórico de eficiência, emissões e tecnologia no mercado de veículos leves | Interpretação setorial e referência. |

O repositório inclui *snapshots* das duas bases em `data/`, permitindo executar o painel mesmo em indisponibilidade momentânea da fonte online. Consulte [`data/SOURCES.md`](data/SOURCES.md) para a proveniência, cobertura e os limites de cada fonte.

## Metodologia

A camada de mercado trata a série com checagens de qualidade, teste Dickey-Fuller aumentado, decomposição STL e análise de autocorrelação. Três modelos são comparados por validação temporal walk-forward: referência sazonal, Holt-Winters aditivo e regressão Ridge com defasagens. O modelo com menor MAPE médio é reajustado sobre o histórico, e seus resíduos fora da amostra são reamostrados por *bootstrap* para produzir cenários empíricos p10–p90 [4] [5] [6].

A camada de produto cria uma taxonomia de propulsão para registros EPA e consolida métricas por marca, modelo e segmento. As métricas de “configurações” medem registros de produto na base pública; elas não representam unidades vendidas. Os nomes de marcas são valores literais do campo `make` da EPA, por isso o catálogo também inclui marcas históricas. O painel apresenta primeiro e último ano-modelo por nome, sem inferir atividade comercial. A auditoria reproduzível está em [`docs/AUDITORIA_CATALOGO_EPA.md`](docs/AUDITORIA_CATALOGO_EPA.md), e a documentação metodológica completa está em [`docs/ARQUITETURA_E_METODOLOGIA.md`](docs/ARQUITETURA_E_METODOLOGIA.md).

## Execução local

Use Python 3.10 ou superior. Crie um ambiente virtual, instale as dependências e inicie o painel:

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

A aplicação será aberta no endereço indicado pelo Streamlit, usualmente `http://localhost:8501`.

## Estrutura

```text
.
├── app.py                                # Interface Streamlit e visualizações
├── src/analysis.py                       # Mercado, forecast e otimização
├── src/vehicle_intelligence.py           # Produto, marca, modelo, eficiência e propulsão
├── data/TOTALSA_snapshot.csv             # Snapshot FRED de contingência
├── data/EPA_vehicles_snapshot.csv        # Snapshot EPA por configuração de veículo
├── data/SOURCES.md                       # Proveniência e limites das fontes
├── docs/ARQUITETURA_E_METODOLOGIA.md     # Arquitetura, métodos e referências
├── docs/AUDITORIA_CATALOGO_EPA.md        # Origem e cobertura temporal dos nomes de marca
├── tests/                                # Testes unitários e de integração
├── .streamlit/config.toml                # Tema e configuração visual
├── requirements.txt                      # Dependências Python
└── docs/ci/quality.yml                   # Template de integração contínua
```

## Testes e qualidade

```bash
python -m pytest -q
python -m compileall -q app.py src
```

O template de integração contínua está em `docs/ci/quality.yml`. Para ativá-lo no GitHub, copie-o para `.github/workflows/quality.yml` e faça um *commit* com uma credencial que tenha permissão para criar ou atualizar *workflows*.

## Referências

[1]: https://fred.stlouisfed.org/series/TOTALSA "FRED — Total Vehicle Sales (TOTALSA)"
[2]: https://www.fueleconomy.gov/feg/download.shtml "U.S. EPA / FuelEconomy.gov — Download Fuel Economy Data"
[3]: https://www.epa.gov/greenvehicles/50-years-epas-automotive-trends-report "U.S. EPA — 50 Years of Automotive Trends Report"
[4]: https://www.wessa.net/download/stl.pdf "Cleveland et al. (1990) — STL"
[5]: https://doi.org/10.1093/biomet/65.2.297 "Ljung & Box (1978)"
[6]: https://doi.org/10.1214/aos/1176344552 "Efron (1979) — Bootstrap Methods"
