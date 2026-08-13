# Fontes de Dados

## FRED — `TOTALSA`

| Item | Descrição |
|---|---|
| Série | Total Vehicle Sales (`TOTALSA`) |
| Fonte | Federal Reserve Economic Data; fonte original atribuída ao U.S. Bureau of Economic Analysis |
| Cobertura | Série mensal de vendas totais de veículos leves nos Estados Unidos, em milhões de unidades SAAR |
| Uso | Diagnóstico temporal, backtest, previsão e cenários de mercado |
| Arquivo local | `TOTALSA_snapshot.csv` |
| Fonte oficial | [FRED — Total Vehicle Sales](https://fred.stlouisfed.org/series/TOTALSA) |

A série representa o mercado agregado. Ela não é desagregada por fabricante, marca ou modelo.

## U.S. EPA / FuelEconomy.gov — `vehicles.csv`

| Item | Descrição |
|---|---|
| Fonte | U.S. Environmental Protection Agency e U.S. Department of Energy / FuelEconomy.gov |
| Cobertura | Veículos leves por ano-modelo, fabricante, modelo, classe EPA, combustível e especificações de eficiência |
| Atributos selecionados | MPG/MPGe, CO₂ de escapamento, autonomia, custo anual de energia, cilindros, cilindrada, transmissão e tração |
| Uso | Exploração de produto por marca, modelo, segmento e propulsão |
| Arquivo local | `EPA_vehicles_snapshot.csv` |
| Fonte oficial | [EPA / FuelEconomy.gov — Download Fuel Economy Data](https://www.fueleconomy.gov/feg/download.shtml) |

A EPA publica características e estimativas de consumo de configurações de veículos. O arquivo não informa vendas, participação de mercado, preços transacionados, rentabilidade ou avaliação de qualidade por marca. As métricas de portfólio da plataforma devem ser interpretadas como abrangência de configurações observadas na base pública.

## Referência setorial

A EPA afirma que o Automotive Trends Report cobre automóveis, SUVs e caminhões leves novos comercializados nos Estados Unidos e disponibiliza contexto histórico de eficiência, emissões e tecnologia [1].

[1]: https://www.epa.gov/greenvehicles/50-years-epas-automotive-trends-report "EPA — 50 Years of Automotive Trends Report"

## Auditoria de origem e nomes de marcas

A verificação foi atualizada em 13 de agosto de 2026. A página oficial de download informa que o arquivo `vehicles.csv` reúne dados de economia de combustível derivados de testes realizados no National Vehicle and Fuel Emissions Laboratory da EPA e de dados submetidos por fabricantes sob supervisão da agência [1]. A página também informa revisões de estimativas para determinados anos e fabricantes, razão pela qual o painel trata o arquivo como *snapshot* com data de atualização, não como fonte imutável [1].

Os nomes exibidos no seletor de fabricantes são os valores literais do campo `make` publicado pela EPA no arquivo `vehicles.csv`. Como o catálogo cobre muitos anos-modelo, ele inclui marcas históricas, descontinuadas e grafias próprias do cadastro; a presença de um nome não equivale a uma marca ativa no ano atual. A plataforma passará a mostrar o primeiro e o último ano-modelo observados para cada nome de marca, em vez de atribuir um status comercial inferido.

A EPA também descreve que os dados de teste usados para estimativas de economia de combustível vêm de seu laboratório e de dados de fabricantes enviados à agência; as estimativas podem ser alteradas quando surgem informações que indiquem valores excessivamente altos em etiquetas de consumo [2].

[1]: https://www.fueleconomy.gov/feg/download.shtml "FuelEconomy.gov — Download Fuel Economy Data"
[2]: https://www.epa.gov/compliance-and-fuel-economy-data/data-cars-used-testing-fuel-economy "EPA — Data on Cars used for Testing Fuel Economy"
