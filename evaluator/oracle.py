"""Score external Oracle decisions; this module never decides a request."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .metrics import safe_ratio
from .validation import load_validated


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    paths = sorted(path.glob("O-*.yaml")) if path.is_dir() else [path]
    cases = [load_validated(item, "oracle_case") for item in paths]
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Oracle case_id")
    return cases


def request_digest(request: dict[str, Any]) -> str:
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def evaluate_oracle(cases: list[dict[str, Any]], observed: dict[str, Any]) -> dict[str, Any]:
    decisions = {row["case_id"]: row for row in observed["decisions"]}
    expected_ids = {case["case_id"] for case in cases}
    if set(decisions) != expected_ids:
        missing, extra = sorted(expected_ids - decisions.keys()), sorted(decisions.keys() - expected_ids)
        raise ValueError(f"Oracle decisions must exactly cover cases; missing={missing}, extra={extra}")
    rows = []
    for case in cases:
        decision = decisions[case["case_id"]]
        digest_ok = decision["request_digest"] == request_digest(case["request"])
        if not digest_ok:
            raise ValueError(f"decision {case['case_id']} request_digest mismatch")
        rows.append({"case_id": case["case_id"], "expected": case["expected"],
                     "actual": decision["actual"], "pass": case["expected"] == decision["actual"],
                     "reject_reason": decision.get("reject_reason"),
                     "latency_seconds": decision.get("latency_seconds")})
    valid = [row for row in rows if row["expected"] == "Allow"]
    invalid = [row for row in rows if row["expected"] == "Reject"]
    accepted_valid = sum(row["actual"] == "Allow" for row in valid)
    rejected_invalid = sum(row["actual"] == "Reject" for row in invalid)
    false_accept = len(invalid) - rejected_invalid
    false_reject = len(valid) - accepted_valid
    return {"synthetic_observations": observed.get("synthetic", False), "cases": rows,
            "metrics": {
                "valid_request_acceptance_rate": safe_ratio(accepted_valid, len(valid)),
                "invalid_request_rejection_rate": safe_ratio(rejected_invalid, len(invalid)),
                "false_acceptance_rate": safe_ratio(false_accept, len(invalid)),
                "false_rejection_rate": safe_ratio(false_reject, len(valid)),
                "bypass_success_rate": safe_ratio(false_accept, len(invalid)),
            }}


def evaluate_files(cases_path: str | Path, decisions_path: str | Path) -> dict[str, Any]:
    cases = load_cases(cases_path)
    observed = load_validated(decisions_path, "oracle_decisions")
    return evaluate_oracle(cases, observed)
