# Auditoria de Integração dos Datasets

## Visão geral

| Camada | Registros | Cobertura | Papel analítico |
|---|---:|---|---|
| Mercado FRED `TOTALSA` | 607 meses | 01/1976–07/2026 | Série agregada de demanda de veículos leves. |
| Catálogo EPA `vehicles.csv` | 50,242 configurações | 1984–2027 | Produto, combustível, eficiência, emissões e tecnologia. |
| Preços de energia | 574 meses no painel consolidado | 11/1978–08/2026 | Preço nacional de gasolina/diesel e preço urbano médio de eletricidade. |

## Por que o painel tinha 2025–2027

O intervalo de 2025–2027 foi apenas o **filtro inicial de leitura** para evitar dezenas de marcas históricas e mais de cinquenta mil configurações em uma mesma visualização. Ele não era uma limitação do dataset. O catálogo completo contém **50,242 configurações** entre **1984 e 2027**, e a versão integrada passa a abrir o universo completo por padrão, mantendo filtros como recurso de exploração.

## Cobertura de campos EPA

| Campo | Configurações não nulas | Cobertura |
|---|---:|---:|
| `comb08` | 50,242 | 100.0% |
| `combE` | 50,242 | 100.0% |
| `co2TailpipeGpm` | 50,242 | 100.0% |
| `fuelCost08` | 50,242 | 100.0% |
| `cylinders` | 48,623 | 96.8% |
| `displ` | 48,625 | 96.8% |
| `range` | 50,242 | 100.0% |
| `rangeCity` | 50,242 | 100.0% |
| `rangeHwy` | 50,242 | 100.0% |

## Tecnologias de propulsão no catálogo completo

| Tecnologia | Configurações | Participação no catálogo |
|---|---:|---:|
| Combustão | 44,938 | 89.4% |
| Híbrido | 1,873 | 3.7% |
| Elétrico a bateria | 1,572 | 3.1% |
| Diesel | 1,310 | 2.6% |
| Híbrido plug-in | 447 | 0.9% |
| Gás natural | 60 | 0.1% |
| Célula a combustível | 42 | 0.1% |

## Séries de preço de energia

| Série mensal consolidada | Observações não nulas | Cobertura disponível |
|---|---:|---|
| gasolina_usd_gal | 433 | 08/1990–08/2026 |
| diesel_usd_gal | 390 | 03/1994–08/2026 |
| eletricidade_usd_kwh | 571 | 11/1978–07/2026 |

## Conexões válidas entre as camadas

A série de mercado não contém marca, modelo ou combustível. Portanto, ela é conectada ao catálogo de produto por **cenário analítico**, e não por uma chave de venda inexistente: o forecast de mercado dimensiona uma demanda agregada, enquanto o catálogo EPA mostra quais tecnologias, segmentos e atributos técnicos podem ser comparados. As séries de energia conectam-se ao catálogo por tipo de combustível e pelas unidades de consumo da EPA para produzir custo energético de referência por 100 milhas.

> A integração é conceitual e metodológica: ela não imputa venda por veículo nem transforma a base EPA em participação de mercado. O painel expõe essa separação em cada módulo.
