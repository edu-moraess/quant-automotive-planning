# Arquitetura-Alvo — Quant Automotive Intelligence & Planning

## Princípio de desenho

A plataforma mantém as fontes separadas e conecta somente variáveis para as quais existe uma relação metodológica válida. O FRED mede demanda agregada, a EPA descreve configurações técnicas e EIA/BLS fornecem preços nacionais de energia. Não existe chave pública que transforme esses dados em vendas por marca ou por veículo; essa inferência não será criada.

```text
Ingestão → Validação e proveniência → Normalização e features
        → Mercado / Veículos / Energia → Forecast e incerteza
        → Cenários e otimização → Inteligência de decisão → Interface
```

| Camada | Responsabilidade | Módulo proposto |
|---|---|---|
| Configuração | URLs, timeout, tentativas, parâmetros de forecast e hipóteses operacionais. | `src/config.py` |
| Ingestão | Download de CSV com timeout, retry limitado, schema esperado e fallback. | `src/ingestion.py` |
| Qualidade | Perfil de observações, cobertura, frequência, duplicatas, ausências, outliers e status. | `src/data_quality.py` |
| Mercado | Normalização de `TOTALSA`, diagnósticos, modelos, backtest, incerteza e cenários. | `src/analysis.py` |
| Veículo | Normalização EPA, taxonomia de propulsão, agregações e evolução tecnológica. | `src/vehicle_intelligence.py` |
| Energia | Harmonização de preço, custo por distância, sensibilidade e correlações. | `src/energy_intelligence.py` |
| Modelos de produto | MLP de eficiência, erros e interpretabilidade por permutação. | `src/advanced_models.py` |
| Planejamento | Capacidade regular/extra, estoque, backlog, nível de serviço e hipóteses. | `src/analysis.py` com contrato de configuração explícito |
| Apresentação | Cache de artefatos, controles, gráficos e estados da fonte; sem cálculo quantitativo central. | `app.py` |

## Contratos de dados

| Dataset | Chave temporal | Campos mínimos | Regras de qualidade |
|---|---|---|---|
| Mercado FRED | `observation_date` mensal, normalizada para início do mês | `observation_date`, `TOTALSA` | Datas válidas, valor numérico, sem duplicatas, sequência mensal monitorada. |
| Catálogo EPA | `id` e `year` | `id`, `year`, `make`, `model`, `VClass`, `fuelType1`, `comb08` | IDs únicos, ano-modelo válido, texto essencial não vazio, métricas numéricas coerentes. |
| Energia | `data` mensal, normalizada para início do mês | `data` e ao menos uma série de preço | Datas únicas, preço não negativo, frequência reportada por série e ausência não imputada silenciosamente. |

## Configuração centralizada

Os valores que influenciam ingestão, validação ou decisão não permanecem espalhados no código. Eles são centralizados em dataclasses imutáveis:

| Grupo | Exemplos |
|---|---|
| Fontes | URL FRED, IDs de energia, timeout, número de tentativas e atraso. |
| Forecast | Horizonte, dobras, tamanho de teste, seed, réplicas e tamanho de bloco. |
| Planejamento | Capacidade regular, capacidade extra, estoque de segurança, custo de produção, custo extra, estoque e ruptura. |
| Modelos | Corte temporal, seed, arquitetura MLP, mínimo de observações e métricas. |

## Critérios quantitativos

A seleção de forecast combina MAPE, sMAPE, WAPE, RMSE e estabilidade entre dobras. A métrica principal não deve ser interpretada isoladamente: o resultado também reporta dispersão, ranking médio e tempo de execução. A seleção favorece o modelo mais simples quando a diferença de desempenho não é material.

A incerteza parte dos resíduos fora da amostra. O motor aplica bootstrap iid somente quando não há sinal de dependência residual; caso contrário, usa bootstrap móvel em blocos. A escolha, tamanho do bloco e seed são registrados nos artefatos de análise.

O modelo econométrico energia-mercado é mantido como análise explicativa enquanto sua validação temporal não superar as referências operacionais. A MLP de eficiência permanece separada, com corte temporal por ano-modelo, features sem vazamento e análise de erro por segmento e propulsão.

## Hipóteses de planejamento

As variáveis de custo, capacidade e estoque não são dados observados de uma empresa. Elas aparecem sempre como **ASSUMPTION** editável, com unidade, significado econômico e data de execução. O motor pode produzir cenários Base, Upside, Downside e Stress, informando explicitamente o choque aplicado a demanda, energia ou capacidade.

## Estratégia de desempenho

A interface usará cache separado para snapshots, transformações, análises e artefatos de modelo. Downloads externos só ocorrem em atualização explícita ou quando o cache expira; uma falha online apresenta o status e usa o snapshot local sem interromper o painel. O treinamento de modelos permanece em script reprodutível, não em cada rerun do Streamlit.
