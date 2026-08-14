# Comparação Técnica: ETIL como Referência Seletiva

## Escopo e baseline

A análise comparou o Quant Automotive Planning, no commit-base `a07a047`, ao ETIL no commit `1f3c7df`. O projeto principal foi validado antes de qualquer alteração: compilação, Ruff e 28 testes passaram. O pipeline real carregou 50.242 configurações EPA, 574 meses de energia e 607 meses FRED; o forecast selecionou **Regressão com defasagens** e produziu seis períodos, enquanto o planejamento resolveu quatro cenários.

O ETIL foi tratado como laboratório de referência. Nenhum arquivo ou dependência será copiado diretamente. As decisões abaixo consideram adequação ao domínio automotivo agregado, custo de manutenção, preservação da lógica quantitativa e evidência de ganho técnico.

| Componente ou padrão do ETIL | Equivalente atual no Quant Automotive | Valor | Complexidade | Decisão | Fundamentação |
|---|---|---:|---:|---|---|
| Ingestão canônica com fachada de compatibilidade | `ingestion.py`, loaders por domínio e contratos explícitos | Médio | Médio | **KEEP** | O Quant não possui duas rotas ativas e contraditórias de ingestão. Criar uma fachada adicional não resolve um problema atual. |
| Preservação de missingness e validação de chaves/dimensões | `data_quality.py`, `prepare_data`, validações EPA/energia | Médio | Baixo | **KEEP** | A implementação atual já é mais estrita em schemas, frequência, duplicatas e proveniência. |
| Construção temporal causal de features | Defasagens 1 e 12, dobras expansivas e corte temporal MLP | Alto | Baixo | **ADAPT** | O princípio é compatível. Será reforçado pela centralização dos hiperparâmetros temporais e por testes de invariantes. |
| Simulações reproduzíveis com RNG local e quantis ordenados | `default_rng(seed)`, bootstrap iid/blocos móveis | Alto | Baixo | **ADAPT** | O mecanismo atual já usa RNG local e bootstrap dependente da autocorrelação. O ganho é formalizar testes de reprodutibilidade, não trocar o método. |
| Trajetórias GP correlacionadas | Bootstrap residual com blocos móveis condicionado a Ljung–Box | Médio | Alto | **KEEP** | O bootstrap atual preserva dependência temporal observada sem introduzir um GP ou novos pressupostos. |
| Métricas de ajuste de curvas de difusão | Backtest walk-forward multi-métrico | Baixo | Alto | **IGNORE** | Curvas de adoção por país não são o problema de previsão do mercado agregado mensal e seus diagnósticos ETIL são majoritariamente in-sample. |
| Regimes GMM, mudanças heurísticas e índices EVQTI/ETII | Cenários operacionais explícitos e modelos de produto/energia | Baixo | Alto | **IGNORE** | Não há base observacional equivalente por país e a própria auditoria ETIL reconhece ausência de validação temporal e risco de viés retrospectivo. |
| Calibração temporal formal de intervalos | Cobertura e pinball calculados sobre resíduos OOS agregados | Alto | Médio | **ADAPT** | A ideia é valiosa: a cobertura atual é diagnóstica, mas usa todos os resíduos OOS ao mesmo tempo. Será adicionada uma medida prequential que avalia cada dobra somente com erros de dobras anteriores. |
| Configuração central de parâmetros de modelo | `ForecastSettings` já centraliza horizonte, bootstrap e tolerância | Alto | Baixo | **ADAPT** | Ainda existem parâmetros de regressão e sazonalidade no código. Eles serão centralizados mantendo exatamente os valores atuais. |
| Logging genérico por arquivo | Status e proveniência visíveis na interface e artefatos JSON | Baixo | Médio | **IGNORE** | Adoção não resolve gargalo ou falha atual e acrescentaria superfície operacional sem infraestrutura de observabilidade persistente. |

## Mudanças aprovadas

A evolução será limitada a três pontos. Primeiro, os hiperparâmetros de forecast hoje dispersos serão centralizados em `ForecastSettings`, preservando os valores atuais e, portanto, o comportamento numérico. Segundo, o motor passará a reportar uma calibração prequential de intervalo p10–p90 e perda de quantil, sem usar resíduos de dobras futuras para avaliar uma dobra passada. Terceiro, a suíte receberá testes de reprodutibilidade local, não negatividade e ordenação dos quantis, inspirados no padrão de guardas quantitativas do ETIL.

## Itens deliberadamente não incorporados

Difusão Bass/Logistic/Gompertz, Gaussian Process, GMM, triagem de rupturas, rankings de países, EVQTI, ETII, World Bank API, multipáginas e logger do ETIL não serão incorporados. Eles não respondem a uma deficiência observada no Quant Automotive e aumentariam complexidade ou pressupostos sem dados compatíveis. O projeto final continuará independente e coerente sem referência de execução ao ETIL.
