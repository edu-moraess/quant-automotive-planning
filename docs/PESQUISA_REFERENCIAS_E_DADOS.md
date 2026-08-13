# Pesquisa de Referências e Dados — Refinamento Analítico

## Padrões de comparação e foco visual

A revisão de plataformas públicas indica que comparações de veículos funcionam melhor quando limitadas a um conjunto pequeno e explicitamente selecionado. A ferramenta **Compare Side-by-Side** do FuelEconomy.gov permite comparar até quatro veículos de cada vez [1]. A nova interface seguirá esse princípio: comparações serão construídas a partir de seleções controladas, não de scatter plots ou tabelas que exibem centenas de modelos simultaneamente.

O **Alternative Fuels Data Center** organiza preços por tipo de combustível, explica que preços variam por localização e período e separa o retrato de preços do cálculo de custo de veículos [2]. A nova camada de energia terá o mesmo cuidado: exibirá preço de energia, eficiência do veículo e custo operacional como medidas distintas, com sua unidade e fonte explícitas.

| Referência | Princípio adotado na plataforma |
|---|---|
| FuelEconomy.gov — comparação lado a lado | Seleção explícita e poucos veículos por comparação. |
| AFDC — preço de combustíveis | Separação entre preço da energia, combustível e cálculo de uso. |
| EIA — Gasoline and Diesel Fuel Update | Série temporal com unidade, data de atualização e origem expostas. |
| EPA — catálogo de veículos | Atributo de configuração sem inferência de venda ou participação comercial. |

## Dados reais para cruzamento de energia

A EIA publica preços nacionais semanais de gasolina regular e diesel em dólares por galão, incluindo impostos, com informações de método e variabilidade amostral [3]. As séries podem ser acessadas sem autenticação também no FRED como `GASREGW` e `GASDESW`.

A série FRED `APU000072610`, com origem no Bureau of Labor Statistics, mede mensalmente o preço médio de eletricidade por quilowatt-hora na média urbana dos Estados Unidos [4]. Ela será alinhada mensalmente às séries semanais de gasolina e diesel apenas para contexto temporal comparável.

A base EPA tem campos de eficiência combinada, emissões de escapamento, cilindrada, custo anual estimado e consumo energético para configurações de veículos. As correlações serão calculadas somente em subconjuntos comparáveis e terão o número de observações apresentado. Para variáveis monetárias e de eficiência, serão preferidas correlações de Spearman, pois as relações são monotônicas e podem ser assimétricas.

> Preços nacionais de energia não substituem preço local, tarifa residencial específica ou preço contratual de frota. Por isso, a plataforma os trata como referência macro de custo de energia, não como estimativa individual de abastecimento.

## Referências

[1]: https://www.fueleconomy.gov/feg/Find.do?action=sbsSelect "FuelEconomy.gov — Compare Side-by-Side"
[2]: https://afdc.energy.gov/fuels/prices.html "U.S. Department of Energy — Alternative Fuel Price Report"
[3]: https://www.eia.gov/petroleum/gasdiesel/ "U.S. EIA — Gasoline and Diesel Fuel Update"
[4]: https://fred.stlouisfed.org/series/APU000072610 "FRED / BLS — Electricity per Kilowatt-Hour in U.S. City Average"
[5]: https://www.fueleconomy.gov/feg/download.shtml "U.S. EPA / FuelEconomy.gov — Download Fuel Economy Data"
