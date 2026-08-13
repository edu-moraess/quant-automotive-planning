# Arquitetura e Metodologia

## Propósito

Esta aplicação converte o estudo do notebook original em um painel analítico interativo para **previsão de demanda e planejamento de produção automotiva**. O objetivo é demonstrar, de forma reproduzível e defensável em contexto acadêmico e de estágio, a ligação entre uma série pública de mercado, seleção rigorosa de modelo temporal, quantificação de incerteza e decisão sob restrições operacionais.

> **Integridade e escopo.** O projeto é didático. A série `TOTALSA` representa vendas agregadas de veículos leves nos Estados Unidos, em taxa anual ajustada sazonalmente (SAAR), e não dados internos, objetivos comerciais, capacidades, mix de produtos ou decisões de qualquer montadora específica. As premissas operacionais são explicitamente hipotéticas e editáveis.

## Arquitetura funcional

| Camada | Implementação | Responsabilidade |
|---|---|---|
| Dados | Série `TOTALSA` do FRED, com cópia local de contingência | Obtém e padroniza a série mensal de vendas agregadas. |
| Qualidade e diagnóstico | Checagens de continuidade, duplicidade, IQR, ADF, STL e ACF/PACF | Verifica premissas e descreve dinâmica de tendência, sazonalidade e dependência temporal. |
| Modelagem | Sazonal ingênuo, Holt-Winters aditivo e Ridge com defasagens | Gera previsões concorrentes sem acesso indevido ao futuro. |
| Validação | Backtest walk-forward com janela expansiva | Seleciona o modelo por desempenho fora da amostra em múltiplos períodos. |
| Incerteza | Bootstrap empírico dos resíduos do backtest | Constrói cenários p10, base e p90 sem impor normalidade aos erros. |
| Decisão | Programação linear | Converte cenários de mercado em plano de produção sob capacidade, estoque e custo de ruptura. |
| Interface | Streamlit e Plotly | Expõe parâmetros, resultados, exportações e metodologia com clareza executiva. |

## Fluxo analítico

A aplicação realiza o fluxo abaixo a cada atualização dos parâmetros. A fonte de dados é consultada em tempo de execução e, quando indisponível, utiliza o *snapshot* versionado com o projeto para preservar a reprodutibilidade.

```mermaid
flowchart LR
    A[Dados TOTALSA] --> B[Limpeza e qualidade]
    B --> C[Diagnóstico temporal]
    C --> D[Backtest walk-forward]
    D --> E[Seleção por MAPE médio]
    E --> F[Previsão pontual]
    D --> G[Resíduos fora da amostra]
    G --> H[Bootstrap p10/p90]
    F --> I[Cenários de demanda]
    H --> I
    I --> J[Otimização de produção]
    J --> K[Plano e sensibilidade]
```

## Metodologia quantitativa

### Dados e qualidade

A análise usa a série mensal **Total Vehicle Sales (`TOTALSA`)**, disponibilizada pelo Federal Reserve Economic Data (FRED) e atribuída ao Bureau of Economic Analysis. A unidade original é milhões de veículos em uma taxa anual ajustada sazonalmente. A conversão por 12 é empregada apenas como aproximação operacional para visualização de demanda mensal; os modelos são estimados diretamente sobre a unidade oficial da série [1].

Antes da modelagem, são verificadas duplicidades, valores ausentes e continuidade temporal. Outliers são apontados pelo intervalo interquartil (IQR), mas não removidos automaticamente: em séries macroeconômicas, extremos podem refletir choques reais e informativos, como crises de oferta ou demanda.

### Diagnóstico de série temporal

O teste Dickey-Fuller aumentado (ADF) é apresentado em nível e primeira diferença para orientar a interpretação de estacionariedade. A decomposição STL separa a observação em componentes de tendência, sazonalidade e resíduo, seguindo o método proposto por Cleveland et al. [4]. As funções ACF e PACF tornam visível a dependência em defasagens, o que dá transparência à escolha de sazonalidade anual e dos *lags* utilizados.

### Modelos comparados

| Modelo | Especificação | Papel no estudo |
|---|---|---|
| Referência sazonal | Média histórica do mesmo mês, usando apenas o treino | Linha de base interpretável para impedir complexidade sem ganho mensurável. |
| Holt-Winters aditivo | Nível, tendência e sazonalidade de 12 meses | Método de suavização exponencial apropriado para padrão sazonal aproximadamente aditivo. |
| Ridge com defasagens | `lag_1`, `lag_12`, tendência linear e dummies de mês | Alternativa regularizada, com previsão recursiva multi-horizonte. |

### Validação e seleção

A seleção usa **validação cruzada temporal walk-forward** com janela expansiva. Em cada dobra, o treino contém apenas observações anteriores ao teste; portanto, não há embaralhamento nem vazamento temporal. Os modelos são comparados por MAE, RMSE e MAPE. O vencedor é aquele com menor MAPE médio entre as dobras, com o desvio-padrão reportado para contextualizar estabilidade e incerteza da comparação.

Após a seleção, os resíduos de previsões fora da amostra do modelo vencedor são agrupados. O teste de Ljung-Box avalia autocorrelação remanescente nos erros [5]. Esse resultado é uma evidência complementar, não uma prova definitiva, pois o poder estatístico depende do número de observações disponíveis.

### Previsão e incerteza

O modelo selecionado é reajustado sobre todo o histórico disponível. Para quantificar incerteza, a aplicação reamostra com reposição os resíduos do backtest e os soma à previsão pontual. Os percentis 10 e 90 da distribuição empírica formam os cenários conservador e otimista, enquanto a previsão pontual é o cenário base. O procedimento tem como referência o *bootstrap* de Efron [6] e evita impor normalidade aos erros.

### Otimização do plano de produção

A demanda de mercado em SAAR é traduzida em veículos mensais de uma carteira hipotética:

\[
D_t = \operatorname{round}\left(\frac{\text{SAAR}_t}{12} \times 1.000.000 \times s\right)
\]

em que \(s\) é a participação de mercado hipotética. A programação linear escolhe produção \(P_t\), estoque final \(I_t\) e demanda pendente \(B_t\), minimizando:

\[
\min \sum_t c_p P_t + c_i I_t + c_b B_t
\]

sujeita a:

\[
I_t - B_t = I_{t-1} - B_{t-1} + P_t - D_t
\]

\[
0 \le P_t \le \text{Capacidade}; \quad I_t, B_t \ge 0
\]

O custo de ruptura é deliberadamente parametrizado acima do custo de estocagem para priorizar nível de serviço. A aplicação avalia os cenários conservador, base e otimista, além de uma matriz de sensibilidade entre capacidade e participação de mercado.

## Limites e evolução recomendada

O painel não substitui um processo de S&OP industrial. Em uma aplicação real, devem ser integrados dados por modelo, região e planta, estoque físico, capacidade por recurso, disponibilidade de componentes, custos calibrados, restrições de fornecedores, lead times e metas de serviço. A interpretação deve enfatizar a disciplina metodológica, as hipóteses explícitas e os limites do caso, jamais sugerir que os valores representam decisões reais de uma empresa.

## Referências

[1]: https://fred.stlouisfed.org/series/TOTALSA "FRED — Total Vehicle Sales (TOTALSA)"
[2]: https://www.federalreserve.gov/releases/g17/mv_sales_sf.htm "Federal Reserve — Seasonal Factors for Motor Vehicle Sales"
[3]: https://catalog.data.gov/dataset/auto-sales "Bureau of Transportation Statistics — Auto Sales"
[4]: https://www.wessa.net/download/stl.pdf "Cleveland et al. (1990) — STL: A Seasonal-Trend Decomposition Procedure Based on Loess"
[5]: https://doi.org/10.1093/biomet/65.2.297 "Ljung & Box (1978) — On a Measure of Lack of Fit in Time Series Models"
[6]: https://doi.org/10.1214/aos/1176344552 "Efron (1979) — Bootstrap Methods: Another Look at the Jackknife"
