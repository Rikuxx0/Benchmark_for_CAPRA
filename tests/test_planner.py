from __future__ import annotations

from evaluator.planner import evaluate_planner


def test_perfect_operator_connection_dependency_path_and_unresolved(truth, graph):
    result = evaluate_planner(truth, graph)
    assert set(result["matched_operators"]) == {"op-a", "op-b", "op-c", "op-e", "op-f"}
    assert result["metrics"]["operator"]["precision"] == 1.0
    assert result["metrics"]["connection"]["f1"] == 1.0
    assert ["op-a", "op-b", "enables"] in result["matched_connections"]
    assert ["op-c", "op-f", "enables"] in result["matched_connections"]
    assert result["metrics"]["goal_path_recall"] == 1.0
    assert result["unresolved_operators"]["matched"] == ["op-d"]


def test_missing_operator(copied, truth, graph):
    graph = copied(graph)
    graph["attack_operators"] = [op for op in graph["attack_operators"] if op["id"] != "op-a"]
    result = evaluate_planner(truth, graph)
    assert result["missing_operators"] == ["op-a"]
    assert result["metrics"]["operator"]["recall"] == 0.8


def test_extra_and_negative_operator(copied, truth, graph):
    graph = copied(graph)
    extra = copied(graph["attack_operators"][0])
    extra.update(id="unknown", target_node="k8s:secret:application:unknown")
    graph["attack_operators"].append(extra)
    result = evaluate_planner(truth, graph)
    assert result["false_operators"] == ["unknown"]
    assert result["metrics"]["false_operator_count"] == 1


def test_ambiguous_diagnostic_match_fails_closed(copied, truth, graph):
    graph = copied(graph)
    op = graph["attack_operators"][0]
    op["id"] = "capra-a-1"
    duplicate = copied(op)
    duplicate["id"] = "capra-a-2"
    graph["attack_operators"].append(duplicate)
    result = evaluate_planner(truth, graph)
    assert "op-a" in result["missing_operators"]
    assert result["ambiguous_operator_matches"][0]["candidate_ids"] == ["capra-a-1", "capra-a-2"]


def test_missing_connection(copied, truth, graph):
    graph = copied(graph)
    graph["connections"].pop(0)
    result = evaluate_planner(truth, graph)
    assert ["op-a", "op-b", "enables"] in result["missing_connections"]
    assert result["metrics"]["goal_path_recall"] == 0.0


def test_false_and_explicit_expected_false_connection(copied, truth, graph):
    graph = copied(graph)
    graph["connections"].append({"source_operator_id": "op-e", "target_operator_id": "op-b",
                                 "connection_type": "enables"})
    result = evaluate_planner(truth, graph)
    assert result["metrics"]["false_connection_count"] == 1
    assert result["false_connections"][0]["source_operator"] == "op-e"


def test_unresolved_missing(copied, truth, graph):
    graph = copied(graph)
    graph["unresolved_items"] = []
    assert evaluate_planner(truth, graph)["unresolved_operators"]["missing"] == ["op-d"]


def test_zero_denominator_planner():
    truth = {"operators": [], "connections": [], "expected_goal_paths": [], "operator_type_aliases": {}}
    graph = {"attack_operators": [], "connections": [], "unresolved_items": []}
    result = evaluate_planner(truth, graph)
    assert result["metrics"]["operator"]["precision"] == 0.0
    assert result["metrics"]["connection"]["recall"] == 0.0
    assert result["metrics"]["goal_path_recall"] == 0.0
