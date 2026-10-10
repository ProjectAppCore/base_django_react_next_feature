"""Exercise the report validator through its real command-line interface."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

VALIDATOR = Path(__file__).resolve().parents[4] / "scripts" / "validate_test_quality_report.py"


@pytest.fixture
def report():
    """Provide complete evidence in the quality gate's actual report layout."""
    return {
        "summary": {
            "status": "passed", "errors": 0, "infra_errors": 0,
            "semantic_rules": "strict",
            "external_lint": {
                "mode": "run",
                "results": [
                    {"source": "ruff", "status": "ok", "message": None, "findings": 0},
                    {"source": "eslint", "status": "ok", "message": None, "findings": 0},
                ],
            },
        },
        "backend": {"files": 25, "tests": 225},
        "frontend": {"unit": {"files": 29, "tests": 197}, "e2e": {"files": 9, "tests": 59}},
    }


def run_validator(path):
    """Invoke the executable CLI without substituting its validation internals."""
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)], capture_output=True, text=True, check=False,
    )


def write_report(tmp_path, report):
    """Serialize evidence into an isolated report file."""
    path = tmp_path / "gate.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def test_cli_accepts_complete_strict_report(tmp_path, report):
    """Complete strict checks with both linters produce an accepted exit status."""
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 0
    assert "Test quality report accepted" in result.stdout


def test_cli_rejects_missing_report(tmp_path):
    """A nonexistent report cannot certify a successful quality gate."""
    path = tmp_path / "missing.json"

    result = run_validator(path)

    assert result.returncode == 1
    assert "Test quality report rejected" in result.stderr


@pytest.mark.parametrize("content", ["{", "not json", "[]", "null"])
def test_cli_rejects_invalid_report_content(tmp_path, content):
    """Malformed JSON or a nonobject report is rejected by the CLI."""
    path = tmp_path / "gate.json"
    path.write_text(content, encoding="utf-8")

    result = run_validator(path)

    assert result.returncode == 1
    assert "Test quality report rejected" in result.stderr


@pytest.mark.parametrize(("field", "value"), [
    ("status", "failed"), ("status", None), ("semantic_rules", "soft"),
    ("errors", 1), ("errors", True), ("errors", False), ("errors", "0"), ("errors", 0.0),
    ("errors", -1), ("errors", None), ("infra_errors", 1), ("infra_errors", None),
])
def test_cli_rejects_invalid_summary(tmp_path, report, field, value):
    """The summary must declare strict success with valid zero error counts."""
    report["summary"][field] = value
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert f"summary.{field}" in result.stderr


@pytest.mark.parametrize("index", [0, 1], ids=["ruff", "eslint"])
def test_cli_rejects_missing_linter(tmp_path, report, index):
    """Both configured linters must be present to accept the report."""
    report["summary"]["external_lint"]["results"].pop(index)
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert "exactly Ruff and ESLint" in result.stderr


@pytest.mark.parametrize(("source", "index"), [("ruff", 0), ("eslint", 1)])
@pytest.mark.parametrize("status", ["unavailable", "misconfigured", "skipped", "unknown"])
def test_cli_rejects_incomplete_linter(tmp_path, report, source, index, status):
    """A noncompleted linter cannot be hidden behind a passed gate summary."""
    item = report["summary"]["external_lint"]["results"][index]
    item["status"] = status
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert f"external lint {source} status must be ok" in result.stderr


@pytest.mark.parametrize("source", ["ruff", "eslint", "unknown", None, []])
def test_cli_rejects_invalid_linter_sources(tmp_path, report, source):
    """Duplicate or invalid source names cannot stand in for the two linters."""
    report["summary"]["external_lint"]["results"] = [
        {"source": source, "status": "ok"}, {"source": source, "status": "ok"},
    ]
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert "unique Ruff and ESLint" in result.stderr


def test_cli_rejects_extra_linter(tmp_path, report):
    """Unexpected sources are rejected instead of silently ignored."""
    report["summary"]["external_lint"]["results"].append({"source": "other", "status": "ok"})
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert "exactly Ruff and ESLint" in result.stderr


def test_cli_rejects_disabled_external_lint(tmp_path, report):
    """A gate with external lint switched off does not provide full evidence."""
    report["summary"]["external_lint"]["mode"] = "off"
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert "external_lint.mode must be run" in result.stderr


@pytest.mark.parametrize("layer", ["backend", "unit", "e2e"])
def test_cli_rejects_missing_layer(tmp_path, report, layer):
    """Reports missing a required test layer cannot pass the postcondition."""
    layers = {"backend": report, "unit": report["frontend"], "e2e": report["frontend"]}
    del layers[layer][layer]
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert f"{layer} must be an object" in result.stderr


@pytest.mark.parametrize("layer", ["backend", "unit", "e2e"])
@pytest.mark.parametrize("field", ["files", "tests"])
def test_cli_rejects_empty_layer(tmp_path, report, layer, field):
    """A linter's ok status without populated target evidence is insufficient."""
    layers = {"backend": report["backend"], **report["frontend"]}
    layers[layer][field] = 0
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert f"{layer}.{field} must be a positive integer" in result.stderr


@pytest.mark.parametrize("value", [True, "1", 1.0, -1, None])
def test_cli_rejects_invalid_layer_count(tmp_path, report, value):
    """Target counts must be positive integers rather than coercible values."""
    report["backend"]["files"] = value
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert "backend.files must be a positive integer" in result.stderr


@pytest.mark.parametrize("field", ["summary", "frontend", "backend"])
def test_cli_rejects_nonobject_section(tmp_path, report, field):
    """Malformed report sections receive a diagnostic instead of a traceback."""
    report[field] = []
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert f"{field} must be an object" in result.stderr


@pytest.mark.parametrize("results", [None, {}, [None, None]])
def test_cli_rejects_invalid_linter_result_structure(tmp_path, report, results):
    """Linter evidence must be a list of report objects with required fields."""
    report["summary"]["external_lint"]["results"] = results
    path = write_report(tmp_path, report)

    result = run_validator(path)

    assert result.returncode == 1
    assert "Test quality report rejected" in result.stderr
