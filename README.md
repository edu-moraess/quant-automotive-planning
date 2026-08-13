# Quant Automotive Intelligence

A **Quant Automotive Intelligence** é uma plataforma Streamlit para análise integrada de mercado, produto, eficiência tecnológica e cenários operacionais no setor automotivo. Ela conecta uma série mensal agregada de veículos leves com um catálogo público de configurações por fabricante e modelo, transformando dados oficiais em uma experiência de análise navegável e auditável.

A plataforma combina o FRED `TOTALSA`, série de vendas agregadas de veículos leves nos Estados Unidos, com a base pública da U.S. Environmental Protection Agency (EPA), que descreve veículos por fabricante, modelo, ano-modelo, segmento, combustível, eficiência, emissões, autonomia e custo anual estimado [1] [2]. A camada de energia acrescenta preços nacionais de gasolina e diesel da EIA/FRED e preço médio urbano de eletricidade do BLS/FRED para contextualizar custo energético e eficiência [3] [4].

> As fontes possuem papéis distintos. O FRED mede o mercado agregado, sem vendas por marca. A EPA descreve atributos técnicos de configurações de produto, sem vendas, participação de mercado ou rentabilidade. A interface preserva essa separação para evitar inferências incorretas.

## Capacidades

| Módulo | Capacidades analíticas |
|---|---|
| Resumo | Universo completo de 1984–2027, forecast p10–p90 e uma leitura sequencial de produto. |
| Portfólio | Marcas, segmentos, posicionamento técnico e auditoria temporal do campo `make`. |
| Energia & Combustível | Preços reais de energia, custo de referência por 100 milhas, mix de combustível e correlação de Spearman. |
| Mercado & Forecast | Histórico, backtest walk-forward, resíduos e seleção de modelo. |
| Modelos integrados | OLS com energia observada, coeficientes auditáveis e rede neural de eficiência com validação temporal. |
| Planejamento | Cenários p10–p90, capacidade, estoque, backlog e sensibilidade. |
| Método & Dados | Fonte, fórmulas, escopo, limites e documentação reprodutível. |

## Fontes de dados

| Fonte | Cobertura | Utilização |
|---|---|---|
| [FRED — Total Vehicle Sales (`TOTALSA`)](https://fred.stlouisfed.org/series/TOTALSA) | Série mensal agregada de veículos leves em milhões SAAR | Dinâmica de mercado, previsão e cenários. |
| [U.S. EPA / FuelEconomy.gov](https://www.fueleconomy.gov/feg/download.shtml) | Configurações de veículos leves por fabricante, modelo, classe, combustível, consumo, emissões e autonomia | Inteligência de produto e tecnologia. |
| [EIA / FRED — `GASREGW` e `GASDESW`](https://www.eia.gov/petroleum/gasdiesel/) | Preços nacionais semanais de gasolina regular e diesel, consolidados mensalmente | Contexto de preço por galão e custo de referência de combustível. |
| [BLS / FRED — `APU000072610`](https://fred.stlouisfed.org/series/APU000072610) | Preço médio urbano mensal de eletricidade por kWh | Contexto de preço elétrico e custo de referência de BEVs. |
| [EPA Automotive Trends](https://www.epa.gov/greenvehicles/50-years-epas-automotive-trends-report) | Contexto histórico de eficiência, emissões e tecnologia no mercado de veículos leves | Interpretação setorial e referência. |

O repositório inclui *snapshots* das três camadas de dados em `data/`, permitindo executar o painel mesmo em indisponibilidade momentânea da fonte online. A interface abre o catálogo completo, de **1984 a 2027**, por padrão; filtros são uma opção de exploração e não reduzem os dados de origem. Consulte [`data/SOURCES.md`](data/SOURCES.md) para a proveniência, cobertura e os limites de cada fonte.

## Metodologia

A camada de mercado trata a série com checagens de qualidade, teste Dickey-Fuller aumentado, decomposição STL e análise de autocorrelação. Três modelos são comparados por validação temporal walk-forward: referência sazonal, Holt-Winters aditivo e regressão Ridge com defasagens. O modelo com menor MAPE médio é reajustado sobre o histórico, e seus resíduos fora da amostra são reamostrados por *bootstrap* para produzir cenários empíricos p10–p90 [6] [7] [8].

A camada de produto cria uma taxonomia de propulsão para registros EPA e consolida métricas por marca, modelo e segmento. As métricas de “configurações” medem registros de produto na base pública; elas não representam unidades vendidas. Os nomes de marcas são valores literais do campo `make` da EPA, por isso o catálogo também inclui marcas históricas. O painel apresenta primeiro e último ano-modelo por nome, sem inferir atividade comercial. A auditoria reproduzível está em [`docs/AUDITORIA_CATALOGO_EPA.md`](docs/AUDITORIA_CATALOGO_EPA.md).

A camada de energia mantém unidades separadas: gasolina e diesel são medidos em US$/galão; eletricidade, em US$/kWh. Ela exibe as séries históricas como índice base 100 e calcula custo energético por 100 milhas somente para gasolina, diesel e veículos elétricos a bateria, pois são os casos com preço e consumo harmonizados. Correlações de Spearman resumem associações monotônicas entre eficiência, custo, emissões e motorização no recorte filtrado, sem inferir causalidade.

A camada de modelos integra os datasets sem inventar chaves inexistentes. Uma regressão OLS temporal usa a interseção mensal de mercado e preços de energia, com os últimos 24 meses reservados para teste. Uma rede neural MLP estima eficiência EPA (`comb08`) a partir de características técnicas de 47.423 configurações de treino (1984–2024) e é avaliada em 2.819 configurações recentes (2025–2027). O OLS é apresentado como análise explicativa quando seu teste não é preditivamente forte; a rede neural reporta MAE, RMSE e \(R^2\) fora da amostra. A arquitetura está documentada em [`docs/ARQUITETURA_VERTICAL_E_MODELOS.md`](docs/ARQUITETURA_VERTICAL_E_MODELOS.md).

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
├── src/energy_intelligence.py            # Preços de energia, custo por 100 milhas e correlação
├── src/advanced_models.py                # OLS temporal e rede neural de eficiência
├── data/TOTALSA_snapshot.csv             # Snapshot FRED de contingência
├── data/EPA_vehicles_snapshot.csv        # Snapshot EPA por configuração de veículo
├── data/energy_price_snapshot.csv        # Snapshot FRED de gasolina, diesel e eletricidade
├── data/advanced_models/                 # Métricas, coeficientes e validações versionadas
├── data/SOURCES.md                       # Proveniência e limites das fontes
├── scripts/fetch_energy_prices.py        # Atualização reproduzível das séries de energia
├── scripts/train_advanced_models.py      # Treino reproduzível de OLS e rede neural
├── docs/ARQUITETURA_E_METODOLOGIA.md     # Arquitetura, métodos e referências
├── docs/ARQUITETURA_DE_INFORMACAO_REFINADA.md # Arquitetura de interação e visualização
├── docs/AUDITORIA_CATALOGO_EPA.md        # Origem e cobertura temporal dos nomes de marca
├── docs/PESQUISA_REFERENCIAS_E_DADOS.md  # Referências de interface e fontes complementares
├── docs/ARQUITETURA_VERTICAL_E_MODELOS.md # Interface vertical e metodologia dos modelos
├── docs/AUDITORIA_INTEGRACAO_TOTAL.md     # Cobertura e conexão válida entre os datasets
├── tests/                                # Testes unitários e de integração
├── .streamlit/config.toml                # Tema e configuração visual
├── requirements.txt                      # Dependências Python
└── docs/ci/quality.yml                   # Template de integração contínua
```

## Testes e qualidade

```bash
python -m pytest -q
python -m compileall -q app.py src scripts
python scripts/fetch_energy_prices.py    # opcional: atualiza o snapshot de energia
python scripts/train_advanced_models.py   # retreina OLS e rede neural nos snapshots
```

O template de integração contínua está em `docs/ci/quality.yml`. Para ativá-lo no GitHub, copie-o para `.github/workflows/quality.yml` e faça um *commit* com uma credencial que tenha permissão para criar ou atualizar *workflows*.

## Referências

[1]: https://fred.stlouisfed.org/series/TOTALSA "FRED — Total Vehicle Sales (TOTALSA)"
[2]: https://www.fueleconomy.gov/feg/download.shtml "U.S. EPA / FuelEconomy.gov — Download Fuel Economy Data"
[3]: https://www.eia.gov/petroleum/gasdiesel/ "U.S. EIA — Gasoline and Diesel Fuel Update"
[4]: https://fred.stlouisfed.org/series/APU000072610 "FRED / BLS — Electricity per Kilowatt-Hour"
[5]: https://www.epa.gov/greenvehicles/50-years-epas-automotive-trends-report "U.S. EPA — 50 Years of Automotive Trends Report"
[6]: https://www.wessa.net/download/stl.pdf "Cleveland et al. (1990) — STL"
[7]: https://doi.org/10.1093/biomet/65.2.297 "Ljung & Box (1978)"
[8]: https://doi.org/10.1214/aos/1176344552 "Efron (1979) — Bootstrap Methods"
