from __future__ import annotations

from evaluator.redagent import evaluate_runs


def test_goal_success_failure_multiple_runs_and_diversity(truth, runs):
    result = evaluate_runs(runs, truth)
    assert result["run_count"] == 4
    assert result["metrics"]["goal_success_rate"] == 0.75
    assert result["metrics"]["steps_to_goal"]["values"] == [3, 2, 2]
    assert result["metrics"]["path_diversity"] == 3
    assert result["metrics"]["invalid_action_count"] == 1
    assert result["metrics"]["non_goal_action_count"] == 1
    assert result["by_mode"]["graph_llm"]["goal_success_rate"] == 1.0
    assert result["initial_state_digest"] == "sha256:fixture-initial-state"


def test_failed_execution_is_derived_from_external_result(copied, truth, runs):
    run = copied(runs[2])
    run["execution_results"][0]["status"] = "failure"
    assert evaluate_runs([run], truth)["metrics"]["failed_execution_count"] == 1


def test_explicit_invalid_count_is_respected(copied, truth, runs):
    run = copied(runs[0])
    run["invalid_actions"] = 4
    assert evaluate_runs([run], truth)["metrics"]["invalid_action_count"] == 4


def test_scenario_mismatch_rejected(copied, truth, runs):
    import pytest
    run = copied(runs[0])
    run["scenario_id"] = "other"
    with pytest.raises(ValueError, match="scenario_id"):
        evaluate_runs([run], truth)


def test_mixed_initial_states_are_rejected(copied, truth, runs):
    import pytest
    runs = copied(runs[:2])
    runs[1]["initial_state_digest"] = "sha256:different"
    with pytest.raises(ValueError, match="initial states"):
        evaluate_runs(runs, truth)
