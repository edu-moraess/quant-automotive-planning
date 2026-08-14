# Camada gratuita de features para demanda automotiva

## Propósito

Esta camada adiciona **features exógenas rastreáveis** ao planejamento automotivo sem mudar artificialmente o alvo de vendas. Enquanto não existir uma base comercial de vendas ou registros por `mês × marca × modelo`, o sistema entrega um painel de mercado agregado com TOTALSA enriquecido por macroeconomia, energia e eventos. Quando a base-alvo desagregada estiver disponível, o mesmo contrato pode ser unido por competência, marca e modelo sem reescrever os clientes de fonte.

> O catálogo EPA descreve produtos; ele não é tratado como série de vendas. A FRED TOTALSA descreve o mercado agregado; ela não é decomposta em marcas ou modelos sem uma fonte observada para isso.

## Arquitetura

| Camada | Responsabilidade | Saída |
|---|---|---|
| `src/data/sources/` | Clientes resilientes de FRED, EIA, News API, EPA e NHTSA | Dados normalizados com data da observação e data de disponibilidade |
| `src/data/temporal.py` | Regras point-in-time, agregação mensal e defasagens | Features sem observações futuras |
| `src/data/feature_builder.py` | Orquestra ingestão, fallback e construção de indicadores | Mercado mensal e painel de eventos por entidade |
| `src/data/feature_store.py` | Parquet particionado e manifesto operacional | Tabelas por fonte/mês/entidade e status para a interface |
| `scripts/refresh_free_features.py` | Execução reproduzível local ou automatizada | Resumo JSON sem segredos |
| `.github/workflows/refresh-free-features.yml` | Atualização diária de notícias e mensal de macro/energia | Commits apenas de dados derivados e manifesto |

Os clientes usam `httpx` assíncrono, retry limitado com `tenacity`, cache local em disco e mensagens estruturadas por fonte. O cache de respostas brutas fica em `data/feature_cache/`, que é ignorado pelo Git. O feature store preserva apenas tabelas normalizadas e indicadores agregados.

## Contrato temporal

Cada observação possui uma coluna `disponivel_em`. A função `enforce_point_in_time` elimina linhas com disponibilidade posterior ao instante `as_of`; `assert_no_future_availability` interrompe a transformação se ainda existir qualquer informação futura. A FRED consulta a API com `realtime_start` e `realtime_end` na data de corte, porque a API disponibiliza observações e datas de vintage/revisão [1]. Para EIA, o lag de publicação é explícito e conservador: sete dias para gasolina/diesel e quarenta e cinco dias para eletricidade residencial, ambos configuráveis no `FeatureBuilder`.

As notícias são filtradas pelo `publishedAt`, deduplicadas por URL ou assinatura determinística e congeladas na execução. O modelo recebe apenas indicadores numéricos mensais; títulos, descrições e conteúdo não são persistidos no feature store como variáveis de entrada.

| Fonte | Features iniciais | Granularidade | Observação temporal |
|---|---|---|---|
| FRED | TOTALSA, desemprego, CPI, juros, confiança, produção e varejo | Mensal ou agregada | Vintage na data de corte quando a série permitir |
| EIA | Gasolina, diesel, eletricidade, diferenciais e variações de 1/3/12 meses | Semanal/mensal convertida a mensal | Lag explícito por série |
| News API | Cobertura, sentimento lexical, recall, lançamento, produção, incentivo e intensidade temática | Diário agregado a mensal | Artigo publicado até `as_of`; deduplicação antes da agregação |
| EPA | Eficiência, emissões, combustível, autonomia e tecnologia | Configuração/ano-modelo | Atributo técnico de produto, não alvo de vendas |
| NHTSA | Recall e reclamação por veículo | Evento por ano/marca/modelo | Somente registros com data de recebimento/publicação |

A FRED disponibiliza tanto consulta de observações quanto consulta de datas de vintage [1]. A EIA oferece dados de energia gratuitos por API, incluindo petróleo e eletricidade [2]. News API permite recuperação de artigos por termo, data, domínio e idioma; no plano de desenvolvimento a chave é gratuita [3]. A NHTSA publica APIs e arquivos para recalls e reclamações, inclusive consultas por ano, marca e modelo [4].

## Feature store

A persistência segue o formato `Parquet` e as partições abaixo:

```text
feature_store/
  source=fred/month=YYYY-MM/data.parquet
  source=eia/month=YYYY-MM/data.parquet
  source=news/month=YYYY-MM/marca=<marca>/modelo=<modelo>/data.parquet
  source=feature_builder/month=YYYY-MM/[marca=<marca>/modelo=<modelo>/]data.parquet
  manifest.json
```

O manifesto guarda somente estado, cobertura, latência, número de linhas, uso de cache e mensagem operacional. O dashboard lê esse manifesto na barra lateral e nunca executa a coleta externa durante a renderização.

## Segredos e execução local

Copie `.streamlit/secrets.example.toml` para `.streamlit/secrets.toml` e preencha as chaves somente no ambiente local. O arquivo real está ignorado pelo Git.

```toml
[feature_sources]
FRED_API_KEY = "..."
EIA_API_KEY = "..."
NEWS_API_KEY = "..."
```

A execução manual usa variáveis de ambiente com os mesmos nomes, o que mantém o script independente do Streamlit:

```bash
export FRED_API_KEY="..."
export EIA_API_KEY="..."
export NEWS_API_KEY="..."
python scripts/refresh_free_features.py --sources fred,eia,news --start 2018-01-01
```

Sem chaves, o pipeline não falha: TOTALSA é carregada do snapshot local e o manifesto informa que as demais fontes não foram consultadas. Nenhum segredo é aceito por argumento de linha de comando, escrito em logs, armazenado em cache ou enviado ao front-end.

## Atualização automatizada

O workflow do repositório executa News API diariamente e FRED/EIA mensalmente. Para ativá-lo, adicione `FRED_API_KEY`, `EIA_API_KEY` e `NEWS_API_KEY` aos segredos criptografados do repositório. O workflow usa as chaves apenas no processo de execução e cria commit somente quando o feature store muda.

A rotina diária consulta uma janela curta de notícias e atualiza as partições de evento. A rotina mensal reprocessa o histórico macro/energético e preserva a disponibilidade por data. O processo é determinístico; não utiliza uma tarefa de IA recorrente para fazer requisições que podem ser executadas por código.

## Expansão para vendas por marca e modelo

Quando uma base de vendas ou novos registros for licenciada, a chave de integração recomendada é:

```text
mês × região × marca × modelo × ano-modelo × propulsão
```

O novo alvo deve ser `vendas_ou_registros_no_mês`. O painel de eventos já produz `mês × marca × modelo` quando a consulta define a entidade; os atributos EPA podem ser unidos por marca/modelo/ano-modelo e as features de mercado entram por mês e região. Uma base comercial como S&P Global Mobility ou Omdia/Wards continua sendo necessária para cobertura completa de vendas por modelo; essas fontes são comerciais e não foram usadas como feed do projeto [5] [6].

## Validação

Os testes em `tests/test_feature_layer.py` usam `httpx.MockTransport` e cobrem contratos de FRED, EIA, News API e NHTSA, cache local, fallback TOTALSA e bloqueio de observações futuras. A suíte não faz chamadas externas nem requer chaves.

## Referências

[1]: https://fred.stlouisfed.org/docs/api/fred/series_observations.html "FRED — Observations by real-time period"
[2]: https://www.eia.gov/opendata/ "U.S. Energy Information Administration — Open Data"
[3]: https://newsapi.org/docs "News API — Documentation"
[4]: https://www.nhtsa.gov/nhtsa-datasets-and-apis "NHTSA — Datasets and APIs"
[5]: https://www.marketplace.spglobal.com/en/datasets/global-new-vehicle-registrations-(248) "S&P Global Mobility — Global New Vehicle Registrations"
[6]: https://omdia.tech.informa.com/collections/afcit021/vehicle-sales--us-annual "Omdia / Wards Intelligence — Vehicle Sales U.S."
