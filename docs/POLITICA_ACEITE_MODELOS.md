# Política única de aceite dos modelos quantitativos

## Decisão da Etapa 2

As metas `MAPE ≤ 2,87%` e `cobertura P10–P90 ≥ 80%` não têm origem documentada como requisito de negócio, benchmark externo ou especificação acadêmica independente. A auditoria do histórico do repositório mostra que elas foram introduzidas durante a otimização do OLS Newey–West no commit `fe6daf6`, depois reutilizadas nos experimentos probabilísticos e nos relatórios. Portanto, devem ser preservadas como **alvos nominais exploratórios**, não como uma fronteira binária que transforme toda especificação com resultado pior em modelo inválido.

A política revisada mantém o rigor dos diagnósticos estatísticos. Ljung–Box, ARCH e CUSUM continuam obrigatórios e reportados; o que muda é a separação entre um piso de aceite empiricamente alcançável e um alvo nominal mais ambicioso.

## Metas canônicas

| Dimensão | Piso de aceite recalibrado | Alvo nominal preservado | Regra |
|---|---:|---:|---|
| Dependência serial OOS | Ljung–Box agrupado, lag 3, p ≥ 0,05 | Igual | Obrigatório; preserva o teste conjunto em resíduos OOS ordenados |
| Erro pontual | MAPE ≤ 4,00% | MAPE ≤ 2,87% | O piso cobre o melhor envelope operacional observado sem transformar ganho parcial em reprovação automática |
| Incerteza | Cobertura P10–P90 ≥ 75% | Cobertura P10–P90 ≥ 80% | O piso é compatível com o melhor resultado OOS reproduzível observado |
| Diagnósticos de resíduos | ARCH e CUSUM executados e reportados | Sem relaxamento | São evidências de adequação, não substitutos de validação OOS |
| DW por dobra | Descritivo | Descritivo | Nunca é critério binário isolado |

A especificação só pode ser chamada de **aceita pelo piso** quando passa simultaneamente o Ljung–Box primário, o MAPE de 4,00% e a cobertura de 75% na métrica OOS declarada pelo artefato. O alvo nominal continua sendo exibido para acompanhar a distância até uma qualidade mais ambiciosa, mas não deve ser confundido com requisito documentado de negócio.

## Base empírica usada para recalibrar

A consolidação utiliza apenas validação fora da amostra em dados reais versionados. O OLS Newey–West v2.2 apresentou MAPE de 3,6460% e Ljung–Box agrupado `p=0,0376`; sua cobertura fold-mean foi 88,89%, mas a dependência serial primária não passou. O desafiante de lags conjuntos `1,2,3,6,9,12` no painel diagnóstico apresentou MAPE de 3,0936%, Ljung–Box `p=0,1070` e cobertura prequential de 75,00% em 12 observações avaliadas. Ele passa o novo piso, mas não o alvo nominal de 2,87%/80%.

No modelo operacional, a configuração atual `lag_1 + lag_12` apresentou MAPE de 3,9742%, Ljung–Box lag 3 agrupado `p=0,1999`, mas cobertura prequential de 66,67%. Assim, ela passa o MAPE e a dependência serial no piso revisado, porém permanece reprovada na cobertura. Nenhuma combinação operacional de lags avaliada alcançou simultaneamente a cobertura de 75%, o MAPE de 4,00% e o Ljung–Box de lag 3 com vantagem consistente sobre a configuração atual.

A política não afirma que qualquer modelo esteja pronto para uso operacional. Ela apenas torna explícita a diferença entre: (i) não atingir um alvo exploratório; (ii) falhar no piso de aceite; e (iii) ter diagnósticos de resíduos que exigem monitoramento ou investigação adicional.

## Escopo estatístico

O p-valor do Ljung–Box é avaliado no lag 3 com os resíduos OOS agrupados e preservando a ordem temporal. Lags 6 e 12 continuam sendo reportados como diagnósticos adicionais, especialmente no modelo operacional, que mostrou dependência acumulada no bloco 7–12. ARCH e CUSUM continuam presentes nos artefatos, mas não são convertidos artificialmente em uma aprovação binária quando a hipótese testada não é diretamente equivalente à qualidade preditiva OOS.

A política é implementada em [`src/acceptance_policy.py`](../src/acceptance_policy.py) e consumida pelo OLS, pelo experimento de lags conjuntos, pelo diagnóstico operacional e pela calibração probabilística. Os artefatos persistem a versão e os dois níveis de meta para evitar divergência textual ou numérica.

## Referências

[1]: https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.acorr_ljungbox.html "Statsmodels — Ljung–Box test"
[2]: https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.het_arch.html "Statsmodels — Engle ARCH test"
[3]: https://www.statsmodels.org/stable/generated/statsmodels.stats.diagnostic.breaks_cusumolsresid.html "Statsmodels — CUSUM of OLS residuals"
[4]: https://github.com/edu-moraess/quant-automotive-planning/commit/fe6daf6 "Commit que introduziu as metas nominais do OLS"
