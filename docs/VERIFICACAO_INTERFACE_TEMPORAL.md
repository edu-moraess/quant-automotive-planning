# Verificação de Interface — Formatação Temporal

**Data:** 14/08/2026  
**Ambiente:** execução local Streamlit em `http://localhost:8501`

A tela principal carregou sem erro de execução após a atualização temporal. O snapshot local foi reconhecido como fonte de mercado, com **607 observações** e cobertura exibida como `1976-01–2026-07`. A tela de resumo também exibiu **50.242 configurações EPA**, **146 marcas**, **5.737 modelos**, modelo selecionado **Regressão com defasagens** e MAPE fora da amostra de **3,97%**.

A verificação confirmou que as abas de **Planejamento** e **Método & Dados** estão disponíveis para navegação na versão carregada. A inspeção subsequente deve confirmar visualmente a célula mensal do plano (`MM/AAAA`) e o timestamp UTC de proveniência (`DD/MM/AAAA HH:MM UTC`).

A aba **Planejamento** carregou sem travamento. Foram exibidos os quatro cenários e os indicadores de capacidade, backlog e risco. O gráfico temporal apresentou competências como `Aug 2026` a `Jan 2027`, sem componente de horário. A área "Hipóteses operacionais e plano mensal" permaneceu recolhida na primeira tentativa de abertura; a inspeção do conteúdo expandido continuará para confirmar a coluna `Data` na tabela e no CSV.

A inspeção do DOM identificou o detalhe mensal como o quinto elemento `summary` da página. A primeira tentativa de acioná-lo por console não foi executada por sintaxe inválida e não alterou a aplicação nem seus dados; a verificação será repetida com uma expressão compatível.

A verificação visual foi concluída para o plano mensal. A tabela expandida apresenta a coluna `Data` como `08/2026`, `09/2026`, `10/2026`, `11/2026`, `12/2026` e `01/2027`, sem `00:00:00`. O gráfico operacional também apresenta o eixo mensal sem horário. A interface continuou responsiva e não exibiu erro de execução durante a abertura da aba e do detalhe mensal.

A aba **Método & Dados** também carregou sem erro. A tabela de saúde exibiu as coberturas como `01/01/1976`, `01/07/2026`, `01/11/1978` e `01/08/2026`, sem horários artificiais. No detalhe de proveniência, os eventos reais preservaram horário e UTC: `13/08/2026 22:19 UTC`, `13/08/2026 22:41 UTC` e `14/08/2026 11:02 UTC`. A correção visual foi confirmada em ambos os contextos críticos.
