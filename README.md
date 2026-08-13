# Quant Automotive Planning

Aplicação Streamlit profissional para **previsão de demanda automotiva e planejamento quantitativo da produção**. O projeto transforma o notebook `planejamento_quantitativo_automotivo_v2.ipynb` em um painel interativo, reproduzível e adequado para apresentação acadêmica, entrevista e estágio em analytics, planejamento ou supply chain.

> **Escopo e integridade.** Este é um caso didático construído com a série pública mensal `TOTALSA`, disponibilizada pelo FRED e atribuída ao U.S. Bureau of Economic Analysis. Não são utilizados dados internos, capacidades reais, mix de produtos, custos ou metas de nenhuma montadora. As premissas de participação, capacidade, estoque e custos são hipóteses editáveis exclusivamente para demonstrar o raciocínio quantitativo.

## O que o projeto entrega

A aplicação cobre o fluxo completo, desde a qualidade dos dados até a decisão operacional. Ela apresenta diagnóstico de continuidade, duplicidades e outliers; teste ADF, decomposição STL, ACF e PACF; comparação de três modelos temporais; backtest walk-forward com janela expansiva; diagnóstico Ljung-Box dos resíduos; previsão de seis meses com faixa p10–p90 via bootstrap; otimização linear do plano de produção; comparação de cenários; análise de sensibilidade; tabelas auditáveis e exportação em CSV.

| Módulo | Resultado principal |
|---|---|
| Visão executiva | KPIs, série histórica e roteiro de defesa em entrevista. |
| Dados & diagnóstico | Qualidade, STL, sazonalidade, variação anual, ADF, ACF e PACF. |
| Modelos & validação | MAPE/MAE/RMSE por modelo e dobra, seleção e Ljung-Box. |
| Previsão & incerteza | Cenários conservador, base e otimista por bootstrap dos resíduos. |
| Produção & sensibilidade | Plano mensal, estoque, backlog, custo, cenários e heatmap. |
| Metodologia | Pergunta de negócio, formulação matemática, limites e referências. |

## Metodologia resumida

A série é obtida do FRED em milhões de veículos a uma taxa anual ajustada sazonalmente (SAAR). A divisão por 12 aparece apenas como aproximação mensal para conversões operacionais; o treinamento é realizado na série oficial. O estudo compara uma referência sazonal ingênua, Holt-Winters aditivo e regressão Ridge com defasagens de 1 e 12 meses, tendência e dummies mensais.

O modelo vencedor é selecionado pela menor MAPE média em validação cruzada temporal walk-forward. Cada janela usa somente o passado para prever o bloco de teste, evitando vazamento temporal. Os resíduos fora da amostra são reamostrados com reposição para construir uma distribuição empírica de demanda e seus percentis 10 e 90.

Na etapa de decisão, a previsão é convertida em veículos para uma carteira hipotética. A programação linear minimiza custos de produção, estoque e ruptura, respeitando uma capacidade mensal. A decisão é mostrada em três cenários e submetida a uma grade de sensibilidade entre capacidade e participação de mercado.

A descrição completa, incluindo equações e referências acadêmicas, está em [`docs/ARQUITETURA_E_METODOLOGIA.md`](docs/ARQUITETURA_E_METODOLOGIA.md).

## Como executar localmente

Recomenda-se Python 3.10 ou superior. Em um terminal, crie e ative um ambiente virtual, instale as dependências e execute o painel:

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

A aplicação tenta consultar a série oficial online. Se a fonte estiver indisponível, utiliza `data/TOTALSA_snapshot.csv`, que é versionado para manter um caminho de contingência. Para atualizar o snapshot de maneira explícita:

```bash
curl --fail --location \
  'https://fred.stlouisfed.org/graph/fredgraph.csv?id=TOTALSA' \
  -o data/TOTALSA_snapshot.csv
```

## Estrutura do repositório

```text
.
├── app.py                              # Interface Streamlit e visualizações
├── src/analysis.py                     # Núcleo analítico testável
├── data/TOTALSA_snapshot.csv           # Snapshot público de contingência
├── docs/ARQUITETURA_E_METODOLOGIA.md   # Metodologia, equações e referências
├── docs/notebook_original_*.ipynb      # Notebook entregue como origem do projeto
├── tests/test_analysis.py              # Testes unitários do núcleo
├── .streamlit/config.toml              # Tema e configuração do painel
├── requirements.txt                    # Dependências Python
├── docs/ci/quality.yml                 # Template de verificação automática de qualidade
```

## Testes e qualidade

Após instalar as dependências, execute:

```bash
python -m pytest -q
python -m compileall -q app.py src
```

O template de integração contínua está em `docs/ci/quality.yml`. Para ativá-lo no GitHub, copie-o para `.github/workflows/quality.yml` e faça um *commit* com uma credencial que tenha permissão para criar ou atualizar *workflows*.

## Como apresentar o projeto

A narrativa recomendada é começar pela pergunta de negócio, mostrar por que um único corte treino/teste seria frágil e explicar a escolha do walk-forward. Em seguida, destaque que complexidade só é aceita se melhorar o erro fora da amostra. A previsão deve ser apresentada com faixa de incerteza empírica, e o plano de produção deve ser discutido como decisão sob restrições, não como consequência automática de um número previsto. Por fim, reconheça os limites do caso e descreva os dados internos necessários para uma evolução real.

## Referências

[1]: https://fred.stlouisfed.org/series/TOTALSA "FRED — Total Vehicle Sales (TOTALSA)"
[2]: https://www.federalreserve.gov/releases/g17/mv_sales_sf.htm "Federal Reserve — Seasonal Factors for Motor Vehicle Sales"
[3]: https://catalog.data.gov/dataset/auto-sales "Bureau of Transportation Statistics — Auto Sales"
[4]: https://www.wessa.net/download/stl.pdf "Cleveland et al. (1990) — STL"
[5]: https://doi.org/10.1093/biomet/65.2.297 "Ljung & Box (1978)"
[6]: https://doi.org/10.1214/aos/1176344552 "Efron (1979) — Bootstrap Methods"

## Licença

Projeto acadêmico e demonstrativo. Consulte a instituição ou responsável pelo projeto antes de utilizar dados proprietários, marcas, resultados ou premissas reais.
