# Backtest conjunto de lags e calibração de intervalos

## Escopo e protocolo

Este experimento compara a especificação OLS atual, com `y_lag1`, à especificação desafiante com os lags do alvo `y_lag1`, `y_lag2`, `y_lag3`, `y_lag6`, `y_lag9` e `y_lag12` avaliados conjuntamente. Ambas usam a mesma matriz macroeconômica real, com `CPIAUCSL` e `INDPRO` materializados no feature store, o mesmo estimador Newey–West, as mesmas três dobras expansivas de seis meses e os mesmos 18 meses OOS.

A seleção foi feita exclusivamente com métricas fora da amostra: RMSE, MAE, MAPE, WAPE, sMAPE, MASE, cobertura P10–P90, Pinball Loss e Ljung–Box agrupado dos resíduos OOS. Nenhum R² in-sample foi usado para escolher a especificação. O script reproduzível é [`scripts/evaluate_joint_lags_volatility.py`](../scripts/evaluate_joint_lags_volatility.py), e o artefato bruto é [`joint_lags_volatility_backtest.json`](../data/model_artifacts/joint_lags_volatility_backtest.json).

O teste de dependência serial usa os 18 resíduos OOS concatenados em ordem temporal, com Ljung–Box em `lag=3` e meta de aceite `p≥0,05`. O DW por dobra permanece descritivo e não participa da decisão binária, porque a primeira dobra contém apenas seis pontos, viés médio de `+0,5147` e um erro extremo que responde por `43,12%` da soma absoluta dos erros.

## Comparação agregada

| Especificação | MAE | RMSE | MAPE | WAPE | sMAPE | MASE | Ljung–Box p | Cobertura fixa |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Atual: `y_lag1` | 0,6144 | 0,7739 | 3,6460% | 3,6630% | 3,6790% | 0,9796 | 0,0376 | 66,67% |
| Conjunta: `y_lag1,2,3,6,9,12` | **0,5219** | **0,6988** | **3,0936%** | **3,1112%** | **3,1226%** | **0,8268** | **0,1070** | **75,00%** |

A especificação conjunta melhora todas as métricas pontuais agregadas e eleva o p-valor do Ljung–Box de `0,0376` para `0,1070`, passando a meta de dependência serial. A melhora relativa do MAPE foi de `0,5524` ponto percentual; apesar disso, o MAPE permanece acima da meta nominal de `2,87%`, e a cobertura fixa de `75,00%` ainda fica abaixo da meta nominal de `80%` usada neste experimento.

## Métricas por horizonte OOS

| Horizonte | MAE atual | MAE conjunto | RMSE atual | RMSE conjunto | MAPE atual | MAPE conjunto | sMAPE atual | sMAPE conjunto | MASE atual | MASE conjunto |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0,5159 | **0,4371** | 0,5159 | **0,4371** | 3,1387% | **2,7011%** | 3,1174% | **2,6702%** | 0,8214 | **0,6917** |
| 2 | 0,9263 | **0,8401** | 0,9263 | **0,8401** | 5,6499% | **5,1071%** | 5,5949% | **5,0892%** | 1,4742 | **1,3289** |
| 3 | **0,3027** | 0,3122 | **0,3027** | 0,3122 | **1,8056%** | 1,8464% | **1,8221%** | 1,8583% | **0,4819** | 0,4941 |
| 4 | 0,6246 | **0,5010** | 0,6246 | **0,5010** | 3,8010% | **3,0577%** | 3,7790% | **3,0350%** | 0,9946 | **0,7929** |
| 5 | 0,4499 | **0,2957** | 0,4499 | **0,2957** | 2,6788% | **1,7492%** | 2,7230% | **1,7764%** | 0,7165 | **0,4679** |
| 6 | **0,8672** | 0,7451 | **0,8672** | 0,7451 | 4,8022% | **4,1003%** | 5,0374% | **4,3064%** | 1,3820 | **1,1802** |

O desafiante foi melhor em quatro dos seis horizontes para todas as métricas de erro comparáveis. A especificação atual foi ligeiramente melhor no horizonte 3. A melhora não deve ser interpretada como prova definitiva de generalização: o painel OOS tem apenas 18 pontos, portanto a combinação é um desafiante forte, mas ainda precisa de uma janela temporal maior antes de receber status operacional.

## Cobertura P10–P90 e heterocedasticidade

A abordagem fixa reproduz a lógica prequential existente: o intervalo da dobra seguinte é estimado somente com resíduos OOS de dobras anteriores, usando quantis fixos `P10`, `P50` e `P90`. A variante condicionada à volatilidade usa a mesma informação disponível até o corte, mas multiplica a distância dos quantis em relação à mediana pela razão entre o desvio-padrão de uma janela recente de seis resíduos e o desvio-padrão histórico disponível, limitada ao intervalo `[0,5; 2,0]`.

| Especificação | Intervalo | Cobertura | Pinball Loss | Escalas usadas | Resultado |
|---|---|---:|---:|---|---|
| Atual | Fixo, prequential | 66,67% | 0,18255 | 1,00; 1,00 | Abaixo de 80% |
| Atual | Condicionado à volatilidade | 58,33% | 0,18252 | 1,00; 0,814 | Piora cobertura |
| Conjunta | Fixo, prequential | **75,00%** | **0,16692** | 1,00; 1,00 | Melhor, mas abaixo de 80% |
| Conjunta | Condicionado à volatilidade | 58,33% | 0,17501 | 1,00; 0,669 | Piora cobertura |

A calibração condicional não melhora a cobertura em nenhuma das duas especificações. No desafiante conjunto, ela reduz a cobertura de `75,00%` para `58,33%` e aumenta o Pinball Loss de `0,16692` para `0,17501`. No modelo atual, reduz a cobertura de `66,67%` para `58,33%`; o ganho marginal de Pinball Loss é insuficiente para compensar a deterioração da cobertura.

A decisão é manter a abordagem fixa como padrão. A variante condicionada à volatilidade permanece implementada e disponível para investigação, mas não deve ser promovida sem uma janela OOS maior e sem um método que modele a variância condicional de maneira mais estável que a razão de desvios-padrão em somente duas dobras avaliadas.

## Decisão técnica

A combinação conjunta `y_lag1, y_lag2, y_lag3, y_lag6, y_lag9, y_lag12` é o melhor desafiante observado: melhora MAE, RMSE, MAPE, WAPE, sMAPE, MASE, Ljung–Box agrupado e cobertura fixa em relação à especificação atual. Ela **passa o critério de dependência serial agrupada**, mas não passa simultaneamente MAPE e cobertura nominal de 80%.

Por governança, a combinação será mantida como **especificação desafiante validada do painel diagnóstico**, não como forecast operacional principal. O OLS continua sendo um painel explicativo de drivers, e não o motor de forecast usado pelo planejamento. A especificação oficial atual não é substituída silenciosamente: a evidência é positiva para a combinação conjunta, mas a amostra OOS de 18 pontos ainda é curta para declarar aceite operacional completo.

A abordagem de intervalo fixa permanece o padrão prequential. A calibração condicionada à volatilidade foi rejeitada nesta rodada porque não melhora a cobertura observada de `66,67%` e `75,00%`, piorando-a para `58,33%` nos dois cenários.

## Reprodutibilidade

A execução é reproduzida por:

```bash
cd /home/ubuntu/quant_automotivo_streamlit
PYTHONPATH=src python3 scripts/evaluate_joint_lags_volatility.py
```

O artefato contém o protocolo, a especificação de lags, métricas agregadas, métricas por horizonte, estatística e p-valor do Ljung–Box agrupado, cobertura prequential fixa, cobertura condicionada à volatilidade e flags de aceite. A implementação genérica está em `src/analysis.py`, nas funções `prequential_interval_quality` e `prequential_interval_quality_volatility`.

## Referências

[1]: https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.acorr_ljungbox.html "Statsmodels — Ljung–Box test"
[2]: https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.het_arch.html "Statsmodels — Engle ARCH test"
