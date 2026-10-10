#!/usr/bin/env python3
"""Reject incomplete reports from the template's required test quality gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def require_mapping(value: Any, location: str) -> dict[str, Any]:
    """Require an object before inspecting its report fields."""
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    return value


def require_count(value: Any, location: str, *, positive: bool = False) -> None:
    """Reject noninteger counts, including booleans, at the requested boundary."""
    if type(value) is not int or (value <= 0 if positive else value != 0):
        expected = "a positive integer" if positive else "the integer zero"
        raise ValueError(f"{location} must be {expected}")


def validate_report(report: Any) -> None:
    """Require strict checks, available linters, and evidence from every layer."""
    report = require_mapping(report, "report")
    summary = require_mapping(report.get("summary"), "summary")
    for field, expected in (("status", "passed"), ("semantic_rules", "strict")):
        if summary.get(field) != expected:
            raise ValueError(f"summary.{field} must be {expected}")
    for field in ("errors", "infra_errors"):
        require_count(summary.get(field), f"summary.{field}")

    lint = require_mapping(summary.get("external_lint"), "summary.external_lint")
    if lint.get("mode") != "run":
        raise ValueError("summary.external_lint.mode must be run")
    results = lint.get("results")
    if not isinstance(results, list) or len(results) != 2:
        raise ValueError("external lint results must contain exactly Ruff and ESLint")
    sources = set()
    for index, result in enumerate(results):
        result = require_mapping(result, f"external lint result {index}")
        source = result.get("source")
        if not isinstance(source, str) or source not in {"ruff", "eslint"} or source in sources:
            raise ValueError("external lint sources must be unique Ruff and ESLint entries")
        if result.get("status") != "ok":
            raise ValueError(f"external lint {source} status must be ok")
        sources.add(source)

    frontend = require_mapping(report.get("frontend"), "frontend")
    layers = (
        ("backend", report.get("backend")),
        ("frontend.unit", frontend.get("unit")),
        ("frontend.e2e", frontend.get("e2e")),
    )
    for location, layer in layers:
        layer = require_mapping(layer, location)
        for field in ("files", "tests"):
            require_count(layer.get(field), f"{location}.{field}", positive=True)


def main(argv: list[str] | None = None) -> int:
    """Read one report and return a failing exit code for incomplete evidence."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("Usage: validate_test_quality_report.py <report.json>", file=sys.stderr)
        return 1
    try:
        report = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))
        validate_report(report)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Test quality report rejected: {exc}", file=sys.stderr)
        return 1
    print("Test quality report accepted: strict checks and both linters completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
