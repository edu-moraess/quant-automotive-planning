# Etapa 3 — Correção da dependência de médio alcance

## Objetivo e decisão

Esta etapa avaliou se uma correção aplicada **após o forecast da especificação operacional atual** poderia reduzir a dependência residual associada ao médio alcance sem introduzir informação futura, piorar a acurácia ou reduzir a cobertura prequential. O modelo operacional permaneceu inalterado: Ridge com `alpha=1`, `lag_1`, `lag_12`, tendência e dummies mensais.

A decisão final é **não promover nenhuma correção**. A correção AR(1) dos erros one-step produziu uma melhora marginal de MAPE, de 3,9742% para 3,9443%, mas não melhorou a cobertura, não reduziu a dependência primária medida pelo Ljung–Box agrupado no lag 3 e ainda elevou levemente o RMSE. A correção por viés recente foi rejeitada porque piorou simultaneamente as métricas de erro, a cobertura e a dependência nos lags mais longos.

> A especificação operacional `lag_1 + lag_12` permanece como baseline. A dependência residual nos lags 7–12 é registrada como limitação conhecida e continuará sendo monitorada; não há evidência suficiente para alterar o forecast ou recalcular o Risk Engine nesta etapa.

## Protocolo de validação

O backtest utilizou o snapshot real e versionado de `TOTALSA`, com quatro dobras walk-forward de seis meses. Em cada dobra, toda estimativa auxiliar foi recalculada somente com o conjunto de treino. O horizonte total de avaliação pontual foi de 24 observações OOS; a cobertura P10–P90 foi calculada pelo protocolo prequential vigente em 18 observações, mantendo comparabilidade com o baseline operacional.

A correção AR(1) ajustou um processo aos erros one-step expansivos do treino de cada dobra. A previsão corrigida recebeu, para cada horizonte, a expectativa recursiva do erro estimado. A alternativa `bias_recent6` adicionou à previsão a média dos seis erros one-step mais recentes disponíveis no treino. Nenhuma das duas abordagens alterou os dados observados, os folds, o treinamento do Ridge ou a geração dos intervalos fixos.

| Critério | Regra da política v2026.08 |
|---|---:|
| Ljung–Box OOS agrupado primário | lag 3, p ≥ 0,05 |
| MAPE — piso de aceite | ≤ 4,00% |
| Cobertura P10–P90 — piso de aceite | ≥ 75% |
| MAPE — alvo nominal exploratório | ≤ 2,87% |
| Cobertura — alvo nominal exploratório | ≥ 80% |
| DW por dobra | Apenas descritivo |

A comparação foi feita por MAPE, MAE, RMSE, WAPE, sMAPE, MASE, cobertura prequential, Pinball Loss e Ljung–Box agrupado nos lags 3, 6 e 12. Não foi usado R² in-sample como critério de seleção.

## Resultado agregado

| Método | MAPE | MAE | RMSE | WAPE | sMAPE | MASE | Cobertura | Pinball Loss | LB3 p | LB12 p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline_current` | 3,9742% | 0,6631 | 0,8123 | 3,9971% | 4,0211% | 1,0594 | 66,67% | 0,2746 | 0,1999 | 0,0251 |
| `error_ar1` | **3,9443%** | **0,6587** | 0,8141 | **3,9698%** | **3,9942%** | **1,0524** | 66,67% | **0,2704** | 0,1911 | **0,0261** |
| `bias_recent6` | 4,8144% | 0,8006 | 0,9352 | 4,8323% | 4,8701% | 1,2787 | 38,89% | 0,3418 | 0,0932 | 0,0023 |

A correção AR(1) reduziu MAPE em apenas **0,0299 ponto percentual**, MAE em 0,0044 e Pinball Loss em 0,0043. Entretanto, aumentou o RMSE em 0,0018, não alterou a cobertura e reduziu o p-valor do Ljung–Box primário de 0,1999 para 0,1911. A diferença é marginal e não resolve a limitação de cobertura, que permanece em 66,67%, abaixo do piso de 75%.

A correção `bias_recent6` elevou o MAPE em **0,8401 ponto percentual**, aumentou o RMSE em 0,1229 e reduziu a cobertura em 27,78 pontos percentuais. Além disso, o p-valor do Ljung–Box no lag 12 caiu de 0,0251 para 0,0023. Portanto, essa alternativa é inequivocamente inferior ao baseline e fica descartada.

## Avaliação por dobra

| Método | Dobra 1 | Dobra 2 | Dobra 3 | Dobra 4 |
|---|---:|---:|---:|---:|
| `baseline_current` MAPE | 2,9162% | 4,6530% | 4,1355% | 4,1922% |
| `error_ar1` MAPE | **2,8903%** | **4,6451%** | **4,0361%** | 4,2056% |
| `bias_recent6` MAPE | 2,9285% | 4,6635% | 5,4062% | 6,2592% |

O AR(1) melhora as três primeiras dobras por pequenas margens, mas piora a quarta, que corresponde ao período mais recente do snapshot, `02/2026–07/2026`. O comportamento é compatível com uma correção de nível pequena, e não com a remoção de uma estrutura de dependência de médio alcance. Os coeficientes estimados do AR(1) ficaram próximos de `phi = -0,071` em todas as dobras, indicando uma correção curta e fraca, incapaz de representar uma persistência sazonal ou estrutural nos lags 7–12.

A alternativa de viés recente sofre com a instabilidade do sinal do erro entre dobras. As correções médias foram aproximadamente `+0,083`, `-0,003`, `+0,220` e `-0,344` milhão de unidades SAAR. A reversão de sinal e a magnitude da última correção tornam o método sensível ao regime local e explicam a deterioração na terceira e na quarta dobra.

## Critérios de aceite e decisão de promoção

| Método | LB3 | MAPE ≤ 4% | Cobertura ≥ 75% | MAPE nominal ≤ 2,87% | Cobertura nominal ≥ 80% | Decisão |
|---|---|---|---|---|---|---|
| `baseline_current` | Passa | Passa | Falha | Falha | Falha | Manter como baseline |
| `error_ar1` | Passa | Passa | Falha | Falha | Falha | Não promover |
| `bias_recent6` | Passa | Falha | Falha | Falha | Falha | Rejeitar |

A regra de seleção exigia uma melhora conjunta, sem piora material de erro ou cobertura. Nenhum método satisfez essa condição. O AR(1) não corrigiu o problema central de cobertura nem melhorou a dependência primária; o viés recente apresentou deterioração clara. Assim, **não há mudança de especificação no `src/analysis.py`**, não há alteração na cadeia `run_forecast_cached → run_planning_cached → run_risk_cached` e não há motivo para recalcular Risk Engine, Monte Carlo, VaR/CVaR, Robust Planning ou Decision Intelligence.

## Limitação conhecida e monitoramento

O resultado não demonstra que `lag_1 + lag_12` seja a especificação definitiva. Ele demonstra apenas que as duas correções pós-modelo testadas neste protocolo não entregam ganho robusto. O Ljung–Box no lag 12 permanece abaixo de 0,05 no baseline e no AR(1), enquanto o lag 3, que é a métrica primária da política, permanece acima de 0,05. Essa diferença indica uma dependência de horizonte mais longo que não foi resolvida por uma correção AR(1) curta.

A limitação será mantida no monitoramento do forecast operacional. Uma futura mudança deverá testar uma nova especificação diretamente no treinamento, com comparação walk-forward isolada, incluindo lags sazonais ou variáveis exógenas economicamente justificadas. A inclusão só poderá ser promovida se preservar a cobertura e melhorar simultaneamente o erro e a dependência fora da amostra.

## Artefatos e reprodutibilidade

O artefato bruto com todos os folds, erros, correções, métricas, diferenças contra o baseline e critérios de aceite está em [`data/model_artifacts/operational_medium_range_correction_backtest.json`](../data/model_artifacts/operational_medium_range_correction_backtest.json). O script reproduzível utilizado para gerar o resultado está em [`scripts/evaluate_operational_medium_range_correction.py`](../scripts/evaluate_operational_medium_range_correction.py).

O experimento consome a política única definida em [`src/acceptance_policy.py`](../src/acceptance_policy.py). A versão da política usada foi `2026.08`, com piso de MAPE de 4,00%, piso de cobertura de 75% e Ljung–Box agrupado no lag 3 com p-valor mínimo de 0,05.

## Referências

[1]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/data/model_artifacts/operational_medium_range_correction_backtest.json "Artefato bruto do backtest de correção de médio alcance"

[2]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/src/acceptance_policy.py "Política única de aceite de modelos"

[3]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/src/analysis.py "Fonte de verdade do forecast operacional"
