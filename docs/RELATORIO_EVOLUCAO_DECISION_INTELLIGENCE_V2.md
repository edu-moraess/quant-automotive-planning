# Relatório de evolução — Decision Intelligence v2

## Sumário executivo

A evolução v2 transformou a plataforma em uma arquitetura quantitativa conectada entre dados, forecast, incerteza, cenários, risco, otimização e decisão. O trabalho preservou a regressão de defasagens como modelo principal de mercado, sem substituir o pipeline legado por uma técnica arbitrária. A integração foi feita em camadas, com contratos explícitos, cache independente na interface e status metodológico em cada resultado.

A validação final possui **79 testes aprovados**, `ruff check` limpo, `ruff format --check` limpo, compilação Python concluída e smoke test local da aplicação Streamlit aprovado. O repositório público foi atualizado até o commit [`6bdceca`](https://github.com/edu-moraess/quant-automotive-planning/commit/6bdceca).

## Entregas por camada

| Camada | Implementação | Evidência de validação |
|---|---|---|
| Auditoria e contratos | Auditoria da árvore, estabilização de entradas, rejeição de séries vazias, NaN e dimensões incompatíveis | `docs/AUDITORIA_EVOLUCAO_V2.md` e testes de contrato |
| Governança de dados | Schema drift, versão determinística, staleness, point-in-time e proveniência | `src/data/governance.py`, `src/data_quality.py` e testes de qualidade |
| Forecast Engine | Contrato modular `fit/predict/forecast/evaluate/diagnostics`, walk-forward por horizonte e seleção de lags OOS | `src/forecast_engine.py` e testes de forecast |
| Econometria | Diagnósticos Ljung–Box, ARCH, Breusch–Pagan, Jarque–Bera, Durbin–Watson e teste de desenho | `src/econometric_diagnostics.py` |
| Forecast probabilístico | Resíduos fora da amostra, quatro distribuições candidatas, calibração prequential e metadados | `src/probabilistic_forecast.py` |
| Cenários | Market share parametrizado, `ScenarioSpec`, choques explícitos e sensibilidade com status de conexão | `src/scenario_engine.py` |
| Risco | Monte Carlo reprodutível, stockout probability, backlog risk, capacity-at-risk, VaR e CVaR | `src/risk_engine.py` |
| Otimização robusta | PuLP/CBC resolvido por caminhos Monte Carlo amostrados e planos representativos P10/P50/P90 | `src/robust_planning.py` |
| Decision Intelligence | Sinais green/amber/red/unavailable, confiança de evidência, ações condicionais e limitações | `src/decision_intelligence.py` |
| Interface | Abas Decisão e Risco & Cenários, cache independente, sidebar colapsável e otimização robusta opcional | `app.py` e smoke test local |

## Resultado quantitativo de referência

A execução reproduzível em `scripts/evaluate_risk_engine.py` utiliza o snapshot FRED local versionado, sem consulta online, e o forecast probabilístico vigente. Com 5.000 caminhos, seed 42 e market share assumido de 8%, o Risk Engine produziu os seguintes resultados:

| Métrica | Resultado | Interpretação |
|---|---:|---|
| Horizonte | 6 meses | Janela de decisão usada na execução de referência |
| Stockout probability | 65,62% | Proporção de caminhos com backlog em algum mês |
| Backlog esperado | 23.577 unidades | Soma média do backlog ao longo dos caminhos |
| Capacity-at-risk P95 | 127.723 unidades | Percentil 95 da demanda mensal convertida em unidades |
| VaR 90% | US$ 3,11 bi | Percentil 90 do custo de backlog sob a política declarada |
| VaR 95% | US$ 4,02 bi | Percentil 95 do custo de backlog sob a política declarada |
| CVaR 95% | US$ 4,69 bi | Média dos custos no conjunto além do VaR 95% |
| VaR 99% | US$ 4,87 bi | Percentil 99 do custo de backlog sob a política declarada |

Esses números não são previsão de vendas, guidance financeiro ou plano ótimo estocástico. Eles são resultados condicionais ao snapshot, ao modelo, à capacidade, ao estoque, ao custo de backlog e à participação assumida.

## Contratos decisórios

A Decision Intelligence não transforma um resultado quantitativo em recomendação incondicional. Cada sinal contém a métrica de origem, o limiar, a unidade, a evidência e a camada responsável. O status `unavailable` é usado quando faltam métricas; portanto, a ausência de evidência não é convertida em sinal favorável.

> **Regra de interpretação.** Market share permanece uma hipótese quando não há observação pública por marca ou modelo. O catálogo EPA mede configurações técnicas, não unidades vendidas. O FRED TOTALSA mede mercado agregado, não participação comercial.

A aba `Decisão` apresenta o status geral, a confiança de disponibilidade das evidências, os sinais quantitativos, as ações condicionais e as limitações. A aba `Risco & Cenários` separa a aproximação de capacidade do plano PuLP por caminhos. Quando a otimização robusta não está ativada, a interface informa essa condição em vez de apresentar o Risk Engine como se fosse uma solução ótima.

## Performance e reprodutibilidade

A carga de mercado continua usando cache seletivo: o snapshot, os hiperparâmetros e o identificador de atualização controlam a invalidação. O Risk Engine é cacheado separadamente do forecast e do planejamento determinístico. A resolução PuLP por caminhos é opcional e configurável entre 10 e 200 caminhos para preservar a responsividade da interface.

A execução local de qualidade é:

```bash
python3 -m compileall -q app.py src scripts tests
ruff check .
ruff format --check .
python3 -m pytest tests/ -q
python3 scripts/evaluate_risk_engine.py
```

## Limitações remanescentes

A origem FRED pode estar indisponível ou atrasada; nesse caso, o snapshot local é exibido com sua proveniência e motivo de fallback. As APIs EIA, News API e NHTSA dependem do ambiente de execução e de suas credenciais ou latência. O monitoramento NHTSA é uma camada de eventos públicos, não uma medida de qualidade ou taxa de defeitos.

A rede de dados não possui vendas públicas confiáveis por marca e modelo dentro do escopo atual. Por isso, o projeto não converte filtros EPA em participação comercial. A propagação de combustível e juros para demanda continua dependente de regressores conectados e validados fora da amostra; sensibilidades não conectadas permanecem marcadas como tais.

A otimização robusta resolve uma amostra de caminhos com o solver existente. Ela não substitui uma formulação estocástica global, não estima uma política ótima de recourse e não calcula valor da informação. Esses pontos são extensões futuras, não resultados já disponíveis.

## Sequência de publicação

| Commit | Entrega |
|---|---|
| `442a62f` | Estabilização dos contratos do forecast |
| `076ecbf` | Governança de dados e schema drift |
| `80671b2` | Forecast Engine modular e walk-forward por horizonte |
| `6101321` | Diagnósticos econométricos e seleção de lags OOS |
| `ac95895` | Forecast probabilístico calibrado por resíduos OOS |
| `5bd80ac` | Scenario Engine e market share parametrizado |
| `fc32453` | Monte Carlo e Risk Engine operacional |
| `5b51b0f` | Integração de risco ao planejamento PuLP |
| `6f42aca` | Decision Intelligence |
| `9403829` | UI por decisão e risco operacional |
| `6bdceca` | Documentação final de risco e decisão |

## Referências

- [1] [FRED — Total Vehicle Sales (`TOTALSA`)](https://fred.stlouisfed.org/series/TOTALSA)
- [2] [U.S. EPA / FuelEconomy.gov — Download Fuel Economy Data](https://www.fueleconomy.gov/feg/download.shtml)
- [3] [U.S. EIA — Gasoline and Diesel Fuel Update](https://www.eia.gov/petroleum/gasdiesel/)
- [4] [NHTSA — Recalls and Complaints](https://www.nhtsa.gov/recalls)
