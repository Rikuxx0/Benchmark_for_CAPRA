"""Aggregate externally produced RedAgent run results."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .metrics import mean, median, path_diversity, success_rate
from .validation import load_validated


def _status_failures(run: dict[str, Any]) -> int:
    if "failed_executions" in run:
        return int(run["failed_executions"])
    return sum(item.get("status") in {"failure", "error"} for item in run["execution_results"])


def _invalid_actions(run: dict[str, Any]) -> int:
    if "invalid_actions" in run:
        return int(run["invalid_actions"])
    return sum(event.get("invalid_action") is True for event in run["execution_trace"])


def _canonical_operator(run: dict[str, Any], selected: str) -> str:
    return run.get("operator_bindings", {}).get(selected, selected)


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successful_steps = [row["steps_to_goal"] for row in rows if row["goal_reached"]]
    return {
        "goal_success_rate": success_rate(row["goal_reached"] for row in rows),
        "steps_to_goal": {"values": successful_steps, "mean": mean(successful_steps),
                          "median": median(successful_steps)},
        "failed_execution_count": sum(row["failed_execution_count"] for row in rows),
        "invalid_action_count": sum(row["invalid_action_count"] for row in rows),
        "non_goal_action_count": sum(row["non_goal_action_count"] for row in rows),
        "path_diversity": path_diversity(row["path"] for row in rows),
        "execution_time_seconds": {"total": sum(row["execution_time_seconds"] for row in rows),
                                   "mean": mean(row["execution_time_seconds"] for row in rows)},
    }


def evaluate_runs(runs: Iterable[dict[str, Any]], ground_truth: dict[str, Any]) -> dict[str, Any]:
    runs = sorted(list(runs), key=lambda item: item["run_id"])
    if not runs:
        raise ValueError("at least one run is required")
    scenario_ids = {run["scenario_id"] for run in runs}
    if scenario_ids != {ground_truth["scenario_id"]}:
        raise ValueError("all runs must use the Ground Truth scenario_id")
    if {run["scenario_version"] for run in runs} != {ground_truth["scenario_version"]}:
        raise ValueError("all runs must use the Ground Truth scenario_version")
    if len({run["initial_state_digest"] for run in runs}) != 1:
        raise ValueError("runs from different initial states cannot be aggregated")
    nong_goal = {op["operator_id"] for op in ground_truth["operators"] if op["goal_contribution"] == "none"}
    per_run = []
    for run in runs:
        non_goal_count = sum(_canonical_operator(run, op) in nong_goal for op in run["selected_operator_ids"])
        per_run.append({
            "run_id": run["run_id"], "evaluation_mode": run["evaluation_mode"],
            "goal_reached": run["goal_reached"], "steps_to_goal": run["steps_to_goal"],
            "failed_execution_count": _status_failures(run),
            "invalid_action_count": _invalid_actions(run),
            "non_goal_action_count": non_goal_count,
            "execution_time_seconds": run["execution_time_seconds"],
            "path": run["selected_operator_ids"],
        })
    modes = sorted({row["evaluation_mode"] for row in per_run})
    return {
        "scenario_id": ground_truth["scenario_id"], "run_count": len(runs), "runs": per_run,
        "initial_state_digest": runs[0]["initial_state_digest"],
        "metrics": _metrics(per_run),
        "by_mode": {mode: _metrics([row for row in per_run if row["evaluation_mode"] == mode])
                    for mode in modes},
    }


def load_runs(path: str | Path) -> list[dict[str, Any]]:
    path = Path(path)
    paths = sorted(path.glob("*.json")) if path.is_dir() else [path]
    return [load_validated(item, "benchmark_result") for item in paths]


def evaluate_files(scenario_dir: str | Path, result_path: str | Path) -> dict[str, Any]:
    from .validation import load_scenario
    _, truth = load_scenario(scenario_dir)
    return evaluate_runs(load_runs(result_path), truth)
