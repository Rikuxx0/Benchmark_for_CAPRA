from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios/simple/simple-01"


@pytest.fixture
def truth():
    return yaml.safe_load((SCENARIO / "ground_truth.yaml").read_text())


@pytest.fixture
def graph():
    return json.loads((ROOT / "tests/fixtures/planner/perfect_graph.json").read_text())


@pytest.fixture
def runs():
    return [json.loads(path.read_text()) for path in sorted((ROOT / "tests/fixtures/redagent").glob("run-*.json"))]


@pytest.fixture
def copied():
    return copy.deepcopy
