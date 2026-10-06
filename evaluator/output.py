"""Stable JSON/CSV result writers."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def write_json(path: str | Path, result: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _flatten(value: Any, prefix="") -> dict[str, Any]:
    flat = {}
    if isinstance(value, dict):
        for key in sorted(value):
            flat.update(_flatten(value[key], f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        flat[prefix] = json.dumps(value, sort_keys=True, ensure_ascii=False)
    else:
        flat[prefix] = value
    return flat


def write_csv(path: str | Path, results: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [_flatten(result) for result in results]
    fields = sorted({field for row in rows for field in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
