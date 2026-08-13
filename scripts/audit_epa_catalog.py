"""Gera um relatório reprodutível de auditoria do snapshot EPA incluído no projeto."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vehicle_intelligence import brand_registry, load_vehicle_data, vehicle_universe_metadata  # noqa: E402


def main() -> None:
    source = ROOT / "data" / "EPA_vehicles_snapshot.csv"
    data = load_vehicle_data(source)
    metadata = vehicle_universe_metadata(data)
    registry = brand_registry(data)
    latest_year = metadata["ano_final"]
    recent_floor = latest_year - 2
    recent = registry[registry["ano_final"] >= recent_floor]
    historical = registry[registry["ano_final"] < recent_floor]
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    representative_names = ["Chevrolet", "Ford", "Toyota", "Tesla", "Rivian", "Lucid", "Pontiac", "Saab", "Geo", "AMC"]
    examples = registry[registry["make"].isin(representative_names)].sort_values("make")
    example_rows = "\n".join(
        f"| {row.make} | {int(row.ano_inicial)} | {int(row.ano_final)} | {int(row.modelos):,} | {int(row.configuracoes):,} | {row.presenca_no_snapshot} |"
        for row in examples.itertuples(index=False)
    )

    report = f"""# Auditoria do Catálogo EPA

## Resultado

O arquivo `EPA_vehicles_snapshot.csv` é uma cópia local do arquivo público `vehicles.csv` do [FuelEconomy.gov](https://www.fueleconomy.gov/feg/download.shtml), da U.S. Environmental Protection Agency. A página oficial informa que os dados de economia de combustível são derivados de testes do National Vehicle and Fuel Emissions Laboratory da EPA e de dados de fabricantes submetidos sob supervisão da agência [1].

| Indicador | Valor |
|---|---:|
| Registros de configuração no snapshot | {metadata['observacoes']:,} |
| Valores distintos em `make` | {metadata['marcas']:,} |
| Combinações distintas de marca e modelo | {metadata['modelos']:,} |
| Primeiro ano-modelo | {metadata['ano_inicial']} |
| Último ano-modelo | {metadata['ano_final']} |
| Marcas com registro EPA em {recent_floor}–{latest_year} | {len(recent):,} |
| Marcas somente históricas antes de {recent_floor} | {len(historical):,} |
| SHA-256 do snapshot | `{digest}` |

## Significado de “marca”

A plataforma mostra exatamente os valores literais do campo `make` do arquivo da EPA. O campo identifica o fabricante conforme registrado pela fonte para aquela configuração de veículo. Como a série abrange décadas, a lista inclui nomes contemporâneos e históricos. O painel não normaliza conglomerados, não deduz propriedade societária e não declara que uma marca esteja comercialmente ativa apenas porque aparece no arquivo.

> O status exibido pela plataforma é apenas temporal: “Registro EPA em {recent_floor}–{latest_year}” significa que o nome aparece em pelo menos uma configuração desse intervalo no snapshot. “Somente histórico até AAAA” significa que o último ano-modelo observado para o nome foi AAAA.

## Exemplos de rastreabilidade

| Nome literal no campo `make` | Primeiro ano | Último ano | Modelos | Configurações | Presença no snapshot |
|---|---:|---:|---:|---:|---|
{example_rows}

## Limites de interpretação

O catálogo EPA é adequado para analisar especificações, eficiência e abrangência técnica de configurações. Ele não informa unidades vendidas, receita, preço de transação, participação de mercado, rentabilidade ou qualidade. A EPA também observa que estimativas de MPG podem ser revisadas quando novas informações indicam que valores de etiqueta estavam altos [1] [2].

## Referências

[1]: https://www.fueleconomy.gov/feg/download.shtml "FuelEconomy.gov — Download Fuel Economy Data"
[2]: https://www.epa.gov/compliance-and-fuel-economy-data/data-cars-used-testing-fuel-economy "EPA — Data on Cars used for Testing Fuel Economy"
"""
    (ROOT / "docs" / "AUDITORIA_CATALOGO_EPA.md").write_text(report, encoding="utf-8")
    print(f"Relatório criado: docs/AUDITORIA_CATALOGO_EPA.md | {metadata['observacoes']:,} registros | {metadata['marcas']:,} valores make")


if __name__ == "__main__":
    main()
