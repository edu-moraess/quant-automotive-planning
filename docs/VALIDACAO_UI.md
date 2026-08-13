# Validação visual do painel

A execução local do Streamlit carregou a página principal sem erro visível. A tela apresentou o cabeçalho Quant, o aviso de escopo didático, cinco cartões de KPI, o insight executivo, as cinco etapas do raciocínio quantitativo, as seis abas analíticas e o gráfico histórico. O log confirmou o servidor ativo na porta 8501.

A inspeção identificou um ponto de usabilidade: o controle de participação de mercado foi originalmente configurado como uma fração decimal (`0.08`) com formatação percentual direta, o que podia exibir `0%` na barra lateral. O controle será convertido para uma escala de 2% a 20%, com transformação interna para a fração usada no modelo, evitando ambiguidade para o usuário.

Os resultados observados na execução inicial foram: modelo selecionado `Regressão com defasagens`, MAPE médio de aproximadamente `3,97%`, demanda base de aproximadamente `666.978 veículos`, utilização média de capacidade de `98,8%` e backlog final de `0 veículos`. Esses valores dependem da data de atualização da série pública e das premissas editáveis.

Após recarregar a sessão, o controle passou a apresentar corretamente a escala de `2%` a `20%`, com valor padrão de `8%`. A renderização do cabeçalho, dos KPIs, do gráfico histórico, da barra lateral e da navegação por abas permaneceu íntegra. A validação visual final não identificou mensagens de erro na página inicial.

Durante a verificação da aba de modelos após a inclusão da ACF residual, a sessão local manteve em cache um resultado calculado pela versão anterior do núcleo analítico e apresentou `KeyError: residual_acf`. A causa foi identificada como invalidação insuficiente da cache do Streamlit quando um módulo importado muda. A aplicação será ajustada com uma versão explícita de cache, de modo que a atualização do núcleo force novo cálculo e elimine a inconsistência.

A primeira tentativa de correção por chave versionada e reinício do processo não eliminou o resultado antigo visto pela sessão do Streamlit. Para tornar o comportamento determinístico neste painel acadêmico, a próxima revisão removerá a cache de dados do fluxo completo. Isso evita incompatibilidade entre estruturas de resultado após uma atualização de código, com um custo de execução aceitável para uma série mensal de cerca de 600 observações.

Em uma navegação nova após a remoção da cache, o painel iniciou normalmente o processamento completo, exibindo o estado `Executando diagnóstico, backtest, previsão e otimização...` sem reapresentar o `KeyError` antes de a renderização terminar. A próxima verificação confirmará a conclusão e o conteúdo da aba de modelos.

A validação final foi concluída em uma sessão nova. A aba **Modelos & validação** renderizou sem exceções e exibiu a comparação de MAPE, a tabela dos três modelos, o histograma de resíduos, a **ACF dos resíduos fora da amostra** e a tabela do teste de Ljung-Box. O erro `KeyError: residual_acf` foi resolvido pela remoção da cache do fluxo completo e reinicialização limpa do painel.
