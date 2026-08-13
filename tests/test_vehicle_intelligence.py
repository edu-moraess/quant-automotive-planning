from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vehicle_intelligence import (  # noqa: E402
    brand_summary,
    classify_powertrain,
    filter_vehicles,
    load_vehicle_data,
    portfolio_kpis,
    powertrain_summary,
    vehicle_universe_metadata,
)


def test_classify_powertrain_recognizes_main_technologies():
    frame = pd.DataFrame(
        {
            "fuelType1": ["Electricity", "Premium Gasoline or Electricity", "Regular Gasoline", "Diesel", "Hydrogen"],
            "atvType": ["", "Plug-in Hybrid Electric Vehicle", "Hybrid Electric Vehicle", "", ""],
            "range": [300, 25, 0, 0, 0],
        }
    )
    assert list(classify_powertrain(frame)) == ["Elétrico a bateria", "Híbrido plug-in", "Híbrido", "Diesel", "Célula a combustível"]


def test_load_vehicle_snapshot_and_build_portfolio_metrics():
    root = Path(__file__).resolve().parents[1]
    data = load_vehicle_data(root / "data" / "EPA_vehicles_snapshot.csv")
    metadata = vehicle_universe_metadata(data)
    assert metadata["observacoes"] > 40_000
    assert metadata["marcas"] > 50
    assert metadata["ano_final"] >= 2026
    assert {"make", "model", "powertrain", "modelo_chave", "eficiencia_valida"}.issubset(data.columns)
    assert data["powertrain"].notna().all()


def test_filters_and_brand_summary_keep_real_records():
    root = Path(__file__).resolve().parents[1]
    data = load_vehicle_data(root / "data" / "EPA_vehicles_snapshot.csv")
    filtered = filter_vehicles(data, (2024, 2026), makes=["Tesla", "Toyota"])
    kpis = portfolio_kpis(filtered)
    summary = brand_summary(filtered)
    powertrains = powertrain_summary(filtered)
    assert set(filtered["make"].unique()).issubset({"Tesla", "Toyota"})
    assert kpis["configuracoes"] == len(filtered)
    assert not summary.empty
    assert not powertrains.empty
