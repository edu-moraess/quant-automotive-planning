# Backtest conjunto de lags e calibração de intervalos

## Escopo e protocolo

Este experimento compara explicitamente dois braços OLS construídos com a mesma matriz macroeconômica real e o mesmo protocolo walk-forward: o baseline `y_lag1` e a especificação conjunta `y_lag1`, `y_lag2`, `y_lag3`, `y_lag6`, `y_lag9` e `y_lag12`. O script reconstrói cada matriz com `target_lags` explícito para evitar que a promoção da família conjunta contamine o braço baseline.

Ambos usam Newey–West, três dobras expansivas de seis meses e 18 observações OOS. A seleção usa RMSE, MAE, MAPE, WAPE, sMAPE, MASE, cobertura P10–P90, Pinball Loss e Ljung–Box agrupado. Nenhum R² in-sample é usado. O script reproduzível é [`scripts/evaluate_joint_lags_volatility.py`](../scripts/evaluate_joint_lags_volatility.py), e o artefato bruto é [`joint_lags_volatility_backtest.json`](../data/model_artifacts/joint_lags_volatility_backtest.json).

O teste de dependência serial usa os 18 resíduos OOS concatenados em ordem temporal, com Ljung–Box em `lag=3` e piso `p≥0,05`. O DW por dobra é descritivo, pois a janela de seis pontos é instável diante de viés de nível e ponto extremo. Os pisos e alvos nominais seguem [`docs/POLITICA_ACEITE_MODELOS.md`](POLITICA_ACEITE_MODELOS.md).

## Comparação agregada

| Especificação | MAE | RMSE | MAPE | WAPE | sMAPE | MASE | Ljung–Box p | Cobertura fixa |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline `y_lag1` | 0,6170 | 0,7776 | 3,6613% | 3,6781% | 3,6948% | 0,9822 | 0,0390 | 66,67% |
| Conjunta `y_lag1,2,3,6,9,12` | **0,5219** | **0,6988** | **3,0936%** | **3,1112%** | **3,1226%** | **0,8268** | **0,1070** | **75,00%** |

A especificação conjunta melhora todas as métricas de erro agregadas, eleva o p-valor do Ljung–Box acima de 0,05 e alcança o piso de cobertura. A melhora do MAPE é de 0,5677 ponto percentual. O MAPE de 3,0936% e a cobertura de 75,00% ainda não alcançam os alvos nominais exploratórios de 2,87% e 80%.

## Métricas por horizonte OOS

| Horizonte | MAE baseline | MAE conjunto | RMSE baseline | RMSE conjunto | MAPE baseline | MAPE conjunto |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0,4345 | 0,4371 | 0,4345 | 0,4371 | 2,6856% | 2,7002% |
| 2 | 0,8310 | 0,8379 | 0,8310 | 0,8379 | 5,0523% | 5,0934% |
| 3 | 0,4307 | 0,3141 | 0,4307 | 0,3141 | 2,5586% | 1,8577% |
| 4 | 0,5279 | 0,5011 | 0,5279 | 0,5011 | 3,2198% | 3,0584% |
| 5 | 0,2891 | 0,2973 | 0,2891 | 0,2973 | 1,7094% | 1,7585% |
| 6 | 0,6903 | 0,7462 | 0,6903 | 0,7462 | 3,7763% | 4,1070% |

A especificação conjunta melhora os horizontes 3 e 4 com maior margem, enquanto o baseline permanece ligeiramente melhor nos horizontes 1, 2, 5 e 6. A decisão foi tomada pelo conjunto de métricas e não por uma única janela. A amostra OOS é curta; por isso, a promoção é restrita ao painel diagnóstico.

## Cobertura P10–P90 e heterocedasticidade

A abordagem fixa reproduz a lógica prequential: a dobra avaliada usa somente resíduos OOS de dobras anteriores para estimar os quantis. A variante condicionada à volatilidade redimensiona a distância dos quantis em relação à mediana pela razão entre o desvio-padrão recente e o histórico, limitada a `[0,5; 2,0]`.

| Especificação | Intervalo | Cobertura | Pinball Loss | Resultado |
|---|---|---:|---:|---|
| Baseline | Fixo, prequential | 66,67% | 0,1849 | Abaixo do piso |
| Baseline | Condicionado à volatilidade | 58,33% | 0,1836 | Piora cobertura |
| Conjunta | Fixo, prequential | **75,00%** | **0,1669** | **Passa o piso; abaixo do alvo** |
| Conjunta | Condicionado à volatilidade | 58,33% | 0,1750 | Piora cobertura |

A calibração condicional não melhora a cobertura em nenhum dos braços. A abordagem fixa permanece o padrão do painel. A variante de volatilidade continua disponível para investigação, mas não é promovida com apenas duas dobras efetivamente avaliadas para intervalos.

## Decisão técnica

A família conjunta `1,2,3,6,9,12` foi promovida como **padrão do painel diagnóstico OLS** porque passa os três pisos canônicos: MAPE, cobertura e Ljung–Box agrupado. O artefato oficial `model_performance_v2.json` foi regenerado após a alteração de `TARGET_LAGS` e apresenta `status_operacional: "aprovado"`, `criterios_aceite_reprovados: []` e `todos_criterios_atingidos: true`.

Essa promoção é restrita ao painel diagnóstico. O OLS continua sendo explicativo e não alimenta o forecast operacional, Risk Engine, Robust Planning ou Decision Intelligence. O modelo principal permanece a Regressão com defasagens implementada em `src/analysis.py`. Os alvos nominais exploratórios de MAPE 2,87% e cobertura 80% continuam como referências de melhoria, não como critérios binários adicionais.

## Reprodutibilidade

```bash
cd /home/ubuntu/quant_automotivo_streamlit
PYTHONPATH=src python3 scripts/evaluate_joint_lags_volatility.py
```

A validação do artefato oficial é executada por:

```bash
PYTHONPATH=src python3 scripts/train_advanced_models.py
```

## Referências

[1]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/data/model_artifacts/joint_lags_volatility_backtest.json "Artefato do backtest de lags conjuntos"

[2]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/data/model_artifacts/model_performance_v2.json "Artefato oficial de desempenho OLS v2.3"

[3]: https://github.com/edu-moraess/quant-automotive-planning/blob/main/docs/POLITICA_ACEITE_MODELOS.md "Política única de aceite"
