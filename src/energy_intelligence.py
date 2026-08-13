"""Análises de energia e combustível para a plataforma automotiva.

A camada combina séries oficiais de preço de energia com atributos técnicos da
EPA. Preços nacionais servem como referência macro; não representam tarifas
locais, contratos de frota ou desembolso individual.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ENERGY_PRICE_COLUMNS = {
    "gasolina_usd_gal": "Gasolina regular",
    "diesel_usd_gal": "Diesel",
    "eletricidade_usd_kwh": "Eletricidade",
}


def load_energy_prices(source: str | Path) -> pd.DataFrame:
    """Lê o snapshot mensal de preços nacionais de energia."""
    prices = pd.read_csv(source, parse_dates=["data"])
    for column in ENERGY_PRICE_COLUMNS:
        prices[column] = pd.to_numeric(prices[column], errors="coerce")
    return prices.sort_values("data").reset_index(drop=True)


def latest_energy_snapshot(prices: pd.DataFrame) -> pd.DataFrame:
    """Retorna última observação disponível por série, preservando a data."""
    rows: list[dict[str, object]] = []
    for column, label in ENERGY_PRICE_COLUMNS.items():
        valid = prices.dropna(subset=[column])[["data", column]].iloc[-1]
        rows.append({"energia": label, "coluna": column, "data": valid["data"], "preco": float(valid[column])})
    return pd.DataFrame(rows)


def energy_price_index(prices: pd.DataFrame, periods: int = 48) -> pd.DataFrame:
    """Transforma séries de unidades diferentes em índices comparáveis, base 100."""
    recent = prices.tail(periods).copy()
    records: list[pd.DataFrame] = []
    for column, label in ENERGY_PRICE_COLUMNS.items():
        series = recent[["data", column]].dropna().rename(columns={column: "preco"})
        if series.empty:
            continue
        base = float(series.iloc[0]["preco"])
        series["indice_base_100"] = series["preco"] / base * 100
        series["energia"] = label
        records.append(series)
    if not records:
        return pd.DataFrame(columns=["data", "preco", "indice_base_100", "energia"])
    return pd.concat(records, ignore_index=True)


def classify_energy_source(data: pd.DataFrame) -> pd.Series:
    """Associa uma configuração à fonte de energia primária para custo comparável."""
    fuel = data.get("fuelType1", pd.Series("", index=data.index)).fillna("").astype(str).str.lower()
    powertrain = data.get("powertrain", pd.Series("", index=data.index)).fillna("").astype(str)
    is_electric = powertrain.eq("Elétrico a bateria")
    is_diesel = fuel.str.contains("diesel", regex=False)
    is_ethanol = fuel.str.contains("ethanol|e85", regex=True)
    is_cng = fuel.str.contains("natural gas|cng", regex=True)
    is_hydrogen = fuel.str.contains("hydrogen", regex=False)
    is_phev = powertrain.eq("Híbrido plug-in")
    return pd.Series(
        np.select(
            [is_electric, is_phev, is_diesel, is_ethanol, is_cng, is_hydrogen],
            ["Eletricidade", "Híbrido plug-in", "Diesel", "Etanol / E85", "Gás natural", "Hidrogênio"],
            default="Gasolina",
        ),
        index=data.index,
        dtype="string",
    )


def _latest_price_value(prices: pd.DataFrame, column: str) -> float:
    return float(prices.dropna(subset=[column]).iloc[-1][column])


def add_energy_cost_estimate(data: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Adiciona custo energético de referência por 100 milhas quando comparável.

    Gasolina e diesel usam preço nacional por galão dividido por MPG. Veículos
    elétricos a bateria usam consumo ``combE`` (kWh por 100 milhas no arquivo
    EPA) multiplicado por preço nacional por kWh. PHEVs e outros combustíveis
    ficam sem estimativa, pois exigem premissas de uso ou fontes de preço não
    harmonizadas nesta camada.
    """
    result = data.copy()
    result["fonte_energia"] = classify_energy_source(result)
    result["custo_energia_100mi_usd"] = np.nan
    mpg = pd.to_numeric(result.get("comb08"), errors="coerce")
    comb_e = pd.to_numeric(result.get("combE"), errors="coerce")
    gas_price = _latest_price_value(prices, "gasolina_usd_gal")
    diesel_price = _latest_price_value(prices, "diesel_usd_gal")
    electricity_price = _latest_price_value(prices, "eletricidade_usd_kwh")

    gasoline_mask = result["fonte_energia"].eq("Gasolina") & mpg.gt(0)
    diesel_mask = result["fonte_energia"].eq("Diesel") & mpg.gt(0)
    electric_mask = result["fonte_energia"].eq("Eletricidade") & comb_e.gt(0)
    result.loc[gasoline_mask, "custo_energia_100mi_usd"] = gas_price / mpg[gasoline_mask] * 100
    result.loc[diesel_mask, "custo_energia_100mi_usd"] = diesel_price / mpg[diesel_mask] * 100
    result.loc[electric_mask, "custo_energia_100mi_usd"] = comb_e[electric_mask] * electricity_price
    return result


def energy_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Consolida tecnologia, eficiência, emissões e custo energético por fonte."""
    if data.empty:
        return pd.DataFrame()
    return (
        data.groupby("fonte_energia", as_index=False)
        .agg(
            configuracoes=("id", "count"),
            marcas=("make", "nunique"),
            modelos=("modelo_chave", "nunique"),
            eficiencia_mediana=("eficiencia_valida", "median"),
            co2_mediano_g_milha=("co2_valido", "median"),
            custo_epa_anual_mediano_usd=("custo_anual_valido", "median"),
            custo_energia_100mi_mediano_usd=("custo_energia_100mi_usd", "median"),
        )
        .sort_values("configuracoes", ascending=False)
        .reset_index(drop=True)
    )


def spearman_correlation_matrix(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula matriz de Spearman e contagem de pares válidos por indicador."""
    columns = {
        "eficiencia_valida": "Eficiência (MPG/MPGe)",
        "custo_anual_valido": "Custo EPA anual (US$)",
        "custo_energia_100mi_usd": "Energia por 100 mi (US$)",
        "co2_valido": "CO₂ de escapamento (g/mi)",
        "displ": "Cilindrada (L)",
        "cylinders": "Cilindros",
    }
    available = [column for column in columns if column in data.columns]
    numeric = data[available].apply(pd.to_numeric, errors="coerce").rename(columns=columns)
    correlations = numeric.corr(method="spearman", min_periods=20)
    pair_counts = pd.DataFrame(index=correlations.index, columns=correlations.columns, dtype=float)
    for row in correlations.index:
        for column in correlations.columns:
            pair_counts.loc[row, column] = int(numeric[[row, column]].dropna().shape[0])
    return correlations, pair_counts


def strongest_spearman_pairs(correlations: pd.DataFrame, pair_counts: pd.DataFrame, limit: int = 6) -> pd.DataFrame:
    """Retorna pares únicos de maior associação absoluta, com n válido."""
    rows: list[dict[str, object]] = []
    labels = list(correlations.columns)
    for i, left in enumerate(labels):
        for right in labels[i + 1 :]:
            rho = correlations.loc[left, right]
            if pd.notna(rho):
                rows.append({"indicador_a": left, "indicador_b": right, "rho_spearman": float(rho), "n": int(pair_counts.loc[left, right])})
    if not rows:
        return pd.DataFrame(columns=["indicador_a", "indicador_b", "rho_spearman", "n"])
    return pd.DataFrame(rows).assign(abs_rho=lambda frame: frame["rho_spearman"].abs()).sort_values(["abs_rho", "n"], ascending=[False, False]).head(limit).drop(columns="abs_rho").reset_index(drop=True)
