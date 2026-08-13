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
