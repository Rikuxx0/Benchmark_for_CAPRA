from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluator.oracle import evaluate_oracle, load_cases

ROOT = Path(__file__).resolve().parents[1]


def test_o01_through_o15_external_decisions():
    cases = load_cases(ROOT / "oracle_cases")
    observed = json.loads((ROOT / "oracle_cases/observed_decisions.json").read_text())
    result = evaluate_oracle(cases, observed)
    assert len(result["cases"]) == 15
    assert all(row["pass"] for row in result["cases"])
    assert result["metrics"] == {
        "valid_request_acceptance_rate": 1.0,
        "invalid_request_rejection_rate": 1.0,
        "false_acceptance_rate": 0.0,
        "false_rejection_rate": 0.0,
        "bypass_success_rate": 0.0,
    }
    assert result["synthetic_observations"] is True


def test_correct_operator_with_bad_concrete_plan_is_rejected():
    cases = load_cases(ROOT / "oracle_cases")
    relevant = {case["case_id"]: case for case in cases}
    for case_id in ("O-11", "O-12", "O-13", "O-14"):
        assert relevant[case_id]["high_level_operator_correct"] is True
        assert relevant[case_id]["expected"] == "Reject"


def test_decision_must_bind_exact_request(copied):
    cases = load_cases(ROOT / "oracle_cases")
    observed = json.loads((ROOT / "oracle_cases/observed_decisions.json").read_text())
    observed = copied(observed)
    observed["decisions"][0]["request_digest"] = "tampered"
    with pytest.raises(ValueError, match="request_digest"):
        evaluate_oracle(cases, observed)


def test_false_acceptance_and_false_rejection_metrics(copied):
    cases = load_cases(ROOT / "oracle_cases")
    observed = copied(json.loads((ROOT / "oracle_cases/observed_decisions.json").read_text()))
    observed["decisions"][0]["actual"] = "Reject"
    observed["decisions"][1]["actual"] = "Allow"
    result = evaluate_oracle(cases, observed)
    assert result["metrics"]["false_rejection_rate"] == 1.0
    assert result["metrics"]["false_acceptance_rate"] == pytest.approx(1 / 14)
    assert result["metrics"]["bypass_success_rate"] == pytest.approx(1 / 14)
