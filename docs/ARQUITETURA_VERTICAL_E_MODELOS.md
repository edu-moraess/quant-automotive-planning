# Arquitetura Vertical e Modelos Integrados

## Regra de interface

> Cada bloco ocupa a largura disponível e aparece **depois** do anterior. A plataforma não coloca gráficos, tabelas, cards de métrica ou painéis analíticos lado a lado.

A interface deixa de otimizar para telas largas e passa a priorizar leitura sequencial. Uma aba terá uma sequência de: pergunta, indicador, gráfico, interpretação e detalhe tabular. Quando houver mais de um gráfico relacionado, eles serão mostrados um abaixo do outro e nunca em uma matriz visual.

| Aba | Sequência vertical |
|---|---|
| Resumo | Estado do universo completo → forecast → amplitude de portfólio → limitações. |
| Portfólio | Métricas → posicionamento técnico → segmento → scorecard → registro temporal. |
| Energia | Preços → tendência → custo por 100 milhas → tabela de fonte → correlações → comparação de veículos. |
| Mercado | Métricas → série histórica → backtest → tabela → diagnósticos. |
| Modelos integrados | Cobertura → modelo econométrico → coeficientes → rede neural → validação → exemplos de previsão. |
| Planejamento | Métricas → demanda e produção → estoque → sensibilidade → cenários → plano mensal. |
| Método | Fontes → fórmulas → escopo → links de auditoria. |

## Universo completo

O catálogo EPA é usado integralmente, de 1984 a 2027, com 50.242 configurações. Filtros continuam disponíveis para exploração, mas o valor inicial passa a ser o intervalo completo. O antigo recorte 2025–2027 era apenas uma escolha de visualização e não uma limitação de dados.

## Modelo econométrico integrado

O modelo econométrico explica a série mensal FRED `TOTALSA` usando informações defasadas da própria demanda, tendência, sazonalidade mensal e preços de energia disponíveis no período comum das fontes. A janela de estimação começa no período em que gasolina, diesel, eletricidade e mercado têm sobreposição válida; os últimos 24 meses ficam reservados para validação cronológica.

| Elemento | Definição |
|---|---|
| Alvo | Vendas agregadas de veículos leves, em milhões SAAR (`TOTALSA`). |
| Variáveis internas | Defasagem de 1 mês, defasagem de 12 meses, tendência e mês do ano. |
| Variáveis externas | Preço nacional de gasolina, diesel e preço urbano médio de eletricidade. |
| Método | Regressão OLS com variáveis contínuas padronizadas. |
| Validação | Últimos 24 meses fora da amostra, sem embaralhamento. |
| Limite | É um modelo explicativo/nowcasting: a avaliação usa preços observados no mês, portanto não substitui a previsão operacional sem um cenário futuro de preços. |

## Rede neural de eficiência

A rede neural prevê a eficiência combinada EPA (`comb08`, MPG/MPGe) a partir de características técnicas disponíveis no catálogo completo: ano-modelo, cilindros, cilindrada, tração, segmento EPA, combustível, tecnologia alternativa, transmissão, turbo, supercharger e start-stop. Ela não usa `comb08`, consumo urbano/rodoviário, CO₂ ou custo anual como entrada, evitando vazamento direto do alvo.

| Elemento | Definição |
|---|---|
| Modelo | `MLPRegressor` com camadas ocultas 64 e 32, padronização numérica e *one-hot encoding* categórico. |
| Treinamento | Configurações de 1984–2024. |
| Validação temporal | Configurações de 2025–2027. |
| Reajuste final | Após a validação, o estimador é ajustado no catálogo completo para uso exploratório. |
| Métricas | MAE, RMSE e \(R^2\) no período de validação. |
| Limite | A previsão estima o padrão presente na base EPA; não certifica desempenho real, consumo individual ou especificações futuras não publicadas. |

## Conexão entre as camadas

O modelo econométrico conecta energia e mercado no período mensal comum. A rede neural usa a totalidade do catálogo EPA para aprender relações entre arquitetura técnica e eficiência. A camada de planejamento permanece ligada ao forecast de mercado; ela não cria vendas por marca. Dessa forma, os três datasets são utilizados integralmente sem inventar chaves de junção que as fontes não fornecem.
