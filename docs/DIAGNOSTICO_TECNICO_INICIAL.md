# Diagnóstico Técnico Inicial

## Escopo examinado

A revisão cobriu a árvore versionada, dependências, snapshots, módulos Python, scripts, testes, documentação, configuração de execução, template de qualidade e todos os fluxos visíveis na aplicação. A plataforma tem uma base funcional e reproduzível de dados públicos, mas ainda concentra responsabilidades e tem pontos importantes de evolução para alcançar padrão de pesquisa e produção.

| Camada atual | Arquivos principais | Situação observada |
|---|---|---|
| Mercado e planejamento | `src/analysis.py` | Funciona de ponta a ponta, mas mistura ingestão, preparação, diagnóstico, previsão, incerteza e otimização no mesmo módulo. |
| Produto EPA | `src/vehicle_intelligence.py` | Taxonomia e agregações claras; falta contrato formal de schema, perfil de qualidade e metadados de snapshot. |
| Energia | `src/energy_intelligence.py`, `scripts/fetch_energy_prices.py` | Fórmulas comparáveis corretas para gasolina, diesel e BEV; ingestão direta sem timeout, retries, schema ou proveniência estruturada. |
| Modelos avançados | `src/advanced_models.py` | MLP temporal de eficiência é válida e auditável; OLS energia-mercado é explicitamente exploratória após desempenho fraco fora da amostra. |
| Interface | `app.py` | Layout vertical consistente; ainda reúne definição de gráficos, carregamento, filtros, execução de mercado e renderização em um arquivo extenso. |
| Qualidade | `tests/`, `docs/ci/quality.yml` | 16 testes e fallback de FRED existem; testes ainda são limitados em falhas de fonte, schema, outliers e estabilidade de forecast. CI é template e cobre apenas compilação/testes. |

## Inventário dos dados locais

| Fonte | Observações | Cobertura | Qualidade inicial |
|---|---:|---|---|
| FRED `TOTALSA` | 607 meses | 01/1976–07/2026 | Sem duplicatas, sem valores ausentes e sem lacunas mensais superiores a 35 dias. |
| EPA `vehicles.csv` | 50.242 configurações × 84 colunas | 1984–2027 | IDs únicos; campos principais completos; `cylinders` e `displ` têm 3,22% de ausências. |
| Energia FRED/EIA/BLS | 574 meses | 11/1978–08/2026 | Sem duplicatas; séries de gasolina e diesel possuem início posterior e, por isso, 24,56% e 32,06% de ausências no painel consolidado. |

> As ausências nas séries de gasolina e diesel decorrem principalmente da diferença de cobertura histórica entre as fontes, não de uma imputação falha. A nova camada deve comunicar essa disponibilidade por série e usar somente a interseção temporal apropriada em modelos externos.

## Fragilidades técnicas priorizadas

A ingestão de FRED e das séries de energia usa leituras diretas de CSV. O FRED principal possui fallback local, porém não há timeout explícito, política de tentativas, controle de status, metadados de atualização ou validação de schema reutilizável. O script de energia não possui fallback em falha de rede.

O núcleo de mercado usa três modelos, bootstrap iid de resíduos e seleção apenas por MAPE médio. Isso é adequado como ponto de partida, mas exige métricas complementares, diagnósticos de resíduos mais completos e uma política de incerteza que respeite autocorrelação quando houver evidência de dependência residual.

O planejamento linear é economicamente legível, mas seus custos e capacidade são parâmetros de cenário. A interface deve distingui-los como hipóteses e fornecer cenários de choque explícitos, em vez de apresentar o resultado como um plano observado de empresa.

A MLP usa separação temporal de ano-modelo e evita entradas diretamente derivadas do alvo. Contudo, a camada precisa persistir metadados completos de treinamento, importância por permutação e análise estruturada de erros por tecnologia/segmento. O OLS com energia tem R² negativo fora da amostra e deve permanecer como diagnóstico explicativo, não ser promovido como previsão decisória.

A aplicação recompõe dados, agregações e o fluxo de mercado a cada rerun, inclusive tentando consultar fonte externa. A refatoração deve separar cache de dados, cache de análise e artefatos de modelo para reduzir latência e exposição desnecessária a APIs.

## Segurança e reprodutibilidade

A inspeção de arquivos versionados não encontrou segredos, credenciais, arquivos temporários ou dependências quebradas. O `.gitignore` protege `.env` e `.streamlit/secrets.toml`. As versões de dependência possuem faixas, mas não há *lock file*; um arquivo de ambiente de desenvolvimento com versões reproduzíveis será justificado na etapa de configuração.

## Direção de evolução

A arquitetura-alvo separará contratos de dados, ingestão, qualidade, preparo de série, motores de forecast/incerteza, cenários, otimização, veículo, energia, decisão e apresentação. O objetivo é manter a funcionalidade atual, reduzir acoplamento e tornar cada decisão quantificável, explicável e testável.
