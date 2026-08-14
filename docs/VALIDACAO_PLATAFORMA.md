# Validação da Plataforma Ampliada

A primeira abertura da **Quant Automotive Intelligence** confirmou o carregamento do catálogo EPA e a nova estrutura de navegação. A barra lateral exibiu filtros de ano-modelo, fabricantes, propulsão e segmento EPA, além dos parâmetros de mercado e planejamento. As referências para FRED e EPA ficaram visíveis na própria interface.

O processamento inicial acionou as camadas de mercado, portfólio, eficiência e cenário operacional sem mensagem de erro. A verificação seguinte observará a renderização completa das abas de produto e de transição tecnológica.

A primeira renderização completa identificou uma colisão de IDs automáticos em gráficos Plotly repetidos entre abas. Foram adicionadas chaves explícitas e únicas aos 17 gráficos da interface. A compilação e os testes continuaram aprovados; a sessão visual exibia a versão anterior até a recarga manual solicitada pelo Streamlit.

Após a reinicialização completa do servidor, uma nova navegação iniciou uma sessão limpa da plataforma corrigida. O primeiro carregamento exibiu apenas o estado transitório padrão do Streamlit; a próxima leitura verificará o conteúdo final e a ausência de colisões de gráficos.

A sessão limpa renderizou a visão integrada sem colisões de gráficos. A aba **Produto & Marcas** também foi validada com sucesso: exibiu 50.242 configurações, 146 fabricantes, 5.737 modelos e 34 segmentos no snapshot EPA, além do gráfico de amplitude por marca, mapa de posicionamento, scorecard por fabricante e estrutura por segmento. Não houve mensagens de erro após a inclusão das chaves únicas.

A aba **Eficiência & Transição** foi validada sem erro. Ela apresentou a composição por propulsão, a tabela consolidada por tecnologia, séries anuais de configurações e eficiência e o mapa competitivo de modelos. A classificação identificou combustão, híbridos, elétricos a bateria, diesel, híbridos plug-in, gás natural e célula a combustível no catálogo EPA.

A versão refinada iniciou com o recorte padrão de ano-modelo 2025–2027 e renomeou o seletor para **Marcas EPA (campo make)**, tornando explícita a procedência dos nomes e evitando misturar marcas históricas com o retrato recente por padrão. O carregamento inicial ocorreu sem mensagens de erro.

A revisão visual confirmou dois ajustes: a **Visão integrada** agora apresenta previsão base e faixa p10–p90, enquanto **Mercado & Validação** preserva a série histórica e os diagnósticos; assim, as abas não repetem o mesmo gráfico. Em **Eficiência & Transição**, o gráfico inicial foi substituído por barras horizontais com percentuais externos, eliminando a sobreposição de rótulos da pizza anterior. A revisão foi feita no recorte padrão recente de 2025–2027.

A auditoria de marcas foi aberta e validada na interface. O registro lista o nome literal EPA, quantidade de configurações e modelos, primeiro e último ano observados e uma presença temporal do snapshot. Exemplos visíveis incluem Chevrolet, Ford, GMC, Dodge, BMW, Toyota, Mercedes-Benz, Nissan, Audi e Volkswagen com registros EPA em 2025–2027. A interface não apresenta esse status como atividade comercial ou participação de mercado.

A primeira revisão da versão redesenhada confirmou que o resumo executivo passou a exibir quatro indicadores, duas visualizações principais e uma única nota de interpretação. A hierarquia está mais enxuta do que a versão exportada no PDF e o carregamento das abas, filtros e fontes ocorreu sem erro visível.

A aba Mercado & Forecast foi revisada visualmente: quatro métricas resumem o resultado, dois gráficos concentram histórico e backtest, e os diagnósticos residuais ficam recolhidos em expander. A estrutura eliminou a repetição com a aba Resumo e preservou as métricas de validação temporal.

As abas Portfólio e Planejamento também foram verificadas. Portfólio concentra quatro métricas, duas leituras técnicas e um scorecard limitado às principais marcas; o registro integral permanece recolhido. Planejamento centraliza cenário operacional, sensibilidade e tabela de cenários, deixando o plano mensal para exportação sob demanda.

A aba Método & Dados foi validada com uma tabela concisa de fontes, fórmulas de custo por 100 milhas, limites das correlações e links para auditoria, pesquisa e proveniência. A revisão final abrangeu Resumo, Portfólio, Energia & Combustível, Mercado & Forecast, Planejamento e Método & Dados.

A versão integrada foi aberta com o seletor padrão em **1984–2027**, confirmando que o catálogo completo passou a ser o universo inicial da interface. Nenhum recorte de 2025–2027 permanece como padrão; filtros ficam disponíveis apenas para exploração opcional.

A aba Modelos integrados foi validada na interface em sequência vertical: métricas OLS, aviso de limitação, gráfico temporal, coeficientes, métricas da rede neural, gráfico de validação e tabela de maiores erros aparecem um após o outro. A validação confirma 47.423 configurações de treino e 2.819 configurações de teste para a rede neural, sem recorte visual de 2025–2027 no restante do catálogo.

A sessão limpa de 14/08/2026 confirmou o carregamento da arquitetura refatorada. A página inicial exibiu o catálogo completo, filtros verticais, parâmetros de forecast, hipóteses operacionais identificadas como **ASSUMPTIONS** e a nova leitura sequencial. A revisão visual não encontrou erro inicial de execução; o resumo mostrou 50.242 configurações EPA, 146 marcas, 5.737 modelos e o forecast selecionado pelo backtest. A nova validação continuará nas abas de energia, modelos, planejamento e método para verificar artefatos, cenários e saúde dos dados.
A aba **Energia & Combustível** foi validada com as séries atuais, custo por 100 milhas, tabela de sensibilidade a choques de preço declarados, matriz de Spearman e comparação controlada. A aba **Modelos integrados** exibiu a OLS com aviso de R² fora da amostra negativo, VIF, rede neural temporal, importância por permutação e erro por propulsão. A leitura permaneceu vertical e sem falhas de carregamento; os diagnósticos reforçam que a OLS é explicativa e que a rede neural apresenta maior erro em elétricos a bateria no período de teste.
A aba **Planejamento** validou os cenários Downside, Base, Upside e Stress, a recomendação textual, a capacidade regular/extra e o backlog sob hipóteses declaradas. A aba **Método & Dados** carregou a tabela de fontes e o perfil de saúde dos três snapshots. A inspeção identificou que a tabela completa de saúde tem colunas demais para leitura confortável; a próxima revisão a dividirá em resumo operacional e detalhes de proveniência recolhidos, preservando a regra de densidade controlada.

Correção em análise — **controle FRED**: a opção de atualização está dentro de um formulário e só é aplicada ao pressionar `Atualizar análise`. A execução online foi reproduzida com sucesso, mas o painel não exibe `source_label`, data de recuperação, última observação nem diferença contra o snapshot. Como o snapshot e a fonte online podem ter a mesma última observação, a ausência desse feedback faz o controle parecer inoperante. O dado de mercado recalculado alimenta Resumo, Mercado & Forecast e Planejamento; Portfólio, Energia & Combustível e Modelos integrados usam apenas EPA/energia/artefatos e não mudam com o controle FRED.

Na primeira abertura após a evolução da proveniência FRED, a interface mostrou `KeyError: market_refresh`. A causa foi um resultado anterior de `st.cache_data`, calculado antes de o novo campo existir, enquanto a função de cache não havia sido invalidada por alteração interna do motor de mercado. A correção em andamento adicionará uma versão explícita ao contrato de cache para forçar nova execução e impedir a reutilização desse payload obsoleto.

A segunda tentativa confirmou que a versão de chave do cache, isoladamente, não resolve uma sessão de desenvolvimento já aberta: o Streamlit recarregou `app.py`, porém o módulo `analysis` importado diretamente permaneceu carregado em memória e expôs a versão anterior de `run_full_analysis`. Para a validação local é necessário reiniciar o processo Streamlit; na publicação, um novo processo já carrega o módulo atualizado. A interface também receberá uma proteção de compatibilidade para nunca interromper a página caso um payload legado seja encontrado.

Após reiniciar o Streamlit, a validação visual confirmou que o painel carrega sem `KeyError` e expõe o estado inicial: **Snapshot FRED aplicado**, 607 observações de 1976-01 a 2026-07, com o motivo de não consultar a fonte online. A própria nota declara que a mesma série alimenta Resumo, Mercado & Forecast e Planejamento.

Na primeira tentativa de marcar e submeter a consulta online, a nota continuou indicando **Snapshot FRED aplicado**. Como o formulário não expõe visualmente o estado selecionado no extrator, a próxima verificação será feita no estado do elemento antes de concluir que existe falha na ação de submissão.

A inspeção do DOM mostrou que o checkbox ainda estava `false` após o primeiro clique, porque a interação havia atingido o rótulo. Foi então acionado diretamente o elemento de entrada do controle; a confirmação do estado e a submissão seguem na validação final.

A automação do navegador não conseguiu reter a marcação do checkbox mesmo ao acionar o campo e a tecla de espaço; o estado no DOM permaneceu `false`. Isso não altera o diagnóstico do produto, pois a aplicação mostra corretamente o estado de snapshot. A validação da ramificação online será feita diretamente pelo motor de mercado, usando a mesma URL e os mesmos parâmetros do painel.

A validação final mostrou a indicação local de proveniência na aba **Resumo** e na aba **Mercado & Forecast**: ambas declaram `Snapshot local versionado`, 607 observações e cobertura 1976-01–2026-07. Em Mercado & Forecast, essa indicação aparece antes do histórico, da comparação walk-forward, das métricas e dos diagnósticos, deixando explícito o conjunto que será recalculado quando a série FRED mudar.

O perfil da atualização FRED encontrou cerca de 1,5–2,3 s na consulta de rede, ~0,8 s no backtest/forecast e ~0,14 s no planejamento. A versão otimizada separa essas etapas: quando a série consultada for idêntica, o painel realiza a nova consulta, mas reutiliza backtest, bootstrap e forecast; o planejamento só é recalculado se forecast ou hipóteses mudarem. O timeout da atualização FRED foi limitado a 4 s por tentativa, com duas tentativas e fallback local. A sessão reiniciada abriu sem erros e manteve o status de snapshot e as visualizações de mercado.

A abertura compactada foi validada visualmente. O cabeçalho passou a ocupar menos altura, o estado do FRED aparece como uma única linha recolhida e as abas surgem imediatamente abaixo desse status. Os quatro indicadores de universo e a nota de escopo foram movidos para dentro da aba **Resumo**, eliminando o longo bloco fixo que empurrava a navegação para baixo.

A correção visual foi validada. O texto superior foi reduzido para `Automotive Intelligence`, sem subtítulo em maiúsculas, eliminando o recorte observado no topo. Os indicadores do Resumo agora usam linhas compactas em sequência vertical; configurações, marcas, modelos, filtro, modelo selecionado, MAPE e mix eletrificado aparecem sem cartões altos nem os grandes intervalos verticais anteriores. A navegação continua imediatamente abaixo do status FRED recolhido.
