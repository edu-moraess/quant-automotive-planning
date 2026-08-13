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
