# Validação do OLS Newey–West v2.2

## Escopo

Esta validação documenta a alteração da matriz de regressão mensal do `src/forecast_model.py`. O modelo mantém `y_lag1`, utiliza drivers macroeconômicos em lags point-in-time e passa a suportar CPI e produção industrial em variação percentual mensal, com `CPI_diff_lag1`, `CPI_diff_lag3` e `PRODIND_diff_lag2`. A implementação também expõe GLSAR iterativo AR(1) como contingência para resíduos persistentes.

A série de mercado é o `TOTALSA` do FRED, que representa vendas agregadas de veículos leves nos Estados Unidos, e não vendas por marca [1]. As séries macroeconômicas utilizadas na avaliação são `CPIAUCSL` e `INDPRO`, ambas provenientes do FRED [2] [3].

## Auditoria do feature store local

O feature store local utilizado pelo treinamento reproduzível contém 19 partições mensais agregadas, cobrindo 2025-01 a 2026-07. Essas partições possuem apenas a série de vendas e suas transformações de defasagem; não contêm `cpi`, `CPI_diff`, `CPI_diff_lag1`, `CPI_diff_lag3`, `producao_industrial`, `PRODIND_diff` ou `PRODIND_diff_lag2`. Por esse motivo, o artefato oficial conserva o OLS v2.2 como contrato de código, mas registra somente `y_lag1` em `regressores` e não produz ganho artificial atribuído a dados que não estavam presentes.

| Item | Resultado observado |
|---|---:|
| Partições agregadas do feature store | 19 |
| Cobertura local | 2025-01 a 2026-07 |
| Regressores macro disponíveis localmente | Nenhum |
| Regressores persistidos no artefato oficial | `y_lag1` |
| Observações da matriz OLS local | 606 |

## Comparação com o backup v2.1

O JSON foi copiado para `data/model_artifacts/model_performance_v2_backup.json` antes do treinamento. Como o feature store local não continha CPI nem produção industrial, as métricas numéricas da execução v2.2 permaneceram iguais às do backup. A mudança funcional está implementada e será ativada automaticamente quando o refresh das fontes FRED materializar as séries macro no feature store.

| Métrica | Backup v2.1 | OLS v2.2 local | Diferença |
|---|---:|---:|---:|
| MAPE médio | 3,5670% | 3,5670% | 0,0000 pp |
| RMSE médio | 0,7249 | 0,7249 | 0,0000 |
| Durbin–Watson médio | 1,4258 | 1,4258 | 0,0000 |
| Durbin–Watson da dobra 3 | 0,5622 | 0,5622 | 0,0000 |
| Cobertura P10–P90 | 83,33% | 83,33% | 0,00 pp |

## Backtest com macro FRED real

Para testar a especificação sem criar dados artificiais, foi feita uma avaliação temporária com `CPIAUCSL` e `INDPRO` reais do FRED, cobrindo 1976-01 a 2026-07. Após a aplicação dos lags e a remoção das primeiras linhas necessárias às transformações, a matriz resultou em 599 observações e incluiu os três regressores diferenciais previstos.

| Estimador | MAPE médio | RMSE médio | DW médio | DW dobra 3 | Cobertura P10–P90 | Pinball Loss |
|---|---:|---:|---:|---:|---:|---:|
| OLS Newey–West | 3,6460% | 0,7491 | 1,5700 | 1,9211 | 88,89% | 0,1923 |
| GLSAR AR(1) | 3,5833% | 0,7497 | 1,6351 | 2,1210 | 83,33% | 0,1936 |

O cenário com macro real melhora substancialmente a dobra final, cujo DW passa de 0,5622 no feature store local para 1,9211 no OLS. O GLSAR melhora adicionalmente o DW médio e a dobra final, mas perde cobertura em relação ao OLS nesse recorte. Como as métricas foram obtidas em uma avaliação temporária e o feature store oficial ainda não contém as séries, o GLSAR não foi promovido silenciosamente para o artefato principal.

## Diagnóstico de multicolinearidade

No backtest com macro FRED real, os VIFs permaneceram baixos, sem indicação de colinearidade severa entre a defasagem do target e as diferenças macroeconômicas. O valor de referência usual de atenção não é tratado como uma regra automática de exclusão; a decisão continua subordinada a estabilidade temporal, sinal econômico e desempenho fora da amostra.

| Regres­ sor | VIF |
|---|---:|
| `y_lag1` | 2,073 |
| `X_CPI_diff_lag1` | 2,183 |
| `X_CPI_diff_lag3` | 2,171 |
| `X_PRODIND_diff_lag2` | 1,044 |

## Decisão sobre GLSAR

GLSAR foi implementado e testado sob o mesmo contrato walk-forward. No ambiente local sem macroeconômicas, o GLSAR apresentou DW médio de 1,4330 e DW de 0,6235 na última dobra, portanto não resolveu a causa observada. No cenário com CPI e INDPRO reais, apresentou DW médio de 1,6351 e DW final de 2,1210, mas cobertura de 83,33% contra 88,89% do OLS. A decisão técnica é manter Newey–West como estimador principal, manter GLSAR disponível como plano B e reexecutar a seleção após a atualização oficial do feature store.

> A próxima atualização das features deve ser executada antes de qualquer conclusão sobre o ganho final de CPI e produção industrial. Sem a presença dessas séries no feature store, nenhuma alteração de especificação pode alterar retroativamente o backtest local.

## Reprodutibilidade

O treinamento oficial é executado por `python3 scripts/train_advanced_models.py`. O artefato `data/model_artifacts/model_performance_v2.json` contém a especificação, os regressores efetivos, as métricas por dobra e os critérios de aceite. O backup da execução anterior permanece em `data/model_artifacts/model_performance_v2_backup.json`.

## Referências

[1]: https://fred.stlouisfed.org/series/TOTALSA "FRED — Total Vehicle Sales"
[2]: https://fred.stlouisfed.org/series/CPIAUCSL "FRED — Consumer Price Index"
[3]: https://fred.stlouisfed.org/series/INDPRO "FRED — Industrial Production Index"
[4]: https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.GLSAR.html "Statsmodels — GLSAR"
