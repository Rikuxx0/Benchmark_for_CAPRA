from evaluator.metrics import classification_metrics, f1, mean, median, path_diversity, precision, recall


def test_zero_denominators_are_explicit_zero():
    assert precision(0, 0) == recall(0, 0) == f1(0, 0) == 0.0
    assert classification_metrics(0, 0, 0)["f1"] == 0.0


def test_common_statistics():
    assert mean([1, 2, 3]) == median([1, 2, 3]) == 2.0
    assert mean([]) is median([]) is None
    assert path_diversity([["a", "b"], ["a", "b"], ["b", "a"]]) == 2
