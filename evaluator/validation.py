"""Strict JSON/YAML loading with useful JSON Schema errors."""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


class InputValidationError(ValueError):
    def __init__(self, path: Path, field_path: str, reason: str):
        self.file = str(path)
        self.field_path = field_path or "$"
        self.reason = reason
        super().__init__(f"{self.file}: {self.field_path}: {self.reason}")


def read_document(path: str | Path) -> Any:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise InputValidationError(path, "$", f"cannot parse document: {exc}") from exc


def schema(name: str) -> dict[str, Any]:
    return json.loads(files("schemas").joinpath(f"{name}.schema.json").read_text(encoding="utf-8"))


def validate_document(document: Any, schema_name: str, path: str | Path = "<memory>") -> Any:
    errors = sorted(
        Draft202012Validator(schema(schema_name), format_checker=FormatChecker()).iter_errors(document),
        # Prefer the most specific field error over a root-level missing-field
        # error when both are present in the same invalid document.
        key=lambda e: (-len(e.absolute_path), [str(part) for part in e.absolute_path]),
    )
    if errors:
        error = errors[0]
        field = "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
        raise InputValidationError(Path(path), field, error.message)
    return document


def load_validated(path: str | Path, schema_name: str) -> Any:
    return validate_document(read_document(path), schema_name, path)


def load_scenario(directory: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    directory = Path(directory)
    scenario = load_validated(directory / "scenario.yaml", "scenario")
    truth = load_validated(directory / "ground_truth.yaml", "ground_truth")
    if scenario["scenario_id"] != truth["scenario_id"]:
        raise InputValidationError(directory / "ground_truth.yaml", "$.scenario_id", "does not match scenario.yaml")
    if scenario["scenario_version"] != truth["scenario_version"]:
        raise InputValidationError(directory / "ground_truth.yaml", "$.scenario_version", "does not match scenario.yaml")
    return scenario, truth
