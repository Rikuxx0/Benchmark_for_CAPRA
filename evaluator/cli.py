"""Command-line interface for black-box evaluation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .oracle import evaluate_files as evaluate_oracle
from .output import write_csv, write_json
from .planner import evaluate_files as evaluate_planner
from .redagent import evaluate_files as evaluate_redagent, evaluate_runs
from .validation import InputValidationError, load_scenario, load_validated


def _scenario(value: str) -> Path:
    path = Path(value)
    if not path.is_dir():
        raise argparse.ArgumentTypeError("scenario must be a directory")
    return path


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output-json", type=Path)
    common.add_argument("--output-csv", type=Path)

    item = commands.add_parser("planner", parents=[common])
    item.add_argument("--scenario", required=True, type=_scenario)
    item.add_argument("--capra-output", required=True, type=Path)

    item = commands.add_parser("redagent", parents=[common])
    item.add_argument("--scenario", required=True, type=_scenario)
    item.add_argument("--result", required=True, type=Path)

    item = commands.add_parser("oracle", parents=[common])
    item.add_argument("--cases", required=True, type=Path)
    item.add_argument("--decisions", type=Path,
                      help="Oracle response file; defaults to cases/observed_decisions.json")

    item = commands.add_parser("aggregate", parents=[common])
    item.add_argument("--results", required=True, type=Path)
    item.add_argument("--scenario", type=_scenario,
                      help="Ground Truth; defaults to scenarios/simple/<scenario_id>")

    item = commands.add_parser("validate")
    item.add_argument("--scenario", type=_scenario)
    item.add_argument("--oracle-cases", type=Path)
    return root


def _emit(result, args):
    if getattr(args, "output_json", None):
        write_json(args.output_json, result)
    if getattr(args, "output_csv", None):
        rows = result.get("runs") or result.get("cases") or [result]
        write_csv(args.output_csv, rows if isinstance(rows, list) else [rows])
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "planner":
            result = evaluate_planner(args.scenario, args.capra_output)
        elif args.command == "redagent":
            result = evaluate_redagent(args.scenario, args.result)
        elif args.command == "oracle":
            decisions = args.decisions or args.cases / "observed_decisions.json"
            result = evaluate_oracle(args.cases, decisions)
        elif args.command == "aggregate":
            paths = sorted(args.results.rglob("run-*.json"))
            if not paths:
                raise ValueError("no run-*.json results found")
            runs = [load_validated(path, "benchmark_result") for path in paths]
            scenario_ids = {run["scenario_id"] for run in runs}
            if len(scenario_ids) != 1:
                raise ValueError("aggregate accepts one scenario_id at a time")
            scenario_dir = args.scenario or Path("scenarios/simple") / next(iter(scenario_ids))
            _, truth = load_scenario(scenario_dir)
            result = evaluate_runs(runs, truth)
        else:
            validated = {}
            if args.scenario:
                scenario, truth = load_scenario(args.scenario)
                validated.update(scenario_id=scenario["scenario_id"], ground_truth_operators=len(truth["operators"]))
            if args.oracle_cases:
                from .oracle import load_cases
                validated["oracle_cases"] = len(load_cases(args.oracle_cases))
            if not validated:
                raise ValueError("provide --scenario and/or --oracle-cases")
            result = {"valid": True, **validated}
        _emit(result, args)
        return 0
    except (InputValidationError, ValueError, OSError) as exc:
        print(f"benchmark error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
