# Diagnóstico da Regressão com Defasagens Operacional

## Escopo

Esta análise investiga o modelo que efetivamente vence o benchmark operacional em `src/analysis.py` e alimenta o forecast usado por planejamento, Monte Carlo, risco e Decision Intelligence. O modelo é uma Ridge com `alpha=1`, defasagens `lag_1` e `lag_12`, tendência e dummies mensais.

O protocolo usa o snapshot real versionado `data/TOTALSA_snapshot.csv`, quatro dobras walk-forward expansivas de seis meses e 24 previsões OOS. Os pisos e alvos de aceite seguem a política canônica em [`docs/POLITICA_ACEITE_MODELOS.md`](POLITICA_ACEITE_MODELOS.md). A cobertura prequential é calculada exatamente no contrato da interface: as três últimas dobras são avaliadas contra resíduos OOS de dobras anteriores, totalizando 18 observações pontuadas. Nenhum R² in-sample foi usado para seleção ou aceite.

O script reproduzível está em [`scripts/diagnose_operational_lagged_regression.py`](../scripts/diagnose_operational_lagged_regression.py), e o artefato bruto em [`operational_lagged_regression_diagnostics.json`](../data/model_artifacts/operational_lagged_regression_diagnostics.json).

## Contexto do benchmark operacional

A Regressão com defasagens foi selecionada pelo `run_backtest()` como vencedora do benchmark de quatro candidatos:

| Modelo | MAPE médio | RMSE médio | WAPE médio | sMAPE médio | MASE médio |
|---|---:|---:|---:|---:|---:|
| **Regressão com defasagens** | **3,9742%** | **0,8123** | **3,9971%** | **4,0211%** | **1,0594** |
| AutoReg sazonal | 4,1933% | 0,8363 | 4,2106% | 4,2362% | 1,1145 |
| Holt-Winters | 4,2853% | 0,8731 | 4,3076% | 4,3473% | 1,1406 |
| Referência sazonal | 8,2931% | 1,5066 | 8,4046% | 8,7227% | 2,2319 |

A seleção é coerente com o código: o resumo é ranqueado por MAPE, sMAPE, WAPE, RMSE e desvio do MAPE, e não por R² in-sample.

## Diagnósticos OOS agrupados

Os 24 erros OOS do vencedor operacional foram preservados em ordem temporal. O Ljung–Box passa em lag 6, mas reprova em lag 12:

| Diagnóstico | Resultado | Interpretação a 5% |
|---|---:|---|
| Ljung–Box lag 3 — primário | p = 0,1999 | Passa o piso `p≥0,05` da política canônica |
| Ljung–Box lag 6 — diagnóstico | p = 0,1646 | Não rejeita ausência de autocorrelação conjunta até lag 6 |
| Ljung–Box lag 12 | p = 0,0251 | Rejeita ausência de autocorrelação conjunta até lag 12 |
| ARCH, lag 4 | p = 0,8123 | Não há evidência de heterocedasticidade ARCH no teste operacional agregado |
| DW descritivo | 1,0555 | Informação descritiva; não é usado como aceite isolado |
| Cobertura prequential fixa | 66,67% | Abaixo do piso de aceite 75,00% e do alvo nominal 80% |
| Pinball Loss prequential | 0,2746 | Referência para calibração |

O padrão do Ljung–Box é informativo: o p-valor permanece acima de 5% até lag 6, cai para `0,0493` em lag 7 e continua abaixo de 5% entre lags 8 e 12, chegando a `0,0251` em lag 12. O ACF OOS agrupado é `0,3997` em lag 1, `−0,3384` em lag 6, `−0,3671` em lag 7, `−0,2528` em lag 9 e `−0,2874` em lag 10. O PACF é `0,3997` em lag 1 e `−0,3322` em lag 6.

Esse padrão **não confirma uma sazonalidade anual limpa**, porque o pico não está isolado em lag 12: há dependência acumulada no bloco de lags 7–10. O `lag_12` atual captura apenas um ponto do padrão e não elimina a dependência conjunta.

## Diagnóstico por dobra

O DW é mantido apenas como descrição, enquanto ACF/PACF, viés, Ljung–Box e ARCH são examinados por dobra.

| Dobra | OOS | MAPE | DW descritivo | DW centrado | ACF(1) | PACF(1) | Erro médio |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | 08/2024–01/2025 | 2,9162% | 1,0255 | 1,1469 | 0,2219 | 0,2219 | +0,1823 |
| 2 | 02/2025–07/2025 | 4,6530% | 0,9726 | 1,7573 | 0,0966 | 0,0966 | +0,7519 |
| 3 | 08/2025–01/2026 | 4,1355% | 0,4923 | 1,1214 | 0,0714 | 0,0714 | −0,6304 |
| 4 | 02/2026–07/2026 | 4,1922% | 0,1595 | 2,5384 | −0,5126 | −0,5126 | +0,6987 |

Na dobra 4, o DW bruto baixo é quase inteiramente um efeito de nível: depois de centralizar os erros, ele sobe de `0,1595` para `2,5384`. Na dobra 3 ocorre o mesmo em menor grau. Isso reforça que o DW bruto por janela curta não deve ser critério isolado. Ao mesmo tempo, a evidência OOS agrupada em lags 7–12 continua sendo relevante e não pode ser descartada como mero efeito do DW.

Os p-valores CUSUM por dobra foram `0,6844`, `0,6852`, `0,6710` e `0,6970`. Portanto, o teste não fornece evidência de quebra estrutural global nos resíduos de treino. A conclusão é limitada ao teste: ausência de rejeição no CUSUM não prova que não existam mudanças econômicas, apenas que elas não foram detectadas por esse diagnóstico.

## Resíduos de treino e ARCH

Os testes de Ljung–Box dos resíduos de treino rejeitam ausência de autocorrelação em todas as dobras, tanto em lag 6 quanto em lag 12, com p-valores entre `0,000133` e `0,000684`. Isso indica que o ajuste interno da Ridge ainda deixa estrutura serial relevante, embora o ARCH agregado OOS não seja significativo.

A diferença entre os dois diagnósticos é importante. O Ljung–Box mede dependência serial dos resíduos; o ARCH testa dependência serial nos quadrados dos resíduos. Neste modelo operacional, há evidência de dependência serial nos resíduos, mas não há evidência suficiente de ARCH no agregado OOS. Portanto, a calibração por volatilidade não deve ser promovida automaticamente com base apenas na confirmação de ARCH no OLS diagnóstico anterior.

## Alternativas de lags

Todas as alternativas foram executadas no mesmo protocolo de quatro dobras e seis meses, com a mesma Ridge e sem R² in-sample.

| Especificação | MAPE | RMSE | MAE | WAPE | sMAPE | MASE | LB6 p | LB12 p | Cobertura fixa |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Atual: `1,12` | **3,9742%** | **0,8381** | **0,6631** | **4,0033%** | **4,0211%** | **1,0601** | **0,1646** | 0,0251 | **66,67%** |
| Somente `1` | 4,5864% | 0,9378 | 0,7639 | 4,6114% | 4,6499% | 1,2211 | 0,0267 | 0,0025 | 44,44% |
| `1,6,12` | 4,1648% | 0,8666 | 0,6937 | 4,1879% | 4,2006% | 1,1090 | 0,0605 | 0,0046 | 66,67% |
| `1,3,6,12` | 4,0434% | 0,8359 | 0,6730 | 4,0631% | 4,0846% | 1,0759 | 0,0961 | 0,0259 | 61,11% |
| `1,2,3,6,12` | 4,0401% | 0,8378 | 0,6726 | 4,0604% | 4,0820% | 1,0752 | 0,0951 | 0,0264 | 61,11% |
| `1,2,3,6,9,12` | 4,0701% | 0,8464 | 0,6774 | 4,0896% | 4,1112% | 1,0830 | 0,0900 | 0,0238 | 61,11% |

Nenhuma alternativa passa simultaneamente o piso canônico de MAPE `4,00%`, cobertura `75%` e Ljung–Box primário `lag 3, p≥0,05` com vantagem consistente sobre a configuração atual. A especificação atual `1,12` é a melhor em MAPE, RMSE, MAE, WAPE, sMAPE, MASE e cobertura fixa dentro deste conjunto: passa MAPE e Ljung–Box primário, mas falha no piso de cobertura. Os alvos nominais mais ambiciosos de MAPE `2,87%` e cobertura `80%` permanecem documentados apenas como referência exploratória. A política completa está em [`docs/POLITICA_ACEITE_MODELOS.md`](POLITICA_ACEITE_MODELOS.md).

A inclusão dos lags 6, 9 e 12 não resolve a dependência de lags 7–12. A especificação `1,3,6,12` melhora ligeiramente RMSE e MAPE em relação a `1,6,12`, mas ainda tem p-valor de `0,0259` em lag 12 e cobertura de apenas `61,11%`. A combinação com todos os lags testados é pior que a atual no MAPE e na cobertura.

## Causa raiz operacional

A causa raiz mais defensável é **dependência serial de médio alcance no bloco de lags 7–12, combinada com viés de nível em dobras específicas**, e não uma simples ausência do `lag_12` isolado nem uma quebra estrutural confirmada pelo CUSUM.

A evidência é composta por quatro fatos. Primeiro, o Ljung–Box OOS passa em lag 6 e reprova a partir de lag 7 até lag 12. Segundo, o ACF OOS mostra correlações negativas concentradas nos lags 6–10, não apenas em lag 12. Terceiro, os DWs baixos das dobras 3 e 4 sobem de forma relevante quando os erros são centralizados, mostrando que o nível médio domina parte da estatística. Quarto, nenhuma especificação de lags testada remove o p-valor de lag 12 abaixo de 5% sem piorar o desempenho pontual e a cobertura.

Não foi confirmada quebra estrutural global pelo CUSUM. Também não há evidência de ARCH no agregado OOS operacional (`p=0,8123`), portanto a calibração de volatilidade não deve ser copiada automaticamente do painel OLS diagnóstico para este modelo.

## Decisão operacional

A decisão é **manter a especificação atual `lag_1 + lag_12` por enquanto**. Ela passa o piso canônico de MAPE e Ljung–Box primário, mas falha o piso de cobertura prequential; também não atinge os alvos nominais exploratórios de MAPE e cobertura. Não há evidência suficiente para promover outra combinação de lags. A política única de aceite e a distinção entre piso e alvo estão em [`docs/POLITICA_ACEITE_MODELOS.md`](POLITICA_ACEITE_MODELOS.md).

Como o modelo alimenta estoque, backlog, Monte Carlo, VaR/CVaR e Decision Intelligence, nenhuma mudança de especificação foi aplicada ao forecast operacional nesta etapa. O próximo experimento, se autorizado, deve testar uma modelagem explícita de dependência de médio alcance — por exemplo, termos de erro ou correção de viés estimados somente com dados disponíveis antes de cada dobra — em vez de continuar adicionando lags do alvo de forma ad hoc.

## Referências

[1]: https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.acorr_ljungbox.html "Statsmodels — Ljung–Box test"
[2]: https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.het_arch.html "Statsmodels — Engle ARCH test"
[3]: https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.breaks_cusumolsresid.html "Statsmodels — CUSUM of OLS residuals"
