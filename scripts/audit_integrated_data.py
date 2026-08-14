"""Confere os dados de mercado, catálogo EPA e preços de energia."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from energy_intelligence import load_energy_prices  # noqa: E402
from vehicle_intelligence import load_vehicle_data, vehicle_universe_metadata  # noqa: E402


def pct(count: int, total: int) -> str:
    return f"{count / total * 100:.1f}%" if total else "—"


def main() -> None:
    vehicles = load_vehicle_data(ROOT / "data" / "EPA_vehicles_snapshot.csv")
    energy = load_energy_prices(ROOT / "data" / "energy_price_snapshot.csv")
    market = pd.read_csv(ROOT / "data" / "TOTALSA_snapshot.csv", parse_dates=["observation_date"])
    meta = vehicle_universe_metadata(vehicles)
    n = len(vehicles)
    fields = ["comb08", "combE", "co2TailpipeGpm", "fuelCost08", "cylinders", "displ", "range", "rangeCity", "rangeHwy"]
    coverage = "\n".join(
        f"| `{field}` | {int(vehicles[field].notna().sum()):,} | {pct(int(vehicles[field].notna().sum()), n)} |"
        for field in fields
    )
    powertrains = vehicles.groupby("powertrain").size().sort_values(ascending=False).reset_index(name="configuracoes")
    powertrain_rows = "\n".join(
        f"| {row.powertrain} | {int(row.configuracoes):,} | {pct(int(row.configuracoes), n)} |"
        for row in powertrains.itertuples(index=False)
    )
    energy_rows = "\n".join(
        f"| {column} | {int(energy[column].notna().sum()):,} | {energy.dropna(subset=[column])['data'].min():%m/%Y}–{energy.dropna(subset=[column])['data'].max():%m/%Y} |"
        for column in ["gasolina_usd_gal", "diesel_usd_gal", "eletricidade_usd_kwh"]
    )
    report = f"""# Auditoria de Integração dos Datasets

## Visão geral

| Camada | Registros | Cobertura | Papel analítico |
|---|---:|---|---|
| Mercado FRED `TOTALSA` | {len(market):,} meses | {market["observation_date"].min():%m/%Y}–{market["observation_date"].max():%m/%Y} | Série agregada de demanda de veículos leves. |
| Catálogo EPA `vehicles.csv` | {n:,} configurações | {meta["ano_inicial"]}–{meta["ano_final"]} | Produto, combustível, eficiência, emissões e tecnologia. |
| Preços de energia | {len(energy):,} meses no painel consolidado | {energy["data"].min():%m/%Y}–{energy["data"].max():%m/%Y} | Preço nacional de gasolina/diesel e preço urbano médio de eletricidade. |

## Por que o painel tinha 2025–2027

O intervalo de 2025–2027 foi apenas o **filtro inicial de leitura** para evitar dezenas de marcas históricas e mais de cinquenta mil configurações em uma mesma visualização. Ele não era uma limitação do dataset. O catálogo completo contém **{n:,} configurações** entre **{meta["ano_inicial"]} e {meta["ano_final"]}**, e a versão integrada passa a abrir o universo completo por padrão, mantendo filtros como recurso de exploração.

## Cobertura de campos EPA

| Campo | Configurações não nulas | Cobertura |
|---|---:|---:|
{coverage}

## Tecnologias de propulsão no catálogo completo

| Tecnologia | Configurações | Participação no catálogo |
|---|---:|---:|
{powertrain_rows}

## Séries de preço de energia

| Série mensal consolidada | Observações não nulas | Cobertura disponível |
|---|---:|---|
{energy_rows}

## Conexões válidas entre as camadas

A série de mercado não contém marca, modelo ou combustível. Portanto, ela é conectada ao catálogo de produto por **cenário analítico**, e não por uma chave de venda inexistente: o forecast de mercado dimensiona uma demanda agregada, enquanto o catálogo EPA mostra quais tecnologias, segmentos e atributos técnicos podem ser comparados. As séries de energia conectam-se ao catálogo por tipo de combustível e pelas unidades de consumo da EPA para produzir custo energético de referência por 100 milhas.

> A integração é conceitual e metodológica: ela não imputa venda por veículo nem transforma a base EPA em participação de mercado. O painel expõe essa separação em cada módulo.
"""
    (ROOT / "docs" / "AUDITORIA_INTEGRACAO_TOTAL.md").write_text(report, encoding="utf-8")
    print(f"Auditoria criada: {n:,} configurações EPA | {len(market):,} meses FRED | {len(energy):,} meses energia")


if __name__ == "__main__":
    main()
