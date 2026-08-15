# Etapa 4 — Decisão formal de não promoção

## Decisão

A Etapa 4 formaliza a decisão de **não promover nenhuma correção de médio alcance ao forecast operacional**. O baseline continua sendo a especificação Ridge com `alpha=1`, `lag_1`, `lag_12`, tendência e dummies mensais implementada em `src/analysis.py`.

A decisão decorre diretamente do backtest controlado da Etapa 3. A correção AR(1) dos erros one-step reduziu o MAPE de 3,9742% para 3,9443%, mas manteve a cobertura prequential em 66,67%, abaixo do piso de 75%, e elevou o RMSE de 0,8123 para 0,8141. A correção por viés dos seis erros mais recentes reduziu a cobertura para 38,89% e elevou o MAPE para 4,8144%. Nenhuma alternativa apresentou melhora conjunta de acurácia, cobertura e dependência serial fora da amostra.

> Resultado operacional: manter o baseline `lag_1 + lag_12`; não alterar `analysis.py`; não recalcular os artefatos downstream; manter a dependência nos lags 7–12 como limitação conhecida e monitorada.

## Evidência de que o modelo operacional não mudou

O diff entre o commit anterior à Etapa 3 e o commit da Etapa 3 contém exclusivamente o artefato bruto, o relatório e o script reprodutível do experimento:

| Arquivo | Situação na Etapa 4 |
|---|---|
| `src/analysis.py` | Sem alteração |
| `src/risk_engine.py` | Sem alteração |
| `src/robust_planning.py` | Sem alteração |
| `src/decision_intelligence.py` | Sem alteração |
| `app.py` | Sem alteração |
| `data/model_artifacts/operational_lagged_regression_diagnostics.json` | Sem alteração |
| `data/model_artifacts/operational_medium_range_correction_backtest.json` | Artefato novo da avaliação, sem promoção |
| `docs/CORRECAO_DEPENDENCIA_MEDIO_ALCANCE.md` | Relatório da Etapa 3 |
| `scripts/evaluate_operational_medium_range_correction.py` | Script reprodutível |

A auditoria de chamadas confirma que a cadeia vigente permanece:

```text
analysis_module.run_backtest
→ analysis_module.make_forecast
→ analysis_module.build_production_plan
→ run_risk_engine
→ optimize_under_uncertainty
→ build_decision_intelligence
```

O experimento da Etapa 3 não é importado por `analysis.py`, `risk_engine.py`, `robust_planning.py`, `decision_intelligence.py` ou `app.py`. Ele existe apenas em `scripts/` para avaliação reproduzível e em `data/model_artifacts/` para rastreabilidade.

## Justificativa para não recalcular o Risk Engine

O Risk Engine recebe a saída do forecast e a distribuição de incerteza produzidas pela cadeia operacional vigente. Como nenhum método experimental foi promovido e nenhum parâmetro de `analysis.py` foi alterado, não existe nova especificação operacional para alimentar o Risk Engine. Recalcular Monte Carlo, VaR, CVaR, Robust Planning ou Decision Intelligence neste ponto produziria apenas uma repetição do mesmo resultado com custo computacional adicional, sem representar uma mudança metodológica.

A decisão não significa que os componentes downstream estejam validados para qualquer modelo futuro. Significa apenas que, para esta etapa, seus inputs contratuais permanecem idênticos aos publicados anteriormente. Uma futura promoção de modelo deverá obrigatoriamente gerar novos artefatos downstream e repetir os testes de integração antes de ser publicada.

## Limitação conhecida e regra de monitoramento

O baseline passa o piso de MAPE de 4,00% e o critério primário de Ljung–Box no lag 3, com p=0,1999. Ele falha o piso de cobertura prequential, com 66,67%, e apresenta Ljung–Box no lag 12 com p=0,0251. A correção AR(1) não alterou esse diagnóstico de forma material: a cobertura permaneceu em 66,67% e o p-valor do lag 12 foi 0,0261.

A evidência é compatível com uma dependência de horizonte mais longo que não é resolvida por um ajuste AR(1) curto sobre os resíduos. Essa dependência, particularmente no intervalo de lags 7–12, fica registrada como **limitação conhecida, não como critério para alterar o modelo sem novo teste**.

O monitoramento futuro deverá acompanhar a cobertura prequential, o Ljung–Box agrupado no lag 3 como métrica primária e o comportamento no lag 12 como diagnóstico secundário. Uma mudança só poderá ser promovida após backtest walk-forward isolado, comparação explícita contra o baseline e ausência de deterioração material em MAPE, RMSE, cobertura e Pinball Loss. Quando tocar o Caminho B, também deve preservar `VaR_95`, `CVaR_95`, `stockout_probability` e `expected_backlog_units`, conforme o contrato canônico em [`docs/POLITICA_ACEITE_MODELOS.md`](POLITICA_ACEITE_MODELOS.md).

## Critérios de encerramento da Etapa 4

| Critério | Resultado |
|---|---|
| Não promoção documentada | Atendido |
| Especificação operacional preservada | Atendido |
| Cadeia Risk Engine/Robust Planning/Decision Intelligence preservada | Atendido |
| Limitação nos lags 7–12 registrada | Atendido |
| Regra de preservação da cauda formalizada na política canônica | Atendido após a revisão da Etapa 2 |
| Recalculo downstream evitado por ausência de mudança de input | Atendido |
| Artefato bruto e script reproduzível publicados | Atendido |
| Testes completos | 85 aprovados |
| Ruff e formatação | Limpos |

## Referências

[1]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/docs/CORRECAO_DEPENDENCIA_MEDIO_ALCANCE.md "Relatório do backtest da Etapa 3"

[2]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/data/model_artifacts/operational_medium_range_correction_backtest.json "Artefato bruto da Etapa 3"

[3]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/src/analysis.py "Fonte de verdade do forecast operacional"

[4]: https://github.com/edu-moraess/quant-automotive-planning/commit/06584e6 "Commit de publicação da Etapa 3"
