# Auditoria Temporal de Tabelas e DataFrames

**Escopo:** Quant Automotive Intelligence & Planning  
**Data da auditoria:** 14/08/2026  
**Critério de controle:** todos os cálculos, junções, reamostragens, previsões e gráficos permanecem com tipos temporais nativos. A conversão para texto ocorre somente em cópias destinadas à interface ou à exportação.

> **Princípio aplicado:** uma competência mensal não deve sugerir uma hora de ocorrência. Por isso, datas mensais são exibidas como `MM/AAAA`; datas diárias, como `DD/MM/AAAA`; e timestamps de auditoria que de fato registram hora permanecem como `DD/MM/AAAA HH:MM UTC`.

## Método de auditoria

A auditoria reproduziu o pipeline com os snapshots versionados, inspecionando origem, dimensões, colunas, `dtype`, exemplos temporais, duplicidades e ausências de **25 DataFrames**: 18 expostos na interface e 7 internos. O inventário reproduzível foi gravado em `temporal_table_audit.json`; o script externo empregado para a verificação está em `/home/ubuntu/audit_temporal_tables.py`.

| Camada | DataFrames auditados | Resultado |
|---|---:|---|
| Interface | 18 | 2 tabelas com formatação temporal aplicada; 16 sem coluna temporal ou somente visualização em gráfico. |
| Interna | 7 | 7 preservam `datetime64[ns]` para cálculo, forecast, diagnóstico, gráficos ou backtest. |
| Qualidade e proveniência | 1 tabela consolidada | Datas de cobertura são diárias; timestamp de modificação preserva UTC e horário. |

## Matriz de auditoria — tabelas da interface

| DataFrame / camada | Origem | Coluna temporal e dtype no baseline | Situação antes | Padrão aplicado / decisão | Status |
|---|---|---|---|---|---|
| `brand_display` | `vehicle_intelligence.brand_summary` | — | Sem campo temporal de data. | Não requer tratamento. | Conforme |
| `registry_display` | `vehicle_intelligence.brand_registry` | — | Anos-modelo numéricos, não datas. | Mantém anos como números inteiros. | Conforme |
| `energy_sensitivity` | `scenarios.energy_price_sensitivity` | — | Sem coluna temporal. | Não requer tratamento. | Conforme |
| `energy_display` | `energy_intelligence.energy_summary` | — | Sem coluna temporal. | Não requer tratamento. | Conforme |
| `strong_pairs` | `energy_intelligence.strongest_spearman_pairs` | — | Sem coluna temporal. | Não requer tratamento. | Conforme |
| `market_summary` | `analysis.run_backtest` | — | Métricas agregadas por modelo. | Não requer tratamento. | Conforme |
| `ljung_box` | `analysis.run_backtest` | — | Diagnóstico agregado por defasagem. | Não requer tratamento. | Conforme |
| `diagnostics_display` | Construção local da interface | — | Diagnósticos escalares. | Não requer tratamento. | Conforme |
| `econometric_coefficients` | Artefato `econometric_coefficients.csv` | — | Coeficientes sem data. | Não requer tratamento. | Conforme |
| `econometric_validation` | Artefato `econometric_validation.csv` | `data`; carregada como `datetime64[ns]` na interface | Usada exclusivamente no gráfico de validação. | Mantida nativa para eixo temporal; não há tabela exposta. | Conforme |
| `econometric_vif` | Artefato `econometric_vif.csv` | — | Sem coluna temporal. | Não requer tratamento. | Conforme |
| `neural_importance` | Artefato `neural_permutation_importance.csv` | — | Sem coluna temporal. | Não requer tratamento. | Conforme |
| `neural_error_by_powertrain` | Artefato `neural_error_by_powertrain.csv` | — | Sem coluna temporal. | Não requer tratamento. | Conforme |
| `neural_validation` | Artefato `neural_efficiency_validation.csv` | — | Ano-modelo numérico, não data. | Mantém ano-modelo como inteiro. | Conforme |
| `scenario_display` | `planning.build_scenario_table` | — | Cenários agregados, sem data. | Não requer tratamento. | Conforme |
| `plan_display` | Plano mensal da otimização | `data`; `datetime64[ns]`, exemplo `2026-08-01 00:00:00` | A tabela e o CSV poderiam expor meia-noite sem significado analítico. | Cópia visual de `Data` em `MM/AAAA`; plano interno permanece temporal. | Corrigido |
| `source_table` | Construção local da interface | — | Sem coluna temporal. | Não requer tratamento. | Conforme |
| `health_display` | `data_health.json` | `period_start`, `period_end`, `last_observation`, `snapshot_modified_utc`; texto ISO | Coberturas e timestamp podiam aparecer no formato bruto do arquivo. | Cobertura em `DD/MM/AAAA`; modificação em `DD/MM/AAAA HH:MM UTC`. | Corrigido |

## Matriz de auditoria — DataFrames internos

| DataFrame | Origem | Temporalidade observada | Decisão de tratamento | Status |
|---|---|---|---|---|
| `market_history` | `analysis.prepare_data` | `data: datetime64[ns]`; série mensal, 607 observações. | Mantido nativo: alimenta diagnóstico, forecast e gráficos. | Preservado |
| `forecast` | `analysis.make_forecast` | `data: datetime64[ns]`; horizonte mensal. | Mantido nativo: alimenta cenários e planejamento. | Preservado |
| `price_index` | `energy_intelligence.energy_price_index` | `data: datetime64[ns]`; índice mensal. | Mantido nativo: alimenta gráfico temporal. | Preservado |
| `price_latest` | `energy_intelligence.latest_energy_snapshot` | `data: datetime64[ns]`; última competência por energia. | Indicadores chamam `fmt_month_display`; fonte interna não é modificada. | Corrigido na apresentação |
| `stl` | `analysis.compute_diagnostics` | `data: datetime64[ns]`; decomposição mensal. | Mantido nativo: artefato analítico interno. | Preservado |
| `fold_details` | `analysis.run_backtest` | `treino_ate`, `teste_de`, `teste_ate: datetime64[ns]`. | Mantido nativo: metadado de validação temporal. | Preservado |
| `oos_predictions` | `analysis.run_backtest` | `data: datetime64[ns]`; previsões fora da amostra. | Mantido nativo: calibração e avaliação. | Preservado |

## Implementação e contrato

A centralização foi implementada em `src/presentation.py` por meio de quatro funções: `fmt_month_display`, `fmt_date_display`, `fmt_datetime_utc_display` e `format_temporal_display`. A última recebe um DataFrame, devolve uma cópia visual e não altera a referência usada por qualquer cálculo.

| Contexto | Formato final | Exemplo |
|---|---|---|
| Competência mensal | `MM/AAAA` | `08/2026` |
| Data diária / cobertura | `DD/MM/AAAA` | `14/08/2026` |
| Timestamp de auditoria em UTC | `DD/MM/AAAA HH:MM UTC` | `14/08/2026 11:02 UTC` |
| Dado ausente | `—` | `—` |

Os testes em `tests/test_temporal_formatting.py` verificam a remoção de `00:00:00` de competências mensais e datas diárias, a preservação do horário em timestamps UTC, o marcador de ausência e, sobretudo, a preservação de `datetime64` no DataFrame de origem.

## Resultado

A ocorrência material identificada foi a coluna mensal `plan_display["Data"]`, cuja amostra nativa era `2026-08-01 00:00:00`. Ela passou a ser exibida e exportada como `08/2026`. As colunas de saúde e proveniência agora comunicam claramente a diferença entre uma **data de cobertura** e um **registro de auditoria com horário real**. Nenhum timestamp interno foi convertido antes de etapas analíticas.

A validação posterior registrou **35 testes aprovados**, além de `ruff check .` e `ruff format --check .` sem pendências.
