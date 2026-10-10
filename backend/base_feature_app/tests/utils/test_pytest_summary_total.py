"""Verify the combined testing summary displayed by pytest."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFTEST_PATH = REPO_ROOT / "backend" / "conftest.py"

spec = importlib.util.spec_from_file_location("backend_conftest", CONFTEST_PATH)
assert spec is not None
assert spec.loader is not None
backend_conftest = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = backend_conftest
spec.loader.exec_module(backend_conftest)


def _run_fake_terminal_summary(tmp_path, monkeypatch):
    """Set up fake coverage infrastructure and return terminal output lines."""
    coverage_file = tmp_path / ".coverage"
    coverage_file.write_text("data", encoding="utf-8")

    sample_path = tmp_path / "sample.py"
    sample_path.write_text(
        "def alpha():\n    return 1\n\ndef beta():\n    return 2\n",
        encoding="utf-8",
    )

    report_payload = {
        "totals": {
            "num_statements": 10,
            "missing_lines": 2,
            "covered_lines": 8,
            "percent_covered": 80.0,
            "num_lines": 10,
            "num_branches": 4,
            "missing_branches": 1,
            "covered_branches": 3,
        },
        "files": {
            "sample.py": {
                "summary": {
                    "num_statements": 10,
                    "missing_lines": 2,
                    "percent_covered": 80.0,
                }
            }
        },
    }

    class FakeCoverageData:
        def lines(self, filename):
            if str(filename).endswith("sample.py"):
                return [2]
            return []

    class FakeCoverage:
        def __init__(self, data_file):
            self.data_file = data_file

        def load(self):
            return None

        def json_report(self, outfile, omit, ignore_errors):
            Path(outfile).write_text(json.dumps(report_payload), encoding="utf-8")

        def get_data(self):
            return FakeCoverageData()

    fake_module = types.ModuleType("coverage")
    fake_module.Coverage = FakeCoverage
    monkeypatch.setitem(sys.modules, "coverage", fake_module)

    output = []

    class FakeTerminalReporter:
        def write_sep(self, sep, title=None, **_kwargs):
            output.append(f"{sep}{title}")

        def write_line(self, message):
            output.append(message)

    class FakeConfig:
        rootdir = tmp_path

    backend_conftest.pytest_terminal_summary(FakeTerminalReporter(), 0, FakeConfig())
    return output


def test_pytest_summary_prints_combined_total(tmp_path, monkeypatch):
    """The pytest summary prints the combined coverage total."""
    output = _run_fake_terminal_summary(tmp_path, monkeypatch)

    combined_lines = [line for line in output if "TOTAL (combined)" in line]

    assert len(combined_lines) == 1
    combined_line = combined_lines[0]
    assert "26" in combined_line
    assert "6" in combined_line
    assert "76.9%" in combined_line
