from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis import run_full_analysis  # noqa: E402


def test_full_pipeline_runs_from_versioned_snapshot():
    root = Path(__file__).resolve().parents[1]
    result = run_full_analysis(
        fallback_path=root / "data" / "TOTALSA_snapshot.csv",
        n_folds=4,
        test_size=6,
        horizon=6,
        bootstrap_replicas=200,
        seed=42,
        participation=0.08,
        capacity=110_000,
        initial_inventory=15_000,
        production_cost=25_000,
        inventory_cost=350,
        backlog_cost=45_000,
        source_url="file-that-does-not-exist.csv",
    )
    assert result["source_label"] == "Snapshot local versionado"
    assert len(result["forecast"]) == 6
    assert result["backtest"]["winner"] in {"Referência sazonal", "Holt-Winters", "Regressão com defasagens"}
    assert set(result["production"]["scenarios"]["Cenário"]) == {"Conservador", "Base", "Otimista"}
    assert (result["production"]["plan"]["producao_recomendada"] <= 110_000).all()
