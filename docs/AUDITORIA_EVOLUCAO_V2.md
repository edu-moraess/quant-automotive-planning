# Auditoria técnica para evolução Decision Intelligence

**Data da auditoria:** 14/08/2026  
**Repositório:** `edu-moraess/quant-automotive-planning`  
**Escopo:** Fase 0 do prompt de evolução v2. O código foi tratado como fonte de verdade; o README foi usado somente para comparar documentação e implementação.

## 1. Estado de qualidade observado

A suíte atual está verde: **55 testes aprovados**, `ruff check .` sem ocorrências e `ruff format --check .` conforme. A configuração de lint está centralizada em `pyproject.toml`, com alvo Python 3.11, regras E/F/I/B/UP e exclusão do diretório de dados.

O projeto contém 25 módulos Python em `src/`, 11 arquivos de teste e aproximadamente 6.062 linhas Python entre código, scripts e testes. As dependências instaladas já cobrem Streamlit, Pandas, NumPy, scikit-learn, statsmodels, PuLP/CBC, Plotly, httpx, tenacity, Pydantic e PyArrow; portanto, Monte Carlo, diagnóstico econométrico e otimização podem ser implementados sem introduzir uma dependência central nova.

## 2. Mapa real de responsabilidades

| Camada | Implementação atual | Observação da auditoria |
|---|---|---|
| Ingestão | `src/ingestion.py`, `src/data/sources/*` | Existem retry, timeout, cache, fallback e status, mas os contratos não são totalmente unificados entre snapshots locais e features remotas. |
| Qualidade | `src/data_quality.py` | Perfila missingness, duplicatas, gaps, outliers e hash; ainda não existe detector geral de schema drift ou SLA de staleness. |
| Features | `src/data/feature_builder.py`, `feature_store.py`, `temporal.py` | Há point-in-time e persistência Parquet, porém a matriz do OLS depende de colunas específicas do feature store e pode degradar silenciosamente para defasagens do target quando macro não está disponível. |
| Forecast principal | `src/analysis.py` | Regressão com defasagens, Seasonal Naive, Holt-Winters e AutoReg são comparados por walk-forward. É o motor mais completo para forecast probabilístico atual. |
| OLS Newey-West | `src/forecast_model.py` | É uma segunda trilha econométrica, atualmente com walk-forward fixo de 3 dobras × 6 meses e matriz dependente do feature store. Deve ser consolidada, não duplicada. |
| Modelos avançados | `src/advanced_models.py` | Econometria de energia e MLP EPA usam holdout fixo; constituem uma trilha legada que diverge do contrato walk-forward. |
| Cenários | `src/scenarios.py`, `planning.py` | Existem choques determinísticos e cenários de planejamento, mas não há objetos de cenário com probabilidade, drivers, metadados e separação formal de simulação. |
| Otimização | `src/planning.py` | PL PuLP/CBC determinística com produção regular/extra, inventário, backlog, segurança e setup opcional. Não há integração com distribuição de demanda nem risco probabilístico. |
| Decisão | `planning.decision_brief` | Regras simples Base/Stress; ainda não é uma camada formal de Decision Intelligence com confiança derivada das métricas. |
| Interface | `app.py` | Interface Streamlit funcional, vertical e com cache; ainda organizada em sete abas, não nas perguntas decisórias do prompt v2. |

## 3. Duplicidades e divergências prioritárias

### 3.1 Duas trilhas de forecasting/econometria

`analysis.py` contém o motor de candidatos com walk-forward, seleção multi-métrica e bootstrap. `forecast_model.py` contém OLS Newey-West independente, com outra matriz, outro número de dobras, outro artefato JSON e outra convenção de nomes. `advanced_models.py` mantém uma terceira trilha econométrica de energia com holdout fixo.

A prioridade arquitetural é definir um contrato único de modelo — `fit`, `predict`, `forecast`, `evaluate` e `diagnostics` — e fazer os candidatos implementarem esse contrato. A regressão de defasagem permanece o modelo principal quando vencer a validação; SARIMAX e outros métodos permanecem benchmarks comparativos, conforme o prompt.

### 3.2 Cenários determinísticos duplicados

`src/scenarios.py` aplica choques à trajetória P50 e calcula sensibilidade energética. `planning.py` repete a transformação de choques dentro de `build_scenario_table`, já acoplada ao solver. A evolução deve separar: objeto de cenário, transformação da demanda, solução operacional e resumo decisório.

### 3.3 Contrato temporal incompleto

`TimeWindow`, `enforce_point_in_time` e `assert_no_future_availability` fornecem uma base correta. Entretanto, o prompt v2 exige que toda série carregue `date, value, source, frequency, retrieved_at, dataset_version`. Esse contrato ainda não está presente de forma uniforme em snapshots, energia, veículos e artefatos de modelos.

### 3.4 Fallback silencioso controlado, mas não suficientemente explícito no modelo

A degradação FRED para `TOTALSA_snapshot.csv` é registrada na proveniência da interface. Na matriz OLS, contudo, ausência das séries macro apenas omite os regressores e permite que o pipeline rode com uma especificação menor. Isso é operacionalmente útil, mas deve ser marcado no artefato como `feature_availability`, `model_specification` e `limitation`, para impedir que resultados de especificações diferentes sejam comparados como se fossem o mesmo modelo.

## 4. Forecast e validação: estado versus alvo v2

O motor atual já possui métricas MAPE, sMAPE, WAPE, MASE, RMSE, diagnóstico ADF/KPSS/STL/ACF/PACF, walk-forward e quantis P10–P90. Os testes confirmam bootstrap reprodutível e calibração prequential.

Os gaps principais são:

1. O walk-forward atual não gera de modo centralizado uma tabela `Model × Horizon × RMSE/MAE/WAPE/sMAPE/MASE/Bias/Coverage` para horizontes 1, 3, 6 e 12 meses.
2. A seleção de lags ainda não é um experimento comparável por conjunto de lags, estabilidade de coeficientes e erro por horizonte.
3. A distribuição probabilística principal precisa ser explicitamente construída a partir dos resíduos out-of-sample por dobra; resíduos in-sample devem ser somente diagnóstico auxiliar.
4. O diagnóstico econométrico requerido pelo prompt ainda não é completo: VIF, Ljung–Box, Breusch–Pagan, ARCH, Jarque–Bera, skewness, kurtosis e Q-Q não formam um contrato consolidado.
5. O `forecast_model.py` deve ser consolidado com `analysis.py` ou claramente rebaixado a módulo especializado; manter dois pipelines independentes aumenta risco de resultados divergentes na interface.

## 5. Planejamento e risco: estado versus alvo v2

O PL existente é uma base sólida e deve ser preservado. Já possui validação de hipóteses, balanço de estoque, capacidade regular e extra, backlog, estoque de segurança, setup binário opcional e testes de cenários básicos.

Ainda não existem:

- motor independente de Monte Carlo com 5.000–10.000 simulações e `random_state` controlável;
- propagação conjunta de incerteza do forecast, market share e erro residual;
- métricas `P(stockout)`, `P(backlog > limiar)`, capacity-at-risk, VaR e CVaR;
- matriz de sensibilidade com combustível, juros, demanda, market share e capacidade;
- cenários como objetos com `scenario_id`, `drivers`, `shock`, `probability` e `metadata`;
- integração formal de cada simulação com o solver de produção ou uma aproximação explicitamente documentada;
- camada Decision Intelligence com confiança quantitativa.

## 6. UI e performance

A UI atual respeita o requisito de leitura vertical e possui caches independentes para dados principais. Os formulários laterais já foram tornados colapsáveis e o status das APIs fica no topo. O prompt v2 propõe 12 áreas decisórias; a migração deve ser incremental, evitando recalcular dados, modelos e simulações em todo rerun.

A futura UI deve separar explicitamente `Observed Data`, `Estimated Parameter`, `Model Output`, `Assumption`, `Scenario` e `Simulation`. O mercado agregado FRED não deve ser apresentado como venda por marca; a atual documentação já registra essa limitação e ela deve ser mantida.

## 7. Limitações que devem permanecer explícitas

O FRED TOTALSA é mercado agregado, não vendas por marca/modelo. O market share de 8% é uma hipótese de planejamento, não um dado observado. O catálogo EPA é técnico e não contém participação comercial. NHTSA mede eventos públicos de segurança da watchlist, não qualidade causal ou risco financeiro. A News API oferece cobertura de mídia, não vendas.

Nenhuma dessas limitações deve ser compensada com dados simulados ou conclusões de marketing. Quando não houver dado real suficiente, o sistema deve retornar `unavailable`, `assumed` ou `not_estimated` com explicação.

## 8. Ordem recomendada de implementação

A ordem técnica é: consolidar contratos e auditoria temporal; criar interface única dos modelos; ampliar walk-forward por horizonte; consolidar diagnóstico e resíduos out-of-sample; formalizar cenários e market share; adicionar Monte Carlo; adicionar risco; integrar ao PL; construir Decision Intelligence; reorganizar UI; expandir testes e documentação.

Cada etapa deve resultar em commit isolado e passar `pytest -q`, `ruff check .` e `ruff format --check .`. Nenhuma meta de métrica deve ser registrada como atingida sem executar o pipeline com a especificação e o dataset correspondentes.

## 9. Conclusão da Fase 0

A base está estável e suficientemente madura para evolução incremental. O principal risco não é falta de biblioteca ou ausência completa de modelagem; é a coexistência de trilhas parcialmente sobrepostas e a ausência das camadas probabilística, de risco e decisão. A implementação deve preservar a regressão de defasagem como modelo principal quando validada, reaproveitar o PL existente e evitar uma reescrita monolítica da aplicação.
