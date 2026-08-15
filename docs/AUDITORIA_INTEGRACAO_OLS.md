# Auditoria de integração do OLS Newey–West v2.2

## Conclusão

`src/forecast_model.py` **não alimenta nenhuma camada operacional** do aplicativo. Ele é chamado pelo script de treinamento e pela seção de drivers da interface. Não há import ou chamada efetiva dele em `forecast_engine.py`, `risk_engine.py`, `scenario_engine.py`, `decision_intelligence.py` ou `robust_planning.py`.

O OLS v2.2 deve ser interpretado como **painel explicativo de drivers, não utilizado no forecast operacional**.

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

Não foram encontrados imports ou chamadas nas camadas operacionais. O fluxo chamado pelo app é:

```text
app.py:258  backtest = analysis_module.run_backtest(data, n_folds, test_size)
app.py:259  forecast, simulations = analysis_module.make_forecast(data, backtest, horizon, ...)
app.py:279  return analysis_module.build_production_plan(forecast, ...)
app.py:314  result = run_risk_engine(simulations, assumptions, ...)
app.py: ...   optimize_under_uncertainty(simulations, ...)
app.py:1041 decision_intelligence = build_decision_intelligence(...)
```

A função `make_forecast` em `src/analysis.py` seleciona entre os modelos do backtest, incluindo a Regressão com defasagens, Holt–Winters, AutoReg sazonal e referência sazonal. O `forecast_model.py` não aparece nessa cadeia.

## Regressores e candidatos

O campo `descricao` de `data/model_artifacts/model_performance_v2.json` contém exatamente os quatro itens presentes no array `regressores`:

```json
"descricao": "Regressores usados: y_lag1, X_CPI_diff_lag1, X_CPI_diff_lag3, X_PRODIND_diff_lag2."
```

O campo `candidatos_avaliados_e_nao_selecionados` é uma lista vazia. Isso é intencional: o código atual não executa uma seleção stepwise documentada para FEDFUNDS, GASREG, desemprego, financiamento auto, confiança do consumidor ou emprego total. Esses drivers são configurados como opcionais e, quando as colunas não existem no feature store, aparecem separadamente em `drivers_configurados_mas_ausentes_na_matriz`.

A ausência desses drivers não é apresentada como rejeição estatística. Ela significa somente que não estavam disponíveis na matriz efetivamente treinada.

## Interface

A UI usa o título **“Drivers diagnósticos — OLS Newey–West”** e exibe, em fluxo vertical:

- o papel como diagnóstico de drivers;
- a informação de que não alimenta forecast nem planejamento;
- os regressores efetivos;
- os drivers configurados, mas ausentes;
- o status dos critérios de aceite;
- a advertência de que o artefato não está aprovado para uso operacional.
