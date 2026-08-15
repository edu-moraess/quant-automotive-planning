# Status arquitetural do Forecast Engine

## Decisão

`src/forecast_engine.py` está **planejado, não integrado** à cadeia operacional atualmente executada pelo aplicativo. A fonte de verdade operacional é `src/analysis.py`.

O módulo não foi removido porque contém um contrato modular útil (`fit`, `predict`, `forecast`, `evaluate`, `diagnostics`), modelos comparativos e testes próprios. Entretanto, seus resultados não devem ser interpretados como os resultados exibidos ou consumidos pela cadeia operacional até que exista uma integração explícita, isolada e validada.

## Evidência por imports e chamadas

A busca foi executada excluindo o próprio arquivo e o diretório de testes:

```text
=== app.py ===
(sem referências)
=== src/analysis.py ===
(sem referências)
=== src/risk_engine.py ===
(sem referências)
=== src/scenario_engine.py ===
(sem referências)
=== src/decision_intelligence.py ===
(sem referências)
=== src/robust_planning.py ===
(sem referências)
=== imports fora de testes e do próprio arquivo ===
(sem imports efetivos)
```

As únicas referências externas são imports dos próprios testes em `tests/test_forecasting_engine.py`. Dentro do módulo há auto-referências normais, como `build_model_registry()`, `walk_forward_by_horizon()` e `select_model_by_evidence()`, mas elas não constituem integração com o aplicativo.

## Fonte operacional ativa

O caminho executado pelo app é:

```text
app.run_forecast_cached
→ analysis_module.run_backtest
→ analysis_module.make_forecast
→ analysis_module.build_production_plan
→ run_risk_engine
→ optimize_under_uncertainty
→ build_decision_intelligence
```

A evidência das chamadas está em `app.py:255–260`, `app.py:264–292`, `app.py:296–320`, `app.py:324–...` e `app.py:1041–1052`. O benchmark de `src/analysis.py` define e seleciona a Regressão com defasagens em `src/analysis.py:36`, `src/analysis.py:328–339` e `src/analysis.py:485–584`.

O OLS de `src/forecast_model.py` é um caminho separado: aparece no painel local de drivers em `app.py:1527–1533` e nos scripts de treinamento/auditoria. Ele não alimenta o forecast operacional, o Risk Engine, o Scenario Engine, o Decision Intelligence ou o Robust Planning.

## Regra para futura integração

Qualquer integração de `forecast_engine.py` deve ser feita em commit isolado, com comparação walk-forward contra `src/analysis.py`, recálculo de forecast probabilístico, planejamento, VaR, CVaR, probabilidade de stockout e Decision Intelligence. Até essa validação, a descrição correta é **“planejado, não integrado”**.
