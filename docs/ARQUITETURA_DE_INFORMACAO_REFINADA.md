# Arquitetura de Informação Refinada

## Princípio de leitura

A interface passa a organizar a análise por perguntas, e não por disponibilidade de gráficos. Cada aba terá um foco operacional, no máximo quatro indicadores no topo e visualizações com uma unidade comparável por vez.

| Aba | Pergunta principal | Elementos visuais prioritários | Detalhes sob demanda |
|---|---|---|---|
| Resumo executivo | O que mudou no mercado e no catálogo recente? | Quatro KPIs, previsão p10–p90 e mapa de marcas. | Metodologia e tabelas extensas. |
| Portfólio | Como marcas e segmentos se posicionam? | Matriz eficiência × emissões; ranking compacto de marca. | Registro completo de marcas e modelos. |
| Energia & Combustível | Como preço de energia, tipo de combustível, eficiência e custo se relacionam? | Cards de preço, índice temporal, custo por 100 milhas e correlações. | Séries brutas e recortes por combustível. |
| Mercado & Forecast | Qual modelo descreve melhor a demanda e qual é a incerteza? | Histórico, MAPE e previsão. | STL, ACF, resíduos e resultados por dobra. |
| Planejamento | Como capacidade e serviço respondem ao cenário? | Quatro KPIs, plano mensal e sensibilidade. | Cenários e tabela completa. |
| Método & Dados | O que cada fonte mede e quais são os limites? | Cartões de proveniência e cobertura. | Auditoria de marcas, dicionário de campos e referências. |

## Camada de energia e combustível

| Indicador | Dados | Unidade | Regra de interpretação |
|---|---|---|---|
| Preço nacional de gasolina | FRED `GASREGW` / EIA | US$/galão | Média mensal de série semanal; inclui impostos. |
| Preço nacional de diesel | FRED `GASDESW` / EIA | US$/galão | Média mensal de série semanal; inclui impostos. |
| Preço médio de eletricidade | FRED `APU000072610` / BLS | US$/kWh | Média urbana mensal; não representa tarifa local. |
| Custo energético por 100 milhas | Preço de energia + EPA `comb08`/`combE` | US$/100 milhas | Comparável dentro de combustível e com unidade explicitada. |
| Custo anual EPA | EPA `fuelCost08` | US$/ano | Estimativa publicada para configuração, não despesa individual. |
| Correlação de Spearman | Campos EPA comparáveis | ρ e n | Associação monotônica; não estabelece causalidade. |

## Regras visuais

A plataforma evitará gráficos de pizza com múltiplos rótulos, legendas longas e matrizes de pontos sem seleção. Séries de combustíveis com unidades diferentes serão exibidas como **índice base 100**; preços nominais aparecerão apenas nos cartões e tooltips. A comparação de modelos será limitada por filtros e por uma seleção controlada de até quatro configurações, inspirada no padrão de comparação lado a lado do FuelEconomy.gov [1].

## Referência

[1]: https://www.fueleconomy.gov/feg/Find.do?action=sbsSelect "FuelEconomy.gov — Compare Side-by-Side"
