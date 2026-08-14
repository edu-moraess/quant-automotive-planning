# Relatório de Evolução Arquitetural com Referência ETIL

## 1. Baseline

O ponto de partida foi o commit `a07a047` do Quant Automotive Planning. Antes da alteração, compilação Python, Ruff e a suíte existente estavam aprovados com **28 testes**. O fluxo reproduzível leu 50.242 configurações EPA, 574 observações mensais de energia e 607 observações FRED; o motor selecionou **Regressão com defasagens**, projetou seis meses e resolveu quatro cenários de planejamento.

| Verificação | Antes | Depois |
|---|---:|---:|
| Compilação | Aprovada | Aprovada |
| Ruff check / format | Aprovado | Aprovado |
| Testes automatizados | 28 aprovados | **30 aprovados** |
| Modelo vencedor | Regressão com defasagens | Regressão com defasagens |
| MAPE médio | 3,97% | 3,97% |
| Horizonte | 6 meses | 6 meses |
| Cenários operacionais | 4 | 4 |

A execução isolada de `tests/test_forecasting_engine.py` revelou uma fragilidade de infraestrutura: o teste dependia implicitamente de outro módulo de testes inserir `src/` em `sys.path`. A suite completa escondia esse problema por ordem de coleta. O teste foi tornado autônomo.

## 2. Principais achados no Quant Automotive

A arquitetura central já era adequada ao domínio: `ingestion.py` controla fonte, timeout e fallback; `data_quality.py` preserva saúde e proveniência; módulos de mercado, produto, energia, cenários e planejamento permanecem separados; o dashboard consome resultados cacheados. A principal oportunidade não era uma reconstrução de diretórios, mas uma melhoria de governança quantitativa na avaliação de incerteza.

A cobertura p10–p90 antes exposta era calculada a partir do conjunto completo de resíduos fora da amostra, incluindo resíduos de dobras posteriores à dobra avaliada. O número era útil como diagnóstico agregado, porém não correspondia à avaliação que estaria disponível em cada origem temporal. Além disso, os valores de sazonalidade, lags AutoReg e regularização Ridge eram estáveis, mas estavam dispersos no código em vez de formalizados no contrato de configuração.

## 3. Análise do ETIL

O ETIL auditado foi `edu-moraess/EV-Transition-Intelligence-Lab-ETIL-`, commit `1f3c7df`. Sua contribuição mais relevante foi metodológica, não de código: o repositório enfatiza construção temporal causal de features, RNG local reprodutível, guardas quantitativas para quantis e transparência sobre limites de validação fora da amostra. A própria auditoria do ETIL reconhece que seus modelos de difusão e índices multifatoriais ainda precisam de validação temporal formal; essa limitação foi considerada na matriz de decisão.

## 4. Itens adaptados do padrão ETIL

| Padrão de referência | Problema resolvido no Quant Automotive | Implementação no Quant Automotive | Risco | Validação |
|---|---|---|---|---|
| Avaliação temporal sem informação futura | Cobertura de intervalo agregava resíduos de todas as dobras | `prequential_interval_quality` usa somente resíduos de dobras anteriores para cada dobra avaliada | A primeira dobra não possui histórico de erros e não é pontuada | Teste com mudança artificial de erro confirma cobertura zero sem uso de resíduos futuros |
| Reprodutibilidade com RNG local | A propriedade existia, mas não tinha regressão explícita | Teste de igualdade de simulações com a mesma seed | Baixo; o algoritmo não foi alterado | Teste de reprodutibilidade e não negatividade |
| Guardas quantitativas de quantis | Ordenação e não negatividade dependiam de comportamento não testado | Teste de `p10 ≤ p50 ≤ p90` e de trajetórias não negativas | Baixo | Teste de forecast probabilístico |
| Configuração explícita | Lags, sazonalidade e regularização estavam hardcoded | `ForecastSettings` recebeu `seasonal_periods`, `autoreg_lags` e `ridge_alpha` com os mesmos valores anteriores | Nulo para resultado atual | Baseline pós-alteração preservou modelo, MAPE, horizonte e cenários |

A interface Mercado & Forecast agora mostra **Cobertura prequential p10–p90** e **Pinball loss prequential**, incluindo quantidade de observações e dobras efetivamente avaliadas. Na execução validada, a cobertura foi 66,7% em 18 observações de três dobras e a pinball loss foi 0,275. Esses valores são diagnósticos de calibração, não garantias de intervalo.

## 5. Itens deliberadamente não incorporados

Modelos Bass, Logistic e Gompertz, Gaussian Process, ranking EVQTI/ETII, GMM de regimes, detector de mudança heurístico, World Bank API, páginas adicionais e logger em arquivo foram ignorados. Esses componentes não corrigem uma deficiência observada no mercado agregado mensal, no catálogo EPA ou no planejamento operacional. Eles introduziriam novos pressupostos, novas fontes ou maior superfície de manutenção sem dados compatíveis ou validação adicional. A fachada de compatibilidade do ETIL também não foi trazida, pois o Quant Automotive não possui rotas de ingestão concorrentes com semânticas divergentes.

## 6. Arquitetura resultante

```text
FRED / EPA / EIA-BLS snapshots e fontes online controladas
  → ingestion + validation + provenance
  → market / vehicle / energy intelligence
  → forecasting walk-forward + bootstrap probabilístico
  → calibração prequential de intervalos
  → cenários explícitos + planejamento linear
  → Streamlit com cache e leitura vertical
```

A alteração preserva as fronteiras existentes. O dashboard não calcula calibração; ele apenas apresenta o contrato produzido por `analysis.py`. O motor de forecast continua escolhido por backtest multi-métrico e a incerteza futura continua construída por bootstrap iid ou por blocos móveis conforme o diagnóstico residual.

## 7. Testes e classificação das diferenças

| Classe | Resultado |
|---|---|
| Correção de infraestrutura | O teste de forecasting passou a funcionar isoladamente, sem depender da ordem de coleta |
| Melhoria quantitativa | A calibração prequential evita usar resíduos de dobras futuras ao avaliar a dobra atual |
| Mudança intencional de interface | O painel passou a exibir métricas prequential em substituição à leitura retrospectiva agregada |
| Regressão | Nenhuma identificada |

Além da suíte completa, o painel foi reiniciado em sessão limpa e a aba Mercado & Forecast foi validada visualmente. Não houve exceção no log Streamlit. Persistem apenas avisos KaTeX não bloqueantes referentes a caracteres acentuados em fórmulas, já conhecidos e sem impacto na execução.

## 8. Dívida técnica remanescente

A cobertura prequential usa poucas dobras na configuração padrão; ela deve ser lida como sinal diagnóstico e não como teste de calibração definitivo. A escolha de modelos ainda é univariada e o forecast operacional pressupõe que a série TOTALSA é uma referência adequada de mercado agregado. O OLS energético permanece descritivo e a MLP de eficiência depende do catálogo EPA, não de resultados comerciais. O template CI ainda precisa ser ativado em `.github/workflows/` por credencial autorizada a alterar workflows.

## 9. Avaliação final

| Dimensão | Nota | Justificativa |
|---|---:|---|
| Arquitetura | 8,5/10 | Fronteiras modulares e cache explícito; `app.py` ainda concentra composição visual extensa. |
| Engenharia de dados | 8,5/10 | Snapshots, schemas, retry, fallback e proveniência estão integrados. |
| Confiabilidade quantitativa | 8,5/10 | Walk-forward, múltiplas métricas, bootstrap dependente e calibração prequential explícita. |
| Infraestrutura de ML | 8,0/10 | Separação temporal, artefatos e interpretabilidade; monitoramento de drift ainda não existe. |
| Testes | 8,0/10 | Trinta testes, incluindo regressões quantitativas; não há cobertura completa de todas as interações visuais. |
| Manutenibilidade | 8,0/10 | Configuração central e módulos por domínio; alguns módulos e `app.py` ainda são extensos. |
| Desempenho | 8,5/10 | Cache por camada, atualizações FRED e energia otimizadas e navegação validada. |
| Prontidão de produção acadêmica/profissional | 8,5/10 | Reprodutível e auditável para análise e planejamento; não deve ser usado como motor de decisão comercial sem dados adicionais e governança operacional. |

O Quant Automotive permanece tecnicamente coerente sem dependência de execução, dados ou marca do ETIL. O laboratório foi usado apenas para inspirar uma salvaguarda quantitativa e uma disciplina de teste mais explícita.
