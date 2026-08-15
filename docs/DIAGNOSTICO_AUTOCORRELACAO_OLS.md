# Diagnóstico de autocorrelação do OLS v2.2

## Conclusão executiva

A causa raiz mais consistente do `DW=0,9969` na primeira dobra **não é uma autocorrelação positiva de primeira ordem não capturada**. A evidência aponta para uma combinação de **viés de nível no horizonte OOS curto** e um erro extremo no último mês da primeira dobra, que torna o Durbin–Watson bruto instável com apenas seis observações.

A hipótese de sazonalidade ausente foi testada com `y_lag12` e não resolveu a primeira dobra. A hipótese de quebra estrutural também não foi confirmada pelo CUSUM aplicado aos resíduos de treino. O Newey–West foi confirmado como um estimador de covariância: ele altera os erros-padrão, mas não altera parâmetros, previsões ou resíduos; portanto, não pode elevar o DW.

GLSAR melhora modestamente o DW médio e o MAPE, mas não resolve a primeira dobra e perde cobertura probabilística. A recomendação é **não promovê-lo ao forecast principal** neste momento; mantê-lo como contingência comparável no mesmo walk-forward.

## Desenho da auditoria

A matriz oficial tem 599 observações mensais, de 1976-05 a 2026-07, com `y_lag1`, três diferenças macroeconômicas defasadas e dummies mensais. O walk-forward usa três dobras expansivas de seis meses, exatamente o contrato do artefato `model_performance_v2.json`.

| Dobra | Período OOS | Treino | OLS DW | GLSAR DW |
|---:|---|---:|---:|---:|
| 1 | 2024-10 a 2025-03 | 563 meses | 0,9969 | 1,0497 |
| 2 | 2025-04 a 2025-09 | 569 meses | 1,7920 | 1,7345 |
| 3 | 2025-10 a 2026-07 | 575 meses | 1,9211 | 2,1210 |
| **Média** | — | — | **1,5700** | **1,6351** |

O diagnóstico completo e os vetores de ACF/PACF estão em `data/model_artifacts/ols_root_cause_diagnostics.json`. A execução é reproduzível por `PYTHONPATH=src python3 scripts/diagnose_ols_root_cause.py`.

## ACF/PACF por dobra

A primeira dobra não apresenta o padrão típico de uma dependência positiva persistente no erro. O ACF e o PACF no lag 1 são próximos de zero; o grande movimento está no lag 2, com sinal negativo. Como há apenas seis observações OOS, esses valores não devem ser tratados como estimativas precisas de uma função de autocorrelação de longo prazo.

| Estimador | Dobra | ACF lag 1 | PACF lag 1 | ACF lag 2 | PACF lag 2 | DW bruto | DW centrado |
|---|---:|---:|---:|---:|---:|---:|---:|
| OLS | 1 | 0,0538 | 0,0538 | −0,5034 | −0,5078 | 0,9969 | 1,3384 |
| OLS | 2 | 0,0369 | 0,0369 | −0,3187 | −0,3205 | 1,7920 | 1,8528 |
| OLS | 3 | −0,4038 | −0,4038 | −0,0105 | −0,2074 | 1,9211 | 2,2164 |
| GLSAR | 1 | 0,0633 | 0,0633 | −0,5032 | −0,5093 | 1,0497 | 1,3294 |
| GLSAR | 2 | 0,0372 | 0,0372 | −0,3221 | −0,3240 | 1,7345 | 1,8527 |
| GLSAR | 3 | −0,4309 | −0,4309 | −0,0079 | −0,2377 | 2,1210 | 2,2863 |

O sinal negativo no lag 2 da primeira dobra é incompatível com a hipótese simples de que faltaria somente um `y_lag2` para capturar autocorrelação positiva. Ele é mais compatível com uma sequência curta de erros alternados e com erro de nível.

## Influência do viés de nível e do último erro

Na primeira dobra OLS, os erros OOS foram `[0,5044, 0,5533, 0,3315, −0,9116, 0,4926, 2,1178]`. O erro médio foi **+0,5147**; o último erro respondeu por **43,12% da soma dos valores absolutos dos erros**.

| Medida OLS na dobra 1 | Valor |
|---|---:|
| DW nos seis erros | 0,9969 |
| DW após centrar os erros na média da dobra | 1,3384 |
| DW nos cinco primeiros erros | 2,0462 |
| Erro médio | +0,5147 |
| Último erro | +2,1178 |

O resultado confirma que o DW bruto está sendo penalizado por deslocamento de nível e por um ponto extremo no horizonte de seis meses. Isso não elimina o problema de previsão da primeira dobra, mas muda a interpretação: o número agregado não é evidência suficiente de que exista um processo AR(1) residual persistente.

## Hipótese (a): defasagem sazonal ausente

A série-alvo possui autocorrelação elevada em nível, com ACF aproximado de 0,898 no lag 1, 0,773 no lag 6 e 0,673 no lag 12. Isso justifica testar `y_lag12`, mas a inclusão não confirmou que a sazonalidade fosse a causa do baixo DW da primeira dobra.

| Especificação | MAPE médio | DW médio | DW dobra 1 | DW dobra 3 | Cobertura | Pinball |
|---|---:|---:|---:|---:|---:|---:|
| OLS v2.2 | 3,6460% | 1,5700 | 0,9969 | 1,9211 | 88,89% | 0,1923 |
| OLS + `y_lag12` | 3,5170% | 1,6216 | 0,9615 | 2,0896 | 88,89% | 0,1867 |
| GLSAR + `y_lag12` | 3,5197% | 1,6482 | 1,0179 | 2,1766 | 83,33% | 0,1889 |

`y_lag12` reduz o MAPE e melhora a dobra 3, mas **piora a dobra 1** e não leva o DW médio a 1,72. Portanto, a hipótese de que faltava apenas uma defasagem sazonal estrutural foi **rejeitada como causa raiz suficiente**. O teste não justifica alterar a especificação principal isoladamente; `y_lag12` pode ser mantido como candidato para um backtest futuro, não como correção já validada.

## Hipótese (b): quebra estrutural na primeira dobra

A primeira dobra cobre 2024-10 a 2025-03. O CUSUM dos resíduos de treino não rejeitou estabilidade nos três cortes OLS: p-valores de 0,6556, 0,5468 e 0,5706. No GLSAR, os p-valores foram 0,9835, 0,9413 e 0,9539. Com esses dados, **não há evidência estatística suficiente para confirmar uma quebra estrutural**.

Isso não prova que o mercado não tenha mudado; significa apenas que o diagnóstico disponível não separa uma quebra real de um erro de nível no horizonte curto. O erro positivo acumulado na primeira dobra deve ser tratado como sinal de possível mudança de regime ou viés de nível para investigação futura, não como quebra estrutural confirmada.

## Hipótese (c): efeito do Newey–West e ambição da meta de DW

No primeiro treino, OLS clássico e OLS com Newey–West apresentaram diferença máxima de **0,0** nos parâmetros e nos resíduos. O DW foi 2,3752 nos dois casos. O erro-padrão médio subiu de 0,1782 para 0,2112 com HAC.

Portanto, o Newey–West **não compensa** a autocorrelação no sentido de alterar o DW; ele corrige a inferência dos erros-padrão. A meta de DW ≥ 1,72 é útil como referência descritiva, mas é ambiciosa e instável quando calculada sobre apenas seis erros OOS brutos, especialmente na presença de viés de nível. Ela não deve ser usada sozinha para promover ou rejeitar um estimador.

## GLSAR no mesmo walk-forward

A comparação foi feita com a mesma matriz, os mesmos cortes temporais e as mesmas três dobras.

| Métrica | OLS Newey–West | GLSAR AR(1) | Diferença GLSAR − OLS |
|---|---:|---:|---:|
| MAPE médio | 3,6460% | **3,5833%** | −0,0627 pp |
| RMSE médio | **0,7491** | 0,7497 | +0,0006 |
| DW médio | 1,5700 | **1,6351** | +0,0651 |
| DW da dobra 1 | 0,9969 | 1,0497 | +0,0527 |
| DW da dobra 3 | 1,9211 | **2,1210** | +0,1999 |
| Cobertura P10–P90 | **88,89%** | 83,33% | −5,56 pp |
| Pinball Loss | **0,1923** | 0,1936 | +0,0013 |

GLSAR melhora o MAPE e o DW médio, mas mantém a primeira dobra muito abaixo de 1,72, reduz a cobertura e piora marginalmente o Pinball Loss e o RMSE. Como a causa raiz não foi identificada como AR(1) persistente e os critérios agregados continuam incompletos, **GLSAR não deve ser promovido ao forecast principal**.

## Decisão técnica

A causa raiz confirmada é **instabilidade do DW bruto na primeira dobra por erro de nível e ponto extremo em um horizonte OOS muito curto**, com ACF/PACF de lag 1 próximos de zero. Não foi confirmada uma sazonalidade ausente como explicação suficiente nem uma quebra estrutural estatisticamente demonstrada. O OLS Newey–West permanece como painel diagnóstico; GLSAR permanece como contingência e benchmark de resíduos.

O próximo experimento recomendado é avaliar uma especificação com componente de erro de nível ou dummies de regime somente se houver uma fonte real de mercado que justifique o regime, mantendo a avaliação por dobras. Não se deve adicionar `y_lag12` ou promover GLSAR apenas para elevar o DW médio.

## Referências

[1]: https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.acf.html "Statsmodels — ACF"
[2]: https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.pacf.html "Statsmodels — PACF"
[3]: https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.breaks_cusumolsresid.html "Statsmodels — CUSUM of OLS residuals"
[4]: https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.GLSAR.html "Statsmodels — GLSAR"
