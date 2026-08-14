import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from energy_intelligence import add_energy_cost_estimate, energy_summary, load_energy_prices  # noqa: E402
from vehicle_intelligence import filter_vehicles, load_vehicle_data  # noqa: E402


def main() -> None:
    vehicles = load_vehicle_data(ROOT / "data" / "EPA_vehicles_snapshot.csv")
    prices = load_energy_prices(ROOT / "data" / "energy_price_snapshot.csv")
    enriched = add_energy_cost_estimate(vehicles, prices)
    recent = filter_vehicles(enriched, (2025, 2027), [], [], [])
    print(energy_summary(recent).to_string(index=False))
    for source in ["Gasolina", "Diesel", "Eletricidade"]:
        subset = recent[recent["fonte_energia"].eq(source)]
        print(f"\n--- {source} | {len(subset)} registros")
        print(
            subset[["make", "model", "year", "fuelType1", "powertrain", "comb08", "combE", "custo_energia_100mi_usd"]]
            .sort_values("custo_energia_100mi_usd")
            .head(8)
            .to_string(index=False)
        )
        print("medianas:", subset[["comb08", "combE", "custo_energia_100mi_usd"]].median(numeric_only=True).to_dict())


if __name__ == "__main__":
    main()
