"""Compare a CAPRA JSON export with independent Ground Truth."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .metrics import classification_metrics, safe_ratio
from .validation import load_validated


def _node_id(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return value.get("id") if isinstance(value, dict) else None


def _signature(operator: dict[str, Any], aliases: dict[str, str]) -> tuple[str | None, str | None, str | None]:
    kind = aliases.get(operator.get("operator_type"), operator.get("operator_type"))
    return kind, _node_id(operator.get("source_node")), _node_id(operator.get("target_node"))


def _identifier(operator: dict[str, Any]) -> str | None:
    return operator.get("id") or operator.get("operator_id")


def _match_operators(truth_ops, observed_ops, aliases):
    matched, missing, ambiguous = {}, [], []
    available = {_identifier(op): op for op in observed_ops if _identifier(op)}
    claimed: set[str] = set()
    for expected in truth_ops:
        gt_id = expected["operator_id"]
        stable = expected.get("stable_operator_id") or gt_id
        exact = available.get(stable)
        if exact is not None and stable not in claimed:
            matched[gt_id], claimed = stable, claimed | {stable}
            continue
        candidates = [op for op in observed_ops if _identifier(op) not in claimed and
                      _signature(op, aliases) == _signature(expected, aliases)]
        if len(candidates) == 1:
            obs_id = _identifier(candidates[0])
            matched[gt_id], claimed = obs_id, claimed | {obs_id}
        elif len(candidates) > 1:
            ambiguous.append({"operator_id": gt_id, "candidate_ids": sorted(_identifier(x) for x in candidates)})
            missing.append(gt_id)
        else:
            missing.append(gt_id)
    false = sorted(op_id for op_id in available if op_id not in claimed)
    return matched, sorted(missing), false, ambiguous


def evaluate_planner(ground_truth: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    aliases = ground_truth.get("operator_type_aliases", {})
    generated = [op for op in ground_truth["operators"] if op["planner_expectation"] == "generated"]
    matched, missing, false, ambiguous = _match_operators(generated, graph["attack_operators"], aliases)

    # Operators explicitly expected absent also make an observed operator false.
    absent = [op for op in ground_truth["operators"] if op["planner_expectation"] == "absent"]
    for expected in absent:
        for observed in graph["attack_operators"]:
            if _signature(expected, aliases) == _signature(observed, aliases):
                false.append(_identifier(observed))
    false = sorted(set(false))

    reverse = {observed: expected for expected, observed in matched.items()}
    positives = {(c["source_operator"], c["target_operator"], c["type"])
                 for c in ground_truth["connections"] if c["expected"]}
    negatives = {(c["source_operator"], c["target_operator"], c["type"])
                 for c in ground_truth["connections"] if not c["expected"]}
    actual = []
    raw_false = []
    for connection in graph["connections"]:
        src = connection.get("source_operator_id") or connection.get("source_operator")
        dst = connection.get("target_operator_id") or connection.get("target_operator")
        typ = connection.get("connection_type") or connection.get("type")
        canonical = (reverse.get(src), reverse.get(dst), typ)
        actual.append(canonical)
        if canonical not in positives or canonical in negatives:
            raw_false.append({"source_operator": src, "target_operator": dst, "type": typ})
    actual_set = set(actual)
    matched_connections = sorted(positives & actual_set)
    missing_connections = sorted(positives - actual_set)

    expected_paths = ground_truth["expected_goal_paths"]
    reproduced = []
    for path in expected_paths:
        operators_present = all(op in matched for op in path)
        edges_present = all(any(s == a and t == b for s, t, _ in positives & actual_set)
                            for a, b in zip(path, path[1:]))
        if operators_present and edges_present:
            reproduced.append(path)

    unresolved_expected = [op for op in ground_truth["operators"] if op["planner_expectation"] == "unresolved"]
    unresolved_matches, unresolved_missing, _, unresolved_ambiguous = _match_operators(
        unresolved_expected, graph.get("unresolved_items", []), aliases)

    operator_metrics = classification_metrics(len(matched), len(false), len(missing))
    connection_metrics = classification_metrics(len(matched_connections), len(raw_false), len(missing_connections))
    return {
        "matched_operators": dict(sorted(matched.items())), "missing_operators": missing,
        "false_operators": false, "ambiguous_operator_matches": ambiguous,
        "matched_connections": [list(x) for x in matched_connections],
        "missing_connections": [list(x) for x in missing_connections],
        "false_connections": raw_false,
        "goal_paths": {"expected": expected_paths, "reproduced": reproduced},
        "unresolved_operators": {"matched": sorted(unresolved_matches), "missing": unresolved_missing,
                                 "ambiguous": unresolved_ambiguous},
        "metrics": {"operator": operator_metrics, "connection": connection_metrics,
                    "goal_path_recall": safe_ratio(len(reproduced), len(expected_paths)),
                    "false_operator_count": len(false), "false_connection_count": len(raw_false)},
    }


def evaluate_files(scenario_dir: str | Path, graph_path: str | Path) -> dict[str, Any]:
    from .validation import load_scenario
    _, truth = load_scenario(scenario_dir)
    graph = load_validated(graph_path, "attack_operator_graph")
    return evaluate_planner(truth, graph)
