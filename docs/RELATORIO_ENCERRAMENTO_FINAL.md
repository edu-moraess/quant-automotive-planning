# Relatório de encerramento final

## Síntese executiva

O projeto `Quant Automotive Intelligence & Planning` está tecnicamente fechado no escopo das cinco etapas originais e possui um registro adicional de encerramento final. O repositório público está publicado na branch `main`, com o commit final [`840d544`](https://github.com/edu-moraess/quant-automotive-planning/commit/840d544). A auditoria final encontrou a branch sincronizada com `origin/main`, sem alterações locais pendentes, e confirmou que o repositório é público.

A arquitetura mantém uma separação essencial entre o **forecast operacional**, que alimenta planejamento e risco, e o **OLS Newey–West**, que atua como painel explicativo de drivers. O OLS v2.3 foi validado nos pisos estatísticos do painel diagnóstico. O forecast operacional atual continua aprovado em MAPE e Ljung–Box primário, mas não passa o piso de cobertura prequential; portanto, não deve ser descrito como completamente validado.

> Conclusão de governança: o painel diagnóstico OLS está validado para interpretação econométrica; o forecast operacional continua em uso com uma limitação explícita de cobertura, sem promoção de correções não comprovadas.

## Estado do repositório

| Item | Resultado final |
|---|---|
| Repositório | `edu-moraess/quant-automotive-planning` |
| Visibilidade | Público |
| Branch padrão | `main` |
| Commit final | `840d544` |
| Sincronização local/remota | `HEAD = origin/main` |
| Alterações locais pendentes | Nenhuma |
| Qualidade automatizada | 85 testes aprovados; Ruff limpo; formatação válida; compilação válida |
| Smoke test Streamlit | HTTP 200 em porta livre 8511 |

A porta 8501 estava ocupada por uma instância preexistente do Streamlit. Para não interromper esse processo, o encerramento executou uma segunda instância isolada na porta 8511, que iniciou sem erro e respondeu HTTP 200. O processo temporário foi encerrado ao final do teste.

## Fontes e escopo de dados

A plataforma usa snapshots reais e rastreáveis, sem dados simulados para os resultados publicados. A série de mercado é `TOTALSA` do FRED, agregada e mensal. O catálogo EPA contém configurações técnicas de veículos e suporta análises por marca, modelo, segmento, combustível e tecnologia, mas não mede vendas ou participação comercial. O feature store contém as séries macroeconômicas materializadas `CPIAUCSL` e `INDPRO`; os preços de energia são mantidos em snapshots próprios com origem EIA, FRED ou BLS conforme a série.

A separação entre mercado agregado e produto técnico continua obrigatória: nomes de marcas são provenientes do campo `make` da EPA, enquanto a série FRED não possui vendas por marca. O aplicativo não converte filtros EPA em participação de mercado nem apresenta configurações técnicas como unidades vendidas.

## Resultados finais dos modelos

| Camada | Especificação | MAPE | Cobertura P10–P90 | Ljung–Box OOS lag 3 | Status |
|---|---|---:|---:|---:|---|
| Painel OLS v2.3 | Lags conjuntos 1, 2, 3, 6, 9, 12 + CPI/INDPRO | 3,1670% | 88,89% | p=0,0805 | Validado para diagnóstico |
| Backtest comparativo dos lags | Agregado sobre 18 pontos OOS | 3,0936% | 75,00% | p=0,1070 | Passa os três pisos diagnósticos |
| Forecast operacional | Ridge `lag_1 + lag_12` | 3,9742% | 66,67% | p=0,1999 | Em uso; cobertura abaixo do piso |

A política única define como pisos MAPE ≤ 4,00%, cobertura ≥ 75% e Ljung–Box agrupado no lag 3 com p ≥ 0,05. Os alvos nominais exploratórios permanecem em MAPE ≤ 2,87% e cobertura ≥ 80%. O OLS v2.3 passa os pisos, mas não atinge o alvo nominal de MAPE. O backtest conjunto passa os pisos, alcançando exatamente 75% de cobertura. O modelo operacional passa MAPE e dependência serial primária, porém permanece em 66,67% de cobertura.

O Durbin–Watson por dobra foi rebaixado a métrica descritiva, pois seis observações por dobra são insuficientes para tratá-lo como critério binário estável. ARCH e CUSUM continuam diagnósticos obrigatórios e reportados.

## Decisões metodológicas encerradas

A Etapa 1 documentou `src/forecast_engine.py` como **planejado, não integrado**, mantendo `src/analysis.py` como fonte de verdade operacional. A Etapa 2 centralizou a política de aceite em `src/acceptance_policy.py` e separou pisos empíricos de alvos nominais. A Etapa 3 testou correções AR(1) de resíduos e viés recente no modelo operacional sem promover nenhuma alteração. A Etapa 4 formalizou a não promoção e confirmou que não era necessário recalcular Risk Engine, VaR, CVaR, Robust Planning ou Decision Intelligence. A Etapa 5 promoveu os lags conjuntos somente no painel diagnóstico OLS e regenerou o artefato oficial v2.3.

O resultado da Etapa 3 permanece importante: a correção AR(1) reduziu o MAPE apenas marginalmente, não melhorou a cobertura e elevou levemente o RMSE; a correção de viés recente piorou MAPE, RMSE, cobertura e dependência nos lags mais longos. A dependência residual de médio alcance, especialmente nos lags 7–12, permanece uma limitação conhecida do forecast operacional.

## Arquitetura operacional confirmada

A cadeia efetivamente chamada pelo aplicativo é:

```text
analysis_module.run_backtest
→ analysis_module.make_forecast
→ analysis_module.build_production_plan
→ run_risk_engine
→ optimize_under_uncertainty
→ build_decision_intelligence
```

O `forecast_model.py` é chamado pelo script de treinamento e pelo expander de drivers da interface. Ele não alimenta diretamente `analysis.py`, `risk_engine.py`, `robust_planning.py` ou `decision_intelligence.py`. O status “aprovado” do JSON v2.3 significa aprovação dos pisos do painel diagnóstico, não autorização para substituir essa cadeia.

## Validação da interface e qualidade

O smoke test final iniciou o Streamlit em uma porta livre e recebeu resposta HTTP 200. A suíte completa executou 85 testes aprovados, com nove warnings já conhecidos do PuLP relacionados à normalização de nomes de restrições; não houve falha funcional. Ruff não reportou problemas, todos os arquivos estavam formatados e `compileall` concluiu sem erro.

A interface foi alinhada ao resultado: o painel OLS informa aprovação nos pisos diagnósticos quando aplicável, mas mantém a mensagem de que não alimenta forecast, planejamento ou risco. O README, a auditoria de integração, o backtest de lags, o artefato v2.3 e a validação OLS v2.3 estão consistentes entre si.

## Limitações remanescentes

A principal limitação é a cobertura prequential do forecast operacional, que permanece em 66,67% contra o piso de 75%. O Ljung–Box no lag 12 do baseline também permanece abaixo de 0,05, embora o lag 3 primário passe. A calibração condicional à volatilidade testada no painel conjunto reduziu a cobertura para 58,33% e, por isso, a abordagem fixa continua padrão.

A janela OOS possui poucos pontos para decisões de alta granularidade. O resultado atual é suficiente para governança e comparação transparente, mas não justifica declarar que o forecast operacional alcançou o alvo nominal de 80% de cobertura ou que a dependência de longo alcance foi resolvida.

## Recomendações futuras

A próxima evolução deve concentrar-se no forecast operacional, não em novas alterações cosméticas do OLS diagnóstico. Qualquer nova especificação deve ser testada com walk-forward isolado contra `lag_1 + lag_12`, preservando MAPE, RMSE, cobertura, Pinball Loss e Ljung–Box agrupado. Uma janela OOS mais longa deve ser priorizada antes de calibrar variância condicional ou promover novos drivers macroeconômicos.

Nenhuma dessas recomendações foi aplicada neste encerramento. O estado publicado é reproduzível, auditável e adequado para apresentação acadêmica e técnica, desde que a distinção entre **painel diagnóstico validado** e **forecast operacional ainda limitado em cobertura** seja preservada.

## Referências

[1]: https://github.com/edu-moraess/quant-automotive-planning "Repositório público do projeto"

[2]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/docs/VALIDACAO_OLS_V23.md "Validação do OLS Newey–West v2.3"

[3]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/docs/POLITICA_ACEITE_MODELOS.md "Política única de aceite"

[4]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/docs/DECISAO_ETAPA4_NAO_PROMOCAO.md "Decisão formal de não promoção operacional"

[5]: https://fred.stlouisfed.org/series/TOTALSA "FRED TOTALSA"

[6]: https://www.fueleconomy.gov/feg/download.shtml "EPA Fuel Economy Data"
