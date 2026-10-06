from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluator.oracle import load_cases
from evaluator.validation import InputValidationError, load_scenario, load_validated, validate_document

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios/simple/simple-01"


def test_valid_scenario_and_ground_truth():
    scenario, truth = load_scenario(SCENARIO)
    assert scenario["scenario_id"] == truth["scenario_id"] == "simple-01"


@pytest.mark.parametrize(("schema", "value", "path"), [
    ("scenario", {"scenario_id": "BAD ID"}, "$.scenario_id"),
    ("ground_truth", {"scenario_id": "simple-01"}, "$"),
    ("oracle_case", {"case_id": "O-99", "expected": "Maybe"}, "$"),
])
def test_invalid_documents_report_file_field_and_reason(schema, value, path):
    with pytest.raises(InputValidationError) as caught:
        validate_document(value, schema, "bad.yaml")
    assert caught.value.file.endswith("bad.yaml")
    assert caught.value.field_path.startswith(path)
    assert caught.value.reason


def test_all_oracle_cases_are_valid_and_complete():
    cases = load_cases(ROOT / "oracle_cases")
    assert [case["case_id"] for case in cases] == [f"O-{index:02d}" for index in range(1, 16)]


def test_benchmark_result_and_graph_fixtures_are_valid():
    load_validated(ROOT / "tests/fixtures/planner/perfect_graph.json", "attack_operator_graph")
    for path in (ROOT / "tests/fixtures/redagent").glob("*.json"):
        load_validated(path, "benchmark_result")


def test_invalid_yaml_is_not_silently_ignored(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("key: [", encoding="utf-8")
    with pytest.raises(InputValidationError, match="cannot parse"):
        load_validated(bad, "scenario")
