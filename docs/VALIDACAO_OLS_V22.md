# Validação do OLS Newey–West v2.2

## Escopo

Esta validação documenta a alteração da matriz de regressão mensal do `src/forecast_model.py` e a posterior materialização das duas séries macroeconômicas definidas para o modelo. O contrato mantém `y_lag1`, drivers macroeconômicos em lags point-in-time e três transformações estacionárias: `CPI_diff_lag1`, `CPI_diff_lag3` e `PRODIND_diff_lag2`.

A série de mercado é `TOTALSA` do FRED, que representa vendas agregadas de veículos leves nos Estados Unidos, não vendas por marca [1]. As séries macroeconômicas são `CPIAUCSL`, Consumer Price Index for All Urban Consumers: All Items in U.S. City Average, índice 1982–1984 = 100 e frequência mensal, e `INDPRO`, Industrial Production: Total Index, índice 2017 = 100 e frequência mensal [2] [3].

> **Papel no aplicativo.** O OLS Newey–West v2.2 é um artefato de diagnóstico de drivers e autocorrelação. Ele não alimenta o forecast principal nem o planejamento operacional. O forecast usado pelo app é a Regressão com defasagens implementada em `src/analysis.py` e registrada no Forecast Engine; o OLS aparece na seção de drivers para interpretação econométrica. A auditoria por imports e chamadas efetivas não encontrou uso de `forecast_model.py` em Forecast Engine, Risk Engine, Scenario Engine, Decision Intelligence ou Robust Planning.

## Materialização do feature store

As séries foram baixadas do endpoint público `fredgraph.csv` do FRED e persistidas segundo o contrato Parquet do projeto. Cada observação foi convertida para o esquema `data`, `disponivel_em`, `serie`, `feature` e `valor`. Como o sandbox não possui `FRED_API_KEY`, não havia `realtime_start` autenticado; portanto, a data da observação foi usada como fallback conservador de disponibilidade, explicitamente registrado no manifesto e em `data/feature_store/fred_macro_refresh.json`.

| Série | Feature interno | Observações materializadas | Cobertura |
|---|---|---:|---|
| `CPIAUCSL` | `cpi` | 606 | 1976-01 a 2026-07 |
| `INDPRO` | `producao_industrial` | 606 | 1976-01 a 2026-06 |
| `TOTALSA` preservado localmente | `vendas_saar_milhoes` | 19 | 2025-01 a 2026-07 |

O agregado `source=feature_builder` foi reconstruído para 607 meses e passou a conter `cpi`, `producao_industrial`, `CPI_diff`, `CPI_diff_lag1`, `CPI_diff_lag3`, `PRODIND_diff` e `PRODIND_diff_lag2`. As primeiras observações ficam naturalmente ausentes nas transformações por diferença e defasagem; essas linhas são removidas pela matriz OLS antes do treinamento.

## Comparação com o backup v2.1

O JSON anterior foi preservado em `data/model_artifacts/model_performance_v2_backup.json`. Após a materialização, o treinamento oficial passou a utilizar os três regressores macroeconômicos diferenciais e a matriz final resultou em 599 observações.

| Métrica | Backup v2.1 | OLS v2.2 com FRED real | Diferença |
|---|---:|---:|---:|
| MAPE médio | 3,5670% | 3,6460% | +0,0790 pp |
| Desvio do MAPE | 1,1397 pp | 0,7814 pp | −0,3583 pp |
| MAE médio | 0,5926 | 0,6144 | +0,0218 |
| RMSE médio | 0,7249 | 0,7491 | +0,0242 |
| Durbin–Watson médio | 1,4258 | 1,5700 | +0,1442 |
| Durbin–Watson da dobra 3 | 0,5622 | **1,9211** | **+1,3589** |
| Cobertura P10–P90 | 83,33% | **88,89%** | **+5,56 pp** |
| Pinball Loss médio | 0,1903 | 0,1923 | +0,0020 |

## Resultado por dobra

| Dobra | MAPE | RMSE | Durbin–Watson | Cobertura P10–P90 |
|---:|---:|---:|---:|---:|
| 1 | 4,7506% | 1,0189 | 0,9969 | 83,33% |
| 2 | 3,0655% | 0,6589 | 1,7920 | 83,33% |
| 3 | 3,1220% | 0,5695 | **1,9211** | 100,00% |
| **Média** | **3,6460%** | **0,7491** | **1,5700** | **88,89%** |

A meta específica de DW médio igual ou superior a 1,72 ainda não foi atingida, mas o problema mais severo foi corrigido: a última dobra passou de 0,5622 para 1,9211. A cobertura também superou o mínimo de 75%. O MAPE médio ficou acima da meta agressiva de 2,87% e ligeiramente acima do backup; portanto, a evolução v2.2 melhora a estrutura residual e a cobertura, mas não deve ser apresentada como superior em todas as dimensões preditivas.

## Regressores efetivamente utilizados

O artefato `data/model_artifacts/model_performance_v2.json` registra os regressores presentes na matriz, evitando confundir features implementadas com features realmente disponíveis no treinamento. O campo `descricao` contém somente a lista do array `regressores`, sem drivers candidatos adicionais. O campo `candidatos_avaliados_e_nao_selecionados` permanece vazio, porque o código atual não executa uma seleção stepwise documentada. Os drivers opcionais que não materializaram colunas são registrados separadamente em `drivers_configurados_mas_ausentes_na_matriz`. Quando o critério de aceite falha, o artefato também registra `status_operacional: nao_aprovado` e os critérios reprovados.

| Regres­sor | Papel |
|---|---|
| `y_lag1` | Persistência mensal da demanda agregada |
| `X_CPI_diff_lag1` | Variação percentual do CPI com uma defasagem |
| `X_CPI_diff_lag3` | Variação percentual do CPI com três defasagens |
| `X_PRODIND_diff_lag2` | Variação percentual da produção industrial com duas defasagens |

**Candidatos avaliados e não selecionados:** nenhum persistido. **Drivers configurados, mas ausentes da matriz:** FEDFUNDS lag-2, GASREG lag-1, Desemprego lag-1, Financiamento auto lag-1, Confiança do consumidor lag-1 e Emprego total lag-1. A ausência indica indisponibilidade das colunas no feature store nesta execução, não rejeição estatística documentada.

## Diagnóstico de multicolinearidade

Os VIFs calculados sobre a matriz com dados reais ficaram baixos e não indicam colinearidade severa entre a defasagem do target e as diferenças macroeconômicas. A seleção não remove variáveis apenas por um limiar mecânico; estabilidade temporal, interpretação econômica e desempenho fora da amostra continuam sendo avaliados em conjunto.

| Regres­sor | VIF |
|---|---:|
| `y_lag1` | 2,073 |
| `X_CPI_diff_lag1` | 2,183 |
| `X_CPI_diff_lag3` | 2,171 |
| `X_PRODIND_diff_lag2` | 1,044 |

## GLSAR como contingência

GLSAR iterativo AR(1) permanece implementado e comparável no mesmo walk-forward. No cenário oficial agora materializado, o backtest GLSAR apresentou DW médio de 1,6351, DW de 2,1210 na terceira dobra, MAPE médio de 3,5833% e cobertura de 83,33%. Ele melhora o DW e o MAPE em relação ao OLS v2.2, mas reduz a cobertura probabilística. A decisão atual é manter Newey–West como estimador principal e GLSAR como plano B explícito, sem substituir o modelo principal por uma única métrica. A investigação por ACF/PACF, CUSUM, teste de `y_lag12`, DW centrado e comparação clássico/HAC está documentada em [`docs/DIAGNOSTICO_AUTOCORRELACAO_OLS.md`](DIAGNOSTICO_AUTOCORRELACAO_OLS.md). A conclusão foi refinada: o DW OOS da primeira dobra é instável por viés de nível e erro extremo em horizonte curto, mas os testes de Ljung–Box e ARCH nos resíduos de treino rejeitam fortemente ausência de dependência serial e variância constante em todas as dobras. Não foi confirmada sazonalidade ausente suficiente nem quebra estrutural estatisticamente demonstrada.

> A evolução v2.2 está validada quanto à disponibilidade das séries e à correção da autocorrelação da última dobra: o DW subiu de 0,5622 para 1,9211. O critério agregado completo ainda requer melhoria adicional do DW médio e do MAPE.

## Reprodutibilidade

A materialização pode ser reproduzida por `PYTHONPATH=src python3 scripts/materialize_fred_macro.py`. O treinamento oficial é executado por `PYTHONPATH=src python3 scripts/train_advanced_models.py`. O JSON atualizado contém a especificação, os regressores efetivos, o papel no aplicativo, as métricas por dobra e os critérios de aceite. O backup v2.1 permanece preservado para comparação.

## Referências

[1]: https://fred.stlouisfed.org/series/TOTALSA "FRED — Total Vehicle Sales"
[2]: https://fred.stlouisfed.org/series/CPIAUCSL "FRED — Consumer Price Index for All Urban Consumers: All Items"
[3]: https://fred.stlouisfed.org/series/INDPRO "FRED — Industrial Production: Total Index"
[4]: https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.GLSAR.html "Statsmodels — GLSAR"
