"""Camada analítica para inteligência de produto automotivo baseada na EPA.

A base EPA descreve configurações de veículos leves comercializados nos Estados
Unidos. Ela suporta comparações técnicas de produto por marca, modelo, segmento,
propulsão, eficiência, emissões, autonomia e custo anual de energia. Não é uma
base de vendas por marca.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

EPA_DATA_URL = "https://www.fueleconomy.gov/feg/epadata/vehicles.csv"
EPA_DOWNLOAD_PAGE = "https://www.fueleconomy.gov/feg/download.shtml"

NUMERIC_COLUMNS = [
    "year",
    "city08",
    "highway08",
    "comb08",
    "combE",
    "co2TailpipeGpm",
    "fuelCost08",
    "youSaveSpend",
    "range",
    "rangeCity",
    "rangeHwy",
    "cylinders",
    "displ",
    "feScore",
    "ghgScore",
]
TEXT_COLUMNS = ["make", "model", "baseModel", "VClass", "fuelType1", "fuelType2", "trany", "drive", "atvType", "mfrCode"]


def _text_series(frame: pd.DataFrame, column: str) -> pd.Series:
    """Retorna uma série de texto limpa mesmo quando a coluna estiver ausente."""
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="string")
    return frame[column].fillna("").astype(str).str.strip()


def classify_powertrain(frame: pd.DataFrame) -> pd.Series:
    """Classifica a configuração em uma taxonomia de propulsão legível."""
    fuel = _text_series(frame, "fuelType1").str.lower()
    atv = _text_series(frame, "atvType").str.lower()
    range_miles = pd.to_numeric(frame.get("range", 0), errors="coerce").fillna(0)

    plug_in = atv.str.contains("plug-in|phev", regex=True) | fuel.str.contains("electricity", regex=False) & fuel.str.contains("gasoline", regex=False)
    battery_electric = (
        fuel.str.contains("electricity", regex=False)
        & ~fuel.str.contains("gasoline", regex=False)
        & ~fuel.str.contains("diesel", regex=False)
        & (range_miles > 0)
        & ~plug_in
    )
    hybrid = atv.str.contains("hybrid", regex=False) | fuel.str.contains("hybrid", regex=False)
    diesel = fuel.str.contains("diesel", regex=False)
    natural_gas = fuel.str.contains("natural gas|cng", regex=True)
    ethanol = fuel.str.contains("ethanol|e85", regex=True)
    hydrogen = fuel.str.contains("hydrogen", regex=False)

    return pd.Series(
        np.select(
            [battery_electric, plug_in, hybrid, hydrogen, diesel, natural_gas, ethanol],
            ["Elétrico a bateria", "Híbrido plug-in", "Híbrido", "Célula a combustível", "Diesel", "Gás natural", "Flex / Etanol"],
            default="Combustão",
        ),
        index=frame.index,
        dtype="string",
    )


def load_vehicle_data(source: str | Path) -> pd.DataFrame:
    """Lê e prepara a base oficial de veículos da EPA."""
    raw = pd.read_csv(source, low_memory=False)
    for column in NUMERIC_COLUMNS:
        if column in raw.columns:
            raw[column] = pd.to_numeric(raw[column], errors="coerce")
    for column in TEXT_COLUMNS:
        if column in raw.columns:
            raw[column] = _text_series(raw, column)

    data = raw.copy()
    data = data[data["year"].between(1984, 2030, inclusive="both")].copy()
    data = data[data["make"].ne("") & data["model"].ne("")].copy()
    data["powertrain"] = classify_powertrain(data)
    data["modelo_chave"] = data["make"] + " · " + data["model"]
    data["eficiencia_valida"] = data["comb08"].where(data["comb08"] > 0)
    data["co2_valido"] = data["co2TailpipeGpm"].where(data["co2TailpipeGpm"] >= 0)
    data["custo_anual_valido"] = data["fuelCost08"].where(data["fuelCost08"] > 0)
    data["autonomia_valida"] = data["range"].where(data["range"] > 0)
    data["eletrificado"] = data["powertrain"].isin(["Elétrico a bateria", "Híbrido plug-in", "Híbrido"])
    return data.reset_index(drop=True)


def filter_vehicles(
    data: pd.DataFrame,
    year_range: tuple[int, int] | list[int],
    makes: Iterable[str] | None = None,
    powertrains: Iterable[str] | None = None,
    segments: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Aplica filtros de explorador preservando o universo de configurações EPA."""
    start_year, end_year = int(year_range[0]), int(year_range[1])
    filtered = data[data["year"].between(start_year, end_year, inclusive="both")].copy()
    if makes:
        filtered = filtered[filtered["make"].isin(list(makes))]
    if powertrains:
        filtered = filtered[filtered["powertrain"].isin(list(powertrains))]
    if segments:
        filtered = filtered[filtered["VClass"].isin(list(segments))]
    return filtered


def portfolio_kpis(data: pd.DataFrame) -> dict[str, float | int]:
    """Consolida indicadores para o universo filtrado de configurações."""
    if data.empty:
        return {"configuracoes": 0, "marcas": 0, "modelos": 0, "mpg_medio": float("nan"), "co2_medio": float("nan"), "eletrificados_pct": float("nan")}
    return {
        "configuracoes": int(len(data)),
        "marcas": int(data["make"].nunique()),
        "modelos": int(data["modelo_chave"].nunique()),
        "mpg_medio": float(data["eficiencia_valida"].mean()),
        "co2_medio": float(data["co2_valido"].mean()),
        "eletrificados_pct": float(data["eletrificado"].mean() * 100),
    }


def brand_summary(data: pd.DataFrame, min_records: int = 1) -> pd.DataFrame:
    """Resume amplitude e eficiência de portfólio por fabricante."""
    if data.empty:
        return pd.DataFrame()
    summary = (
        data.groupby("make", as_index=False)
        .agg(
            configuracoes=("id", "count"),
            modelos=("modelo_chave", "nunique"),
            segmentos=("VClass", "nunique"),
            ano_inicial=("year", "min"),
            ano_final=("year", "max"),
            mpg_medio=("eficiencia_valida", "mean"),
            co2_medio_g_milha=("co2_valido", "mean"),
            custo_anual_medio_usd=("custo_anual_valido", "mean"),
            participacao_eletrificada_pct=("eletrificado", "mean"),
            autonomia_max_milhas=("autonomia_valida", "max"),
        )
        .assign(participacao_eletrificada_pct=lambda frame: frame["participacao_eletrificada_pct"] * 100)
    )
    summary = summary[summary["configuracoes"] >= min_records]
    return summary.sort_values(["configuracoes", "mpg_medio"], ascending=[False, False]).reset_index(drop=True)


def brand_registry(data: pd.DataFrame, recent_window_years: int = 3) -> pd.DataFrame:
    """Audita os nomes literais de marca publicados no campo ``make`` da EPA.

    O status é temporal e descritivo: informa apenas se existe observação no
    intervalo recente do próprio snapshot. Ele não infere atividade comercial,
    propriedade societária ou participação de mercado de uma marca.
    """
    if data.empty:
        return pd.DataFrame()
    latest_year = int(data["year"].max())
    recent_floor = latest_year - recent_window_years + 1
    registry = (
        data.groupby("make", as_index=False)
        .agg(
            configuracoes=("id", "count"),
            modelos=("modelo_chave", "nunique"),
            ano_inicial=("year", "min"),
            ano_final=("year", "max"),
        )
        .assign(
            presenca_no_snapshot=lambda frame: np.where(
                frame["ano_final"] >= recent_floor,
                f"Registro EPA em {recent_floor}–{latest_year}",
                f"Somente histórico até {{ano_final}}",
            )
        )
    )
    registry["presenca_no_snapshot"] = registry.apply(
        lambda row: row["presenca_no_snapshot"].format(ano_final=int(row["ano_final"])), axis=1
    )
    return registry.sort_values(["ano_final", "configuracoes", "make"], ascending=[False, False, True]).reset_index(drop=True)


def model_summary(data: pd.DataFrame, min_records: int = 1) -> pd.DataFrame:
    """Consolida o portfólio por marca e modelo sem misturar configurações."""
    if data.empty:
        return pd.DataFrame()
    summary = (
        data.groupby(["make", "model", "VClass", "powertrain"], as_index=False)
        .agg(
            configuracoes=("id", "count"),
            ano_inicial=("year", "min"),
            ano_final=("year", "max"),
            mpg_medio=("eficiencia_valida", "mean"),
            co2_medio_g_milha=("co2_valido", "mean"),
            custo_anual_medio_usd=("custo_anual_valido", "mean"),
            autonomia_max_milhas=("autonomia_valida", "max"),
            cilindros_medios=("cylinders", "mean"),
            motor_medio_litros=("displ", "mean"),
        )
    )
    summary = summary[summary["configuracoes"] >= min_records]
    return summary.sort_values(["mpg_medio", "configuracoes"], ascending=[False, False]).reset_index(drop=True)


def segment_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Resume diversidade e desempenho por classe de veículo EPA."""
    if data.empty:
        return pd.DataFrame()
    return (
        data.groupby("VClass", as_index=False)
        .agg(
            configuracoes=("id", "count"),
            marcas=("make", "nunique"),
            modelos=("modelo_chave", "nunique"),
            mpg_medio=("eficiencia_valida", "mean"),
            co2_medio_g_milha=("co2_valido", "mean"),
            custo_anual_medio_usd=("custo_anual_valido", "mean"),
        )
        .sort_values("configuracoes", ascending=False)
        .reset_index(drop=True)
    )


def powertrain_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Resume participação de configurações e atributos de propulsão."""
    if data.empty:
        return pd.DataFrame()
    total = len(data)
    return (
        data.groupby("powertrain", as_index=False)
        .agg(
            configuracoes=("id", "count"),
            marcas=("make", "nunique"),
            modelos=("modelo_chave", "nunique"),
            mpg_medio=("eficiencia_valida", "mean"),
            co2_medio_g_milha=("co2_valido", "mean"),
            autonomia_max_milhas=("autonomia_valida", "max"),
        )
        .assign(participacao_pct=lambda frame: frame["configuracoes"] / total * 100)
        .sort_values("configuracoes", ascending=False)
        .reset_index(drop=True)
    )


def annual_portfolio_trend(data: pd.DataFrame) -> pd.DataFrame:
    """Série anual de produto e eficiência por tipo de propulsão."""
    if data.empty:
        return pd.DataFrame()
    return (
        data.groupby(["year", "powertrain"], as_index=False)
        .agg(
            configuracoes=("id", "count"),
            marcas=("make", "nunique"),
            modelos=("modelo_chave", "nunique"),
            mpg_medio=("eficiencia_valida", "mean"),
            co2_medio_g_milha=("co2_valido", "mean"),
            eletrificados_pct=("eletrificado", "mean"),
        )
        .assign(eletrificados_pct=lambda frame: frame["eletrificados_pct"] * 100)
        .sort_values(["year", "powertrain"])
        .reset_index(drop=True)
    )


def vehicle_universe_metadata(data: pd.DataFrame) -> dict[str, int]:
    """Resume a escala temporal e a cobertura do snapshot."""
    return {
        "observacoes": int(len(data)),
        "marcas": int(data["make"].nunique()),
        "modelos": int(data["modelo_chave"].nunique()),
        "ano_inicial": int(data["year"].min()),
        "ano_final": int(data["year"].max()),
        "segmentos": int(data["VClass"].nunique()),
    }
