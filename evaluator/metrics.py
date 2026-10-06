"""Deterministic metric primitives with explicit empty-set semantics."""
from __future__ import annotations

from statistics import mean as _mean, median as _median
from typing import Iterable, Sequence


def safe_ratio(numerator: int | float, denominator: int | float, *, empty: float = 0.0) -> float:
    return float(numerator / denominator) if denominator else float(empty)


def precision(tp: int, fp: int) -> float:
    return safe_ratio(tp, tp + fp)


def recall(tp: int, fn: int) -> float:
    return safe_ratio(tp, tp + fn)


def f1(p: float, r: float) -> float:
    return safe_ratio(2 * p * r, p + r)


def mean(values: Iterable[float]) -> float | None:
    values = list(values)
    return float(_mean(values)) if values else None


def median(values: Iterable[float]) -> float | None:
    values = list(values)
    return float(_median(values)) if values else None


def success_rate(values: Iterable[bool]) -> float:
    values = list(values)
    return safe_ratio(sum(values), len(values))


def path_diversity(paths: Iterable[Sequence[str]]) -> int:
    return len({tuple(path) for path in paths})


def classification_metrics(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    p, r = precision(tp, fp), recall(tp, fn)
    return {"true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": p, "recall": r, "f1": f1(p, r)}
