import pandas as pd
import pytest

from data_quality import profile_time_series, profile_vehicle_catalog
from energy_intelligence import load_energy_prices
from ingestion import SourceUnavailable, load_csv_with_fallback
from vehicle_intelligence import load_vehicle_data


def test_fallback_loads_snapshot_when_online_source_fails(tmp_path, monkeypatch):
    snapshot = tmp_path / "market.csv"
    pd.DataFrame({"observation_date": ["2024-01-01"], "TOTALSA": [15.0]}).to_csv(snapshot, index=False)

    def unavailable(*args, **kwargs):
        raise SourceUnavailable("offline")

    monkeypatch.setattr("ingestion.fetch_csv", unavailable)
    result = load_csv_with_fallback(
        url="https://example.invalid/data.csv",
        expected_columns=["observation_date", "TOTALSA"],
        source_name="market",
        snapshot_path=snapshot,
        allow_online=True,
    )
    assert result.source_status == "SNAPSHOT"
    assert result.frame.iloc[0]["TOTALSA"] == 15.0
    assert "offline" in result.fallback_reason


def test_time_series_profile_reports_frequency_and_missingness(tmp_path):
    snapshot = tmp_path / "series.csv"
    frame = pd.DataFrame({"data": ["2024-01-01", "2024-03-01", "2024-04-01"], "value": [1.0, None, 3.0]})
    frame.to_csv(snapshot, index=False)
    health = profile_time_series(frame, "test", "data", ["value"], "SNAPSHOT", snapshot, "test")
    assert health.frequency_gaps == 1
    assert health.missing_rate_pct > 0
    assert health.snapshot_sha256 is not None


def test_energy_loader_rejects_duplicate_dates(tmp_path):
    source = tmp_path / "energy.csv"
    pd.DataFrame(
        {
            "data": ["2024-01-01", "2024-01-01"],
            "gasolina_usd_gal": [3.0, 3.1],
            "diesel_usd_gal": [4.0, 4.1],
            "eletricidade_usd_kwh": [0.2, 0.2],
        }
    ).to_csv(source, index=False)
    with pytest.raises(ValueError, match="duplicadas"):
        load_energy_prices(source)


def test_vehicle_loader_rejects_duplicate_ids(tmp_path):
    source = tmp_path / "vehicles.csv"
    pd.DataFrame(
        {
            "id": [1, 1],
            "year": [2024, 2024],
            "make": ["A", "A"],
            "model": ["B", "B"],
            "VClass": ["Cars", "Cars"],
            "fuelType1": ["Regular Gasoline", "Regular Gasoline"],
            "comb08": [30, 30],
            "co2TailpipeGpm": [300, 300],
            "fuelCost08": [2000, 2000],
        }
    ).to_csv(source, index=False)
    with pytest.raises(ValueError, match="IDs duplicados"):
        load_vehicle_data(source)


def test_vehicle_profile_marks_invalid_records(tmp_path):
    source = tmp_path / "vehicles.csv"
    frame = pd.DataFrame(
        {
            "id": [1, 2],
            "year": [2024, 1970],
            "make": ["A", ""],
            "model": ["B", ""],
            "comb08": [30, 0],
        }
    )
    frame.to_csv(source, index=False)
    health = profile_vehicle_catalog(frame, "SNAPSHOT", source)
    assert health.invalid_rows == 1
    assert health.rows == 2
