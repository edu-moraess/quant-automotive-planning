# Decision Intelligence, risco e planejamento robusto

## Escopo

A camada de Decision Intelligence transforma resultados já calculados pelo projeto em sinais operacionais rastreáveis. Ela não gera recomendação comercial independente do modelo, não converte dados EPA em vendas por marca e não trata hipóteses de market share como observações.

> **Princípio de governança.** Uma decisão só é apresentada como sinal quando existe uma métrica quantitativa, um limiar declarado e uma fonte metodológica identificável.

## Camadas de saída

| Camada | Entrada | Saída | Status metodológico |
|---|---|---|---|
| Forecast probabilístico | Previsão pontual e resíduos walk-forward OOS | P10/P25/P50/P75/P90, método de erro e metadados | Estimado |
| Risk Engine | Caminhos de forecast, capacidade, estoque e market share | Probabilidade de stockout, backlog esperado, capacity-at-risk, VaR e CVaR | Estimado sobre simulações |
| Planejamento robusto | Caminhos de forecast e hipóteses operacionais | Soluções PuLP por caminhos amostrados e planos representativos P10/P50/P90 | Otimização integrada em amostra |
| Decision Intelligence | Métricas de forecast, risco, cenários e otimização | Sinais green/amber/red/unavailable, confiança e ações condicionais | Derivado das camadas anteriores |

## Monte Carlo e Risk Engine

O `src/risk_engine.py` utiliza caminhos de forecast já produzidos pelo motor probabilístico. A semente é controlável e os caminhos são amostrados com ou sem reposição conforme a quantidade disponível. A conversão para unidades usa a participação assumida e mantém a hipótese registrada no resultado.

A política operacional aproximada é `full_capacity_backlog_first`: a capacidade regular mais a capacidade extra atende primeiro o backlog acumulado, preservando o estoque remanescente. Essa política é transparente e não deve ser chamada de solução ótima. As métricas de cauda usam a distribuição de custo de backlog.

| Métrica | Definição operacional |
|---|---|
| `stockout_probability` | Proporção de caminhos com backlog positivo em algum mês. |
| `backlog_threshold_probability` | Proporção de caminhos cujo backlog acumulado excede o limiar configurado. |
| `capacity_at_risk_units` | Percentil 95 da capacidade mensal requerida nos caminhos simulados. |
| `VaR_95` | Percentil 95 do custo de backlog simulado. |
| `CVaR_95` | Média dos custos no conjunto que excede o VaR 95. |

A execução de referência sobre o snapshot local FRED, com 5.000 caminhos e participação assumida de 8%, produziu stockout probability de **65,62%**, backlog esperado de **23.577 unidades** e capacity-at-risk de **127.723 unidades**. Esses valores são uma referência do snapshot e das hipóteses daquele run; não representam previsão comercial nem garantia de execução.

## Planejamento robusto

O `src/robust_planning.py` integra os caminhos com o solver PuLP/CBC. Uma amostra configurável de caminhos é resolvida individualmente, e a saída preserva o custo, backlog, estoque, utilização e status do solver por caminho. Também são calculados planos representativos usando os quantis P10, P50 e P90 dos caminhos.

O método é uma **otimização robusta amostrada**, não uma formulação estocástica global. O número de caminhos é deliberadamente configurável para que a interface permaneça responsiva. A aba `Risco & Cenários` permite ativar a resolução com PuLP no expander `Forecast & Planejamento`.

## Decision Intelligence

O `src/decision_intelligence.py` aplica limiares declarados para MAPE, cobertura P10–P90, probabilidade de stockout, probabilidade de backlog final e utilização de capacidade. Cada sinal contém valor, limiar, unidade, evidência e origem. A classificação é:

| Status | Interpretação |
|---|---|
| `green` | Métrica dentro do limite declarado. |
| `amber` | Métrica próxima do limite e requer monitoramento. |
| `red` | Métrica excede materialmente o limite e requer revisão das hipóteses operacionais. |
| `unavailable` | Não há métrica suficiente para emitir sinal. |

A confiança não é uma probabilidade estatística de sucesso. É um score de disponibilidade e conformidade dos sinais que mostra quantas métricas foram observadas e quantas ficaram amber ou red.

## Limitações

O mercado FRED é agregado e não identifica vendas por marca ou modelo. O market share é assumido quando não há fonte observada. As probabilidades dos cenários são hipóteses de planejamento. O Risk Engine usa caminhos de forecast e uma política operacional declarada. A integração PuLP por caminhos é amostrada e não constitui uma solução estocástica ótima global.

Quando uma variável de combustível ou juros ainda não está conectada à função de demanda, a sensibilidade é marcada como `not_connected`; nenhum efeito é inventado. A Decision Intelligence preserva essa limitação na lista de ações condicionais e no painel de limitações.

## Execução reproduzível

```bash
python scripts/evaluate_risk_engine.py
```

O script usa `data/TOTALSA_snapshot.csv`, impede consulta online ao FRED e imprime a origem do dado, o modelo vencedor, as métricas de risco, a semente e o status metodológico da otimização.
