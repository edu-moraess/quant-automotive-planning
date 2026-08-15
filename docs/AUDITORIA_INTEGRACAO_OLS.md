# Auditoria de integração do OLS Newey–West v2.3

## Conclusão

`src/forecast_model.py` **não alimenta nenhuma camada operacional** do aplicativo. Ele é chamado pelo script de treinamento e pela seção de drivers da interface. Não há import ou chamada efetiva dele em `analysis.py`, `risk_engine.py`, `robust_planning.py` ou `decision_intelligence.py` como parte do forecast, planejamento, risco ou decisão.

O OLS v2.3 é um **painel explicativo de drivers, não utilizado no forecast operacional**. O artefato está aprovado nos pisos diagnósticos de MAPE, cobertura e Ljung–Box, mas essa aprovação não promove o modelo para a cadeia operacional.

## Evidência por grep

A busca foi feita sobre imports e chamadas, não sobre nomes de classes, docstrings ou declarações:

```bash
grep -RInE --include='*.py' \
  '(from forecast_model|import forecast_model|run_ols_forecast|build_regression_matrix|walk_forward_ols|save_performance_v2)' .
```

Resultado relevante:

```text
./scripts/train_advanced_models.py:20:from forecast_model import run_ols_forecast
./scripts/train_advanced_models.py:32:    ols = run_ols_forecast()
./app.py:1527:from forecast_model import build_regression_matrix, walk_forward_ols
./app.py:1532:    matrix = build_regression_matrix()
./app.py:1533:    results = walk_forward_ols(matrix)
```

Não foram encontrados imports ou chamadas do painel OLS nas camadas operacionais. O fluxo chamado pelo app é:

```text
app.py:258  backtest = analysis_module.run_backtest(data, n_folds, test_size)
app.py:259  forecast, simulations = analysis_module.make_forecast(data, backtest, horizon, ...)
app.py:279  return analysis_module.build_production_plan(forecast, ...)
app.py:314  result = run_risk_engine(simulations, assumptions, ...)
app.py:354  result = optimize_under_uncertainty(simulations, ...)
app.py:1041 decision_intelligence = build_decision_intelligence(...)
```

A função `make_forecast` em `src/analysis.py` seleciona entre os modelos do backtest, incluindo a Regressão com defasagens, Holt–Winters, AutoReg sazonal e referência sazonal. O `forecast_model.py` não aparece nessa cadeia.

## Regressores efetivos e campos do artefato

O campo `descricao` de `data/model_artifacts/model_performance_v2.json` contém exatamente os nove itens presentes no array `regressores`:

```json
"descricao": "Regressores usados: y_lag1, y_lag2, y_lag3, y_lag6, y_lag9, y_lag12, X_CPI_diff_lag1, X_CPI_diff_lag3, X_PRODIND_diff_lag2."
```

O campo `candidatos_avaliados_e_nao_selecionados` é uma lista vazia. Isso é intencional: o código atual não executa seleção stepwise documentada para FEDFUNDS, GASREG, desemprego, financiamento auto, confiança do consumidor ou emprego total. Esses drivers são configurados como opcionais e, quando as colunas não existem no feature store, aparecem separadamente em `drivers_configurados_mas_ausentes_na_matriz`.

A ausência desses drivers não é apresentada como rejeição estatística. Ela significa somente que não estavam disponíveis na matriz efetivamente treinada.

## Status diagnóstico e interface

O artefato v2.3 apresenta:

| Campo | Valor |
|---|---|
| `papel_no_app` | `diagnostico_de_drivers` |
| `nao_alimenta_forecast_principal` | `true` |
| `status_operacional` | `aprovado` nos pisos diagnósticos |
| `criterios_aceite_reprovados` | `[]` |
| MAPE | 3,1670% |
| Cobertura P10–P90 | 88,89% |
| Ljung–Box OOS agrupado, lag 3 | p=0,0805 |

A UI exibe o status como aprovação diagnóstica quando os três pisos são atingidos, mas mantém explicitamente a mensagem de que o OLS não alimenta forecast, planejamento ou risco. O DW por dobra continua apenas descritivo.

## Referências

[1]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/docs/VALIDACAO_OLS_V23.md "Validação do OLS Newey–West v2.3"

[2]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/data/model_artifacts/model_performance_v2.json "Artefato de desempenho OLS v2.3"
