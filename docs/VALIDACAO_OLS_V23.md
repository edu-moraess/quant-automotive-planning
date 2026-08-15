# Validação do OLS Newey–West v2.3

## Escopo

Esta validação fecha a Etapa 5 do painel diagnóstico de drivers. A alteração consiste em promover, somente no `src/forecast_model.py`, a família conjunta de defasagens `y_lag1`, `y_lag2`, `y_lag3`, `y_lag6`, `y_lag9` e `y_lag12`. O forecast operacional não foi alterado: `src/analysis.py` continua sendo a fonte de verdade do Forecast Engine executado pelo aplicativo.

O painel usa a série real `TOTALSA` do FRED e as transformações materializadas de `CPIAUCSL` e `INDPRO` no feature store. O estimador é OLS com erros-padrão HAC de Newey–West. A validação usa três dobras walk-forward expansivas de seis meses, totalizando 18 resíduos OOS. O Ljung–Box OOS agrupado no lag 3 é a métrica primária de dependência serial; Durbin–Watson por dobra permanece descritivo.

## Regressores efetivos

O artefato oficial regenerado contém exatamente os seguintes regressores:

```text
y_lag1, y_lag2, y_lag3, y_lag6, y_lag9, y_lag12,
X_CPI_diff_lag1, X_CPI_diff_lag3, X_PRODIND_diff_lag2
```

O campo `descricao` do JSON lista exatamente esses itens. FEDFUNDS, GASREG, desemprego, financiamento auto, confiança do consumidor e emprego total permanecem configurados como drivers opcionais ausentes da matriz atual; eles não são apresentados como candidatos testados e descartados.

## Resultado do artefato oficial

O artefato `data/model_artifacts/model_performance_v2.json` foi regenerado pelo comando `PYTHONPATH=src python3 scripts/train_advanced_models.py` após a alteração de `TARGET_LAGS`.

| Métrica | Resultado v2.3 | Piso de aceite | Alvo nominal |
|---|---:|---:|---:|
| MAPE médio OOS | **3,1670%** | ≤ 4,00% | ≤ 2,87% |
| Cobertura P10–P90 | **88,89%** | ≥ 75% | ≥ 80% |
| Ljung–Box agrupado, lag 3 | **p=0,0805** | p ≥ 0,05 | p ≥ 0,05 |
| MAE médio | 0,5339 | — | — |
| RMSE médio | 0,6712 | — | — |
| Pinball Loss médio | 0,1689 | — | — |
| DW médio | 1,4707 | Descritivo | Descritivo |
| DW da última dobra | 1,4274 | Descritivo | Descritivo |

Os três critérios canônicos do piso foram atingidos. Consequentemente, o JSON apresenta `status_operacional: "aprovado"`, `resultado_aceite` com os três campos verdadeiros, `criterios_aceite_reprovados: []` e `todos_criterios_atingidos: true`.

Esse status significa **aprovado nos pisos de validação do painel diagnóstico**. Não significa aprovação para alimentar planejamento, risco ou forecast principal. O próprio artefato mantém `papel_no_app: "diagnostico_de_drivers"` e `nao_alimenta_forecast_principal: true`.

## Comparação controlada contra o baseline

Para evitar contaminação do braço de comparação após a promoção, o script `scripts/evaluate_joint_lags_volatility.py` passou a reconstruir explicitamente a matriz com `target_lags=[1]` para o baseline e com `target_lags=[1, 2, 3, 6, 9, 12]` para o desafiante. O método não usa R² in-sample.

| Especificação | MAE | RMSE | MAPE | WAPE | sMAPE | MASE | Ljung–Box p | Cobertura fixa |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline `y_lag1` | 0,6170 | 0,7776 | 3,6613% | 3,6781% | 3,6948% | 0,9822 | 0,0390 | 66,67% |
| Conjunta `y_lag1,2,3,6,9,12` | **0,5219** | **0,6988** | **3,0936%** | **3,1112%** | **3,1226%** | **0,8268** | **0,1070** | **75,00%** |

A especificação conjunta melhora todas as métricas de erro agregadas, eleva o p-valor do Ljung–Box acima do piso e alcança exatamente o piso de cobertura fixa. O resultado sustenta a promoção **dentro do painel diagnóstico**. O MAPE conjunto de 3,0936% ainda não alcança o alvo nominal exploratório de 2,87%, e a cobertura de 75,00% ainda não alcança o alvo nominal de 80%.

A diferença entre o MAPE 3,1670% do artefato oficial e o MAPE 3,0936% da tabela comparativa é intencional e documentada: o primeiro é a média dos MAPE das três dobras no contrato `walk_forward_ols`; o segundo é a métrica agregada sobre os 18 pontos OOS usada no experimento comparativo. Ambos usam os mesmos dados, dobras e família de lags, mas agregam os erros de maneira diferente.

## Intervalos e volatilidade

A calibração fixa prequential da comparação conjunta apresentou cobertura de 75,00% em 12 observações avaliadas e Pinball Loss de 0,1669. A alternativa condicionada à volatilidade apresentou cobertura de 58,33% e Pinball Loss de 0,1750. Portanto, a abordagem fixa permanece o padrão do painel; a calibração condicional não foi promovida.

O ARCH por dobra permanece reportado como diagnóstico obrigatório. No artefato v2.3, os p-valores de ARCH no treino são inferiores a 0,05 nas três dobras, indicando heterocedasticidade condicional ou especificação de média ainda não totalmente absorvida. Essa evidência é interpretativa e não altera o critério primário de aceite, que continua sendo o Ljung–Box OOS agrupado.

## Papel arquitetural e interface

A auditoria por imports e chamadas confirma que `forecast_model.py` é chamado pelo script de treinamento e pelo expander de drivers da interface. Ele não é importado nem chamado por `analysis.py`, `risk_engine.py`, `robust_planning.py` ou `decision_intelligence.py` como parte da cadeia operacional.

A UI passou a exibir duas informações simultâneas: o artefato está **aprovado nos pisos diagnósticos** e o OLS **não alimenta forecast, planejamento ou risco**. Essa separação evita que a palavra “aprovado” seja interpretada como promoção operacional.

## Reprodutibilidade

```bash
cd /home/ubuntu/quant_automotivo_streamlit
PYTHONPATH=src python3 scripts/train_advanced_models.py
PYTHONPATH=src python3 scripts/evaluate_joint_lags_volatility.py
pytest -q
ruff check .
ruff format --check .
```

## Referências

[1]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/src/forecast_model.py "Implementação do OLS Newey–West v2.3"

[2]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/data/model_artifacts/model_performance_v2.json "Artefato oficial de desempenho OLS v2.3"

[3]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/data/model_artifacts/joint_lags_volatility_backtest.json "Backtest comparativo dos lags conjuntos"

[4]: https://fred.stlouisfed.org/series/TOTALSA "FRED TOTALSA"

[5]: https://fred.stlouisfed.org/series/CPIAUCSL "FRED CPIAUCSL"

[6]: https://fred.stlouisfed.org/series/INDPRO "FRED INDPRO"
