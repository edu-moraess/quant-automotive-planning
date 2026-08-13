import json
from pathlib import Path

import pandas as pd


def test_advanced_model_artifacts_are_real_and_temporal():
    root = Path(__file__).resolve().parents[1]
    results_dir = root / "data" / "advanced_models"
    summary = json.loads((results_dir / "advanced_model_summary.json").read_text(encoding="utf-8"))
    econometric = summary["econometria_energia"]
    neural = summary["rede_neural_eficiencia"]
    assert econometric["observacoes"] == 24
    assert econometric["inicio_treino"] < econometric["inicio_teste"]
    assert neural["observacoes"] == 2819
    assert neural["inicio_treino"] == 1984
    assert neural["fim_treino"] == 2024
    assert neural["inicio_teste"] == 2025
    assert neural["r2"] > 0.9


def test_advanced_validation_files_have_expected_fields():
    root = Path(__file__).resolve().parents[1]
    results_dir = root / "data" / "advanced_models"
    coefficients = pd.read_csv(results_dir / "econometric_coefficients.csv")
    validation = pd.read_csv(results_dir / "neural_efficiency_validation.csv")
    assert {"variavel", "coeficiente_padronizado", "p_valor"}.issubset(coefficients.columns)
    assert {"id", "make", "model", "year", "comb08", "previsto_mlp", "erro_abs"}.issubset(validation.columns)
    assert len(validation) == 2819
