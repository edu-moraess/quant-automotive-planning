# Quant Automotive Intelligence & Planning

## Relatório técnico-executivo para Comitê Automotivo

**Data:** 14/08/2026  
**Autor:** Manus AI  
**Base de evidências:** snapshots versionados da plataforma, artefatos de modelagem e fontes públicas oficiais.

> **Síntese para decisão:** a plataforma transforma dados públicos fragmentados de mercado, produto e energia em uma visão única para orientar capacidade, estoque, risco de demanda e leitura técnica de portfólio. Ela não substitui sistemas transacionais ou a decisão gerencial; organiza evidências, explicita hipóteses e torna os trade-offs verificáveis.

## 1. Resumo Executivo

A **Quant Automotive Intelligence & Planning** integra três perguntas que normalmente são tratadas de forma separada: qual é a trajetória provável do mercado agregado, como o portfólio técnico está posicionado e qual é a implicação operacional sob diferentes condições de demanda. A plataforma conecta a série mensal norte-americana de vendas totais de veículos, o catálogo técnico da EPA e indicadores nacionais de preço de energia. A série TOTALSA é publicada mensalmente, em milhões de unidades e taxa anualizada sazonalmente ajustada; ela representa uma referência consistente para leitura macro de demanda, e não vendas de uma marca específica.[1]

A solução se apoia em dados rastreáveis: **607 observações mensais de mercado** de 01/1976 a 07/2026, **50.242 configurações técnicas de veículos** da EPA entre os anos-modelo 1984 e 2027 e **574 observações mensais de energia** entre 11/1978 e 08/2026. Os três snapshots possuem controles de cobertura, ausência, duplicidade, integridade e hash SHA-256 em [`data/data_health.json`](../data/data_health.json). Essa estrutura reduz o risco de decisões sustentadas por planilhas sem origem, versões não identificadas ou datas ambíguas.

O resultado prático é um ambiente de decisão que mantém separadas as evidências de mercado, produto e operação, mas permite observá-las em sequência. O comitê pode compreender a previsão e sua incerteza, testar cenários de demanda, verificar a resposta de capacidade e estoque e contextualizar o portfólio por marca, segmento, eficiência e fonte de energia — sem atribuir, indevidamente, vendas agregadas a marcas do catálogo técnico.

| Frente de decisão | Evidência entregue | Uso executivo |
|---|---|---|
| Mercado | Backtest temporal, previsão por quantis e faixa de incerteza | Calibrar expectativa de volume e risco de erro. |
| Produto | Configurações EPA por marca, segmento, eficiência, emissões e tecnologia | Ler amplitude técnica do portfólio, sem inferir participação comercial. |
| Energia | Preços de gasolina, diesel e eletricidade, custo de referência e associações | Qualificar discussões sobre custo de uso e transição tecnológica. |
| Operação | Cenários, produção regular/extra, estoque, backlog e custo | Identificar pressão de capacidade antes de comprometer o plano. |
| Governança | Proveniência, saúde dos snapshots e contratos de apresentação temporal | Sustentar rastreabilidade e reprodutibilidade. |

## 2. Problema de Negócio

O setor automotivo toma decisões de produção e portfólio sob incerteza: uma revisão de demanda pode alterar a utilização da fábrica; uma pressão de preço energético pode mudar a narrativa de custo de uso; e a composição técnica do catálogo pode evoluir mais rapidamente do que os indicadores comerciais disponíveis. Quando esses sinais permanecem em silos, o planejamento tende a alternar entre excesso de confiança no ponto central e reações tardias a desvios.

A plataforma responde a esse problema ao criar uma cadeia analítica explícita. A demanda agregada fornece uma referência macro; o catálogo técnico descreve a diversidade de produto; energia aproxima o contexto de custo de uso; e a otimização traduz os cenários em produção, estoque e atendimento. A decisão não é apresentada como uma previsão infalível: ela é apresentada como uma escolha entre alternativas, com premissas declaradas e consequências mensuráveis.

| Pergunta do comitê | Resposta fornecida pela plataforma | Limite de interpretação |
|---|---|---|
| O mercado tende a expandir ou retrair? | Faixa probabilística e validação fora da amostra do forecast agregado. | Não identifica demanda por marca, região ou modelo. |
| O portfólio está tecnicamente concentrado ou diversificado? | Contagem de configurações EPA, segmentos, eficiência, emissões e propulsão. | Não mede vendas, margem ou participação. |
| Qual o efeito de uma variação de demanda? | Cenários Downside, Base, Upside e Stress com choques explícitos. | O resultado depende das hipóteses operacionais informadas. |
| A operação suporta o cenário? | Utilização, produção regular/extra, estoque, backlog e custo. | Não substitui restrições reais de fornecedores, mão de obra ou mix. |

## 3. Arquitetura Funcional

Em linguagem de negócio, a arquitetura atua como uma **linha de produção de inteligência**. Primeiro, ela coleta e confere dados públicos; depois, transforma dados em indicadores comparáveis; em seguida, mede o desempenho das previsões; por fim, converte os cenários em alternativas operacionais. Cada etapa deixa um rastro claro sobre fonte, data de cobertura e hipótese adotada.

A camada de mercado usa TOTALSA, cuja fonte original é o Bureau of Economic Analysis e cuja divulgação ocorre via FRED.[1] A camada de produto parte de dados de testes de economia de combustível conduzidos pela EPA e fabricantes sob supervisão da agência.[2] A camada de energia combina a atualização pública de gasolina e diesel da EIA, cujos preços incluem tributos aplicáveis, com a série urbana média de eletricidade do BLS distribuída pelo FRED.[3] [4]

| Etapa funcional | O que acontece | Entrega ao comitê |
|---|---|---|
| Aquisição e integridade | Leitura de snapshots, validação de estrutura, tentativa controlada de atualização e fallback reprodutível. | Evidência com fonte e versão identificadas. |
| Inteligência de produto | Classificação de propulsão e agregação por marca, modelo e segmento. | Leitura técnica de amplitude, eficiência e emissões. |
| Inteligência de energia | Consolidação mensal e estimativa de custo de energia por 100 milhas para casos comparáveis. | Contexto econômico de uso. |
| Previsão de mercado | Comparação de métodos e seleção por desempenho fora da amostra. | Volume de referência e intervalo de incerteza. |
| Cenários e planejamento | Choques declarados e otimização de capacidade, estoque e atendimento. | Plano operacional comparável por cenário. |
| Governança | Metadados, qualidade, hashes e apresentação temporal padronizada. | Auditabilidade e confiança no uso. |

## 4. Explicação dos Componentes Relevantes

Os componentes foram desenhados para que uma alteração em um deles não distorça os demais. Por exemplo, o filtro do catálogo EPA atualiza a leitura de produto e energia, mas não reinterpreta a série TOTALSA como se ela fosse venda por marca. Da mesma forma, a atualização do mercado refaz forecast e planejamento sem reprocessar desnecessariamente a camada de produto.

| Componente | Papel de negócio | Resultado entregue |
|---|---|---|
| Ingestão e fallback | Evita que indisponibilidade temporária de fonte interrompa a análise. | Snapshot local rastreável quando a consulta externa não é necessária ou falha. |
| Qualidade de dados | Identifica cobertura, lacunas, ausências, duplicidades, invalidações e valores atípicos. | Transparência sobre o que pode ou não ser interpretado. |
| Inteligência de portfólio | Reorganiza o catálogo EPA em visões de marca, classe e tecnologia. | Scorecards técnicos e comparação controlada de configurações. |
| Inteligência de energia | Alinha preços nacionais e atributos de consumo disponíveis. | Custo de referência por 100 milhas e sensibilidade a choques. |
| Forecast | Compara métodos sob validação temporal. | Modelo selecionado, erro histórico e quantis p10–p90. |
| Econometria | Explora associação entre mercado, defasagens e energia. | Sinais explicativos, coeficientes e diagnósticos, sem substituir o forecast. |
| Rede neural | Estima eficiência EPA a partir de atributos técnicos permitidos. | Previsão de MPG/MPGe, erros por propulsão e importância de variáveis. |
| Otimização | Aloca produção regular, extra e estoque frente à demanda. | Trade-off quantificado entre custo, backlog e nível de serviço. |
| Apresentação temporal | Distingue competência, data de cobertura e timestamp de auditoria. | Tabelas legíveis sem perda de precisão operacional. |

## 5. Data Intelligence

A inteligência de dados começa pela escolha de fontes públicas com escopo claro. TOTALSA é uma série agregada de vendas de veículos novos nos Estados Unidos, com frequência mensal e unidade em milhões de unidades na taxa anualizada sazonalmente ajustada.[1] O catálogo FuelEconomy.gov disponibiliza arquivos para todos os anos-modelo e descreve que as informações derivam de testes da EPA e de fabricantes supervisionados pela agência.[2] Para energia, a EIA divulga preços semanais de gasolina e diesel, enquanto a série de eletricidade observada é mensal e representa o preço médio em áreas urbanas dos Estados Unidos.[3] [4]

Essas fontes têm granularidades distintas. A plataforma não mascara essa diferença: gasolina e diesel são consolidados para a competência mensal; eletricidade já é mensal; e os atributos EPA são estruturais por configuração de veículo. Assim, a análise consegue comparar tendências sem inventar uma precisão que os dados não possuem.

| Ativo de dados | Papel analítico | Cobertura no snapshot | Controle de qualidade |
|---|---|---|---|
| FRED TOTALSA | Mercado agregado de veículos leves. | 607 meses, 01/1976–07/2026. | 0% de ausência, 0 duplicidade e sem lacunas mensais. |
| EPA vehicles | Configurações, marca, modelo, segmento, consumo, emissões e tecnologia. | 50.242 linhas, anos-modelo 1984–2027. | 84 colunas; outliers de eficiência são sinalizados, não excluídos automaticamente. |
| Energia FRED/EIA/BLS | Gasolina, diesel e eletricidade para custo de referência. | 574 meses, 11/1978–08/2026. | Ausências históricas são preservadas; não há imputação artificial. |

A revisão temporal recente também elevou a qualidade da comunicação. Competências mensais do plano aparecem como `MM/AAAA`; coberturas diárias como `DD/MM/AAAA`; e o horário é preservado apenas onde ele representa um evento de auditoria em UTC. A documentação detalhada está em [`AUDITORIA_TEMPORAL_TABELAS.md`](AUDITORIA_TEMPORAL_TABELAS.md).

## 6. Analytics

A camada analítica responde a três necessidades. A primeira é descrever o portfólio: marcas, segmentos, propulsão, eficiência, emissões e custo energético de referência. A segunda é medir associações entre atributos comparáveis, com correlação de Spearman, para detectar relações monotônicas sem confundir associação com causalidade. A terceira é avaliar se sinais de energia e defasagens ajudam a explicar o comportamento da demanda agregada.

A análise econométrica é deliberadamente tratada como **explicativa**, não como mecanismo operacional de previsão. O artefato atual contém 24 observações de validação temporal, MAE de aproximadamente 0,584 milhão de unidades SAAR e R² fora da amostra negativo. Esse resultado é visível na interface para evitar que um ajuste histórico forte seja confundido com capacidade de antecipação futura. A plataforma privilegia transparência sobre narrativa estatística.

| Análise | Pergunta de negócio | Como deve ser usada |
|---|---|---|
| Scorecard de marcas | Onde há concentração técnica de configurações e como se distribuem eficiência e emissões? | Leitura de produto e benchmark técnico. |
| Comparação controlada | Como até quatro configurações se comparam em consumo, custo e emissões? | Discussão de produto sem extrapolar para margem ou vendas. |
| Correlação Spearman | Quais atributos caminham juntos dentro do recorte analisado? | Geração de hipóteses e priorização de investigação. |
| OLS com energia | Sinais de preço e defasagens ajudam a contextualizar a demanda? | Análise explicativa; não substituir o forecast. |
| Rede neural de eficiência | Quão previsível é a eficiência a partir do projeto técnico? | Avaliar coerência técnica, fontes de erro e variáveis relevantes. |

## 7. Forecasting

O forecast operacional compara quatro famílias de modelos: referência sazonal, Holt-Winters, regressão Ridge com defasagens e AutoReg sazonal. A seleção não ocorre pelo melhor ajuste sobre a história completa; ocorre por **walk-forward**, em que cada dobra aprende com o passado e é avaliada em meses que não foram vistos durante o ajuste. O método vencedor é reestimado para produzir uma projeção de referência e os quantis p10, p25, p50, p75 e p90.

A incerteza é uma parte do resultado, não um rodapé. A plataforma usa bootstrap de resíduos, incluindo blocos móveis, para formar faixas de resultado. Também acompanha a calibração prequential: cada dobra usa apenas resíduos disponíveis em dobras anteriores, evitando que o futuro melhore artificialmente a qualidade do intervalo. A validação apresenta MAPE, sMAPE, WAPE, MAE, RMSE e MASE para que a leitura não dependa de uma única métrica.

| Elemento | Significado para o comitê | Decisão apoiada |
|---|---|---|
| Walk-forward | Simula o processo real de prever meses ainda desconhecidos. | Escolher o método com melhor comportamento fora da amostra. |
| MAPE / sMAPE / WAPE | Erro percentual em diferentes formulações. | Dimensionar o risco relativo da projeção. |
| MAE / RMSE | Erro em milhões SAAR e penalização de desvios maiores. | Estimar amplitude prática do desvio. |
| MASE | Erro comparado a uma referência simples. | Evitar elogiar modelo que não supera o baseline. |
| p10–p90 | Intervalo de cenários probabilísticos da previsão. | Preparar capacidade e estoque para dispersão plausível. |

## 8. Análise de Cenários

A análise de cenários transforma incerteza em linguagem operacional. A plataforma aplica choques de demanda claramente declarados aos quatro cenários: **Downside** (−10%), **Base** (0%), **Upside** (+10%) e **Stress** (+20%). Os percentuais não são apresentados como previsão macroeconômica independente; são hipóteses de gestão que permitem testar a robustez do plano.

A mesma disciplina é usada para energia. Os choques de −20%, 0% e +20% sobre os preços observados são uma sensibilidade, não uma projeção de combustível. A EIA mantém atualizações semanais de gasolina e diesel nacionais, com preços que incluem tributos, e a série elétrica usada é mensal; portanto, a plataforma preserva a distinção entre frequência de fonte e frequência de decisão.[3] [4]

| Cenário | Hipótese explícita | Indicadores acompanhados | Leitura gerencial |
|---|---:|---|---|
| Downside | −10% de demanda | Produção, estoque, ociosidade e custo. | Proteção contra excesso de produção e estoque. |
| Base | 0% de choque | Plano de referência. | Orçamento e coordenação corrente. |
| Upside | +10% de demanda | Utilização, produção extra e backlog. | Antecipação de pressão de capacidade. |
| Stress | +20% de demanda | Backlog, desvio de segurança e custo total. | Teste de resiliência e contingência. |

## 9. Inteligência Quantitativa

A inteligência quantitativa se materializa quando previsão e cenários chegam ao modelo de planejamento. Para cada mês do horizonte, a otimização decide a produção regular, a produção extra, o estoque final e a demanda pendente. O objetivo econômico combina custo de produção, custo de horas extras, custo de manutenção de estoque, penalidade de backlog, desvio de estoque de segurança e, quando aplicável, custo de setup.

O mérito do modelo não está em prometer uma solução “automática”, mas em tornar os trade-offs explícitos. Se a capacidade é insuficiente, o impacto aparece como backlog e custo; se a produção é antecipada, o efeito aparece como estoque e seu custo; se há estoque de segurança, o desvio é mensurado. A interface deixa as hipóteses editáveis para que o comitê possa avaliar como a recomendação muda quando capacidade, participação assumida, custos ou estoque inicial são revisados.

| Variável decisória | O que representa | Risco que torna visível |
|---|---|---|
| Produção regular | Volume dentro da capacidade de referência. | Subutilização ou saturação da operação. |
| Produção extra | Resposta além da capacidade regular. | Custo marginal e dependência de contingência. |
| Estoque final | Amortecedor entre produção e demanda. | Capital empatado ou cobertura insuficiente. |
| Backlog | Demanda não atendida no período. | Risco de nível de serviço e receita postergada. |
| Estoque de segurança | Proteção definida pela gestão. | Exposição a ruptura em cenário adverso. |
| Custo total | Soma das consequências das decisões. | Trade-off econômico entre serviço e eficiência. |

## 10. Aplicação no Setor Automotivo

No ambiente automotivo, a plataforma pode organizar a conversa entre comercial, produto, manufatura, planejamento e finanças. Comercial obtém uma referência agregada e uma faixa de incerteza; produto observa padrões técnicos por marca e segmento; manufatura testa capacidade e backlog; e finanças recebe o custo relativo de alternativas operacionais. O resultado é especialmente útil em rotinas mensais de S&OP, comitês de produto, discussão de transição energética e exercícios de contingência.

A camada EPA é adequada para comparar características técnicas porque o banco disponibilizado publicamente inclui dados de economia de combustível derivados de testes e avaliações supervisionadas pela EPA.[2] Já a camada de mercado é adequada para contextualização macro porque TOTALSA é agregado e mensal.[1] O ganho vem de respeitar o papel de cada fonte em vez de forçar uma equivalência inexistente entre catálogo, venda e margem.

| Rotina executiva | Como usar a plataforma | Resultado esperado |
|---|---|---|
| S&OP mensal | Revisar forecast, intervalo p10–p90 e cenários de capacidade. | Plano com risco e custos explícitos. |
| Comitê de portfólio | Filtrar marcas, segmentos e tecnologias no catálogo EPA. | Leitura comparável de atributos técnicos. |
| Planejamento de contingência | Rodar Upside e Stress com capacidade e estoque alterados. | Gatilhos objetivos para ação preventiva. |
| Discussão de custo de uso | Avaliar energia por 100 milhas em configurações comparáveis. | Contexto para narrativa de tecnologia e consumidor. |
| Governança de dados | Verificar fonte, cobertura, hash e data de atualização. | Decisões com rastreabilidade. |

## 11. Diferencial do Quant Automotive

O diferencial central é a combinação de **disciplina analítica e transparência de escopo**. A plataforma não transforma dados técnicos da EPA em participação de mercado, não trata correlação como causalidade e não promove a regressão econométrica a previsão operacional quando sua validação fora da amostra é fraca. Essa postura reduz o risco de decisões baseadas em indicadores visualmente atraentes, mas conceitualmente inadequados.

Também há um diferencial de engenharia voltado à confiabilidade: atualização com timeout e tentativa controlada, fallback local, validação de esquema, metadados de saúde, hashes, cache seletivo e testes automatizados. A auditoria temporal removeu horários artificiais de competências mensais sem converter timestamps internos antes dos cálculos. Isso melhora a leitura executiva e mantém a integridade das etapas quantitativas.

| Diferencial | Evidência na plataforma | Benefício de negócio |
|---|---|---|
| Dados reais e rastreáveis | FRED/BEA, EPA, EIA e BLS; snapshots e SHA-256. | Confiança e reprodutibilidade. |
| Validação temporal | Walk-forward, métricas múltiplas e calibração prequential. | Menor risco de superestimar a previsão. |
| Separação de contratos de dados | Mercado agregado não é atribuído ao catálogo de marcas. | Menor risco de interpretação indevida. |
| Cenários explícitos | Choques declarados, não disfarçados como fato. | Discussão objetiva de contingências. |
| Otimização operacional | Produção, estoque, backlog e custos integrados. | Decisões comparáveis e quantificadas. |
| Interface vertical e auditável | Tabelas e gráficos em sequência; datas sem ruído de meia-noite. | Leitura executiva mais clara. |

## 12. Limitações

A plataforma é forte para análise integrada, mas suas limitações precisam orientar o uso. TOTALSA é um indicador agregado dos Estados Unidos e não identifica vendas por marca, modelo, região, canal ou consumidor.[1] O catálogo EPA descreve configurações técnicas e resultados de teste; ele não contém preço transacional, margem, disponibilidade em concessionária, pedidos, produção real ou participação comercial.[2]

Os preços energéticos também são referências nacionais. A EIA divulga gasolina e diesel em frequência semanal, enquanto a eletricidade usada é uma média urbana mensal; variação regional, contratos corporativos, tarifas locais e comportamento de recarga podem divergir materialmente dos valores de referência.[3] [4] Além disso, a análise econométrica atual apresenta R² fora da amostra negativo e, por desenho, serve para explicação, não para recomendação de volume.

| Limitação | Consequência | Mitigação recomendada |
|---|---|---|
| Mercado agregado | Não permite inferir demanda por marca ou região. | Integrar dados comerciais proprietários quando disponíveis. |
| Catálogo técnico sem vendas | Configurações não equivalem a volume ou margem. | Cruzar com registro, pedidos, mix e rentabilidade internos. |
| Energia nacional média | Pode não refletir contexto local do cliente ou da fábrica. | Adicionar tarifa, geografia e exposição contratual relevantes. |
| Modelo causal limitado | Associação não prova causalidade; OLS atual não prevê bem fora da amostra. | Manter como explicação e testar variáveis adicionais sob governança. |
| Horizonte e incerteza | Faixas estatísticas não cobrem todos os choques externos. | Atualizar cenário e acionar contingência qualitativa. |
| Otimização simplificada | Não captura integralmente fornecedores, restrições de mix, ramp-up e logística. | Evoluir para restrições operacionais reais antes de uso prescritivo amplo. |

## 13. Roadmap

O roadmap deve priorizar ganho de decisão antes de complexidade. A primeira etapa aprofunda a governança e os recortes operacionais; a segunda incorpora dados proprietários que conectem catálogo a demanda e margem; a terceira evolui o planejamento para uma visão de rede, fornecedores e mix. Cada avanço deve manter a mesma disciplina atual: fonte identificada, hipótese documentada, validação temporal e limite de interpretação visível.

| Horizonte indicativo | Prioridade | Entrega proposta | Critério de sucesso |
|---|---|---|---|
| Curto prazo | Governança e usabilidade | Agenda de atualização, dicionário de dados, exportação auditável e monitoramento de drift. | Toda decisão exibe versão, cobertura e data de dados. |
| Curto prazo | Operação | Restrições adicionais de estoque de segurança, horas extras e custo por cenário. | Cenários refletem as premissas aprovadas pelo comitê. |
| Médio prazo | Dados comerciais | Integração com pedidos, estoque, mix, preços e margens, se autorizada. | Separação clara entre fatos internos e fontes públicas. |
| Médio prazo | Granularidade | Forecast por segmento, região ou canal quando houver histórico suficiente. | Ganho fora da amostra superior a baseline e cobertura adequada. |
| Médio prazo | Rede de suprimentos | Restrições de fornecedor, componente, lead time e logística. | Plano identifica gargalos antes da execução. |
| Longo prazo | Prescrição robusta | Otimização estocástica e monitoramento contínuo de decisões. | Redução mensurável de backlog, estoque excessivo ou custo de contingência. |

## 14. Conclusão Executiva

A Quant Automotive Intelligence & Planning estabelece uma base sólida para transformar dados públicos em debate executivo estruturado. Ela não simplifica indevidamente a realidade automotiva: deixa claro que mercado agregado, catálogo técnico, preço energético e plano operacional são dimensões distintas, porém conectáveis. Ao combinar previsão validada, cenários explícitos, otimização e rastreabilidade, a plataforma oferece ao comitê uma forma mais disciplinada de discutir volume, capacidade, estoque e transição tecnológica.

A recomendação de uso é tratar a solução como **camada de inteligência e governança de decisão**. Nas rotinas de planejamento, ela deve orientar perguntas, revelar riscos e comparar alternativas; quando dados proprietários de demanda, margem e operação estiverem disponíveis, poderá ampliar progressivamente sua precisão e alcance. A credibilidade do sistema continuará derivando menos da complexidade do algoritmo e mais da honestidade sobre seus dados, premissas, incertezas e limites.

## Referências

[1]: https://fred.stlouisfed.org/series/TOTALSA "FRED — Total Vehicle Sales (TOTALSA)"
[2]: https://www.fueleconomy.gov/feg/download.shtml "EPA / FuelEconomy.gov — Download Fuel Economy Data"
[3]: https://www.eia.gov/petroleum/gasdiesel/ "U.S. Energy Information Administration — Gasoline and Diesel Fuel Update"
[4]: https://fred.stlouisfed.org/series/APU000072610 "FRED / BLS — Average Price: Electricity per Kilowatt-Hour in U.S. City Average"
