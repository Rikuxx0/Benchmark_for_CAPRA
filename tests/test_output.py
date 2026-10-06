import csv
import json

from evaluator.output import write_csv, write_json


def test_json_and_csv_outputs(tmp_path):
    result = {"run_id": "run-001", "metrics": {"success": 1.0}, "path": ["op-a", "op-b"]}
    json_path, csv_path = tmp_path / "result.json", tmp_path / "summary.csv"
    write_json(json_path, result)
    write_csv(csv_path, [result])
    assert json.loads(json_path.read_text()) == result
    with csv_path.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["run_id"] == "run-001"
    assert row["metrics.success"] == "1.0"
