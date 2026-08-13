# Auditoria do Catálogo EPA

## Resultado

O arquivo `EPA_vehicles_snapshot.csv` é uma cópia local do arquivo público `vehicles.csv` do [FuelEconomy.gov](https://www.fueleconomy.gov/feg/download.shtml), da U.S. Environmental Protection Agency. A página oficial informa que os dados de economia de combustível são derivados de testes do National Vehicle and Fuel Emissions Laboratory da EPA e de dados de fabricantes submetidos sob supervisão da agência [1].

| Indicador | Valor |
|---|---:|
| Registros de configuração no snapshot | 50,242 |
| Valores distintos em `make` | 146 |
| Combinações distintas de marca e modelo | 5,737 |
| Primeiro ano-modelo | 1984 |
| Último ano-modelo | 2027 |
| Marcas com registro EPA em 2025–2027 | 49 |
| Marcas somente históricas antes de 2025 | 97 |
| SHA-256 do snapshot | `cb6304e8970fabc4ae144ee91210953729ab3bae1ff0290f986c31501bf2c7a7` |

## Significado de “marca”

A plataforma mostra exatamente os valores literais do campo `make` do arquivo da EPA. O campo identifica o fabricante conforme registrado pela fonte para aquela configuração de veículo. Como a série abrange décadas, a lista inclui nomes contemporâneos e históricos. O painel não normaliza conglomerados, não deduz propriedade societária e não declara que uma marca esteja comercialmente ativa apenas porque aparece no arquivo.

> O status exibido pela plataforma é apenas temporal: “Registro EPA em 2025–2027” significa que o nome aparece em pelo menos uma configuração desse intervalo no snapshot. “Somente histórico até AAAA” significa que o último ano-modelo observado para o nome foi AAAA.

## Exemplos de rastreabilidade

| Nome literal no campo `make` | Primeiro ano | Último ano | Modelos | Configurações | Presença no snapshot |
|---|---:|---:|---:|---:|---|
| Chevrolet | 1984 | 2027 | 313 | 4,586 | Registro EPA em 2025–2027 |
| Ford | 1984 | 2027 | 279 | 3,949 | Registro EPA em 2025–2027 |
| Geo | 1989 | 1997 | 15 | 147 | Somente histórico até 1997 |
| Lucid | 2022 | 2027 | 30 | 64 | Registro EPA em 2025–2027 |
| Pontiac | 1984 | 2010 | 60 | 893 | Somente histórico até 2010 |
| Rivian | 2022 | 2027 | 126 | 187 | Registro EPA em 2025–2027 |
| Saab | 1984 | 2012 | 27 | 432 | Somente histórico até 2012 |
| Tesla | 2012 | 2026 | 88 | 185 | Registro EPA em 2025–2027 |
| Toyota | 1984 | 2027 | 212 | 2,628 | Registro EPA em 2025–2027 |

## Limites de interpretação

O catálogo EPA é adequado para analisar especificações, eficiência e abrangência técnica de configurações. Ele não informa unidades vendidas, receita, preço de transação, participação de mercado, rentabilidade ou qualidade. A EPA também observa que estimativas de MPG podem ser revisadas quando novas informações indicam que valores de etiqueta estavam altos [1] [2].

## Referências

[1]: https://www.fueleconomy.gov/feg/download.shtml "FuelEconomy.gov — Download Fuel Economy Data"
[2]: https://www.epa.gov/compliance-and-fuel-economy-data/data-cars-used-testing-fuel-economy "EPA — Data on Cars used for Testing Fuel Economy"
