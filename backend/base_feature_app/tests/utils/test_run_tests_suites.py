"""Verify test-runner resume state, reporting, and suite execution."""

from __future__ import annotations

import builtins
import importlib.util
import json
import sys
import types
from functools import partial
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run-tests-all-suites.py"

spec = importlib.util.spec_from_file_location("run_tests_all_suites", SCRIPT_PATH)
assert spec is not None
assert spec.loader is not None
run_tests_all_suites = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = run_tests_all_suites
spec.loader.exec_module(run_tests_all_suites)


def make_step_result(
    name: str,
    *,
    status: str = "ok",
    returncode: int = 0,
    log_path: Path | None = None,
) -> run_tests_all_suites.StepResult:
    """Build a suite execution result with explicit reporting metadata."""
    return run_tests_all_suites.StepResult(
        name=name,
        command=["cmd", name],
        returncode=returncode,
        duration=0.1,
        status=status,
        output_tail=[],
        coverage=[],
        log_path=log_path,
    )


class _DummyFuture:
    def __init__(self, result):
        self._result = result

    def result(self):
        return self._result


class _SimpleParallelExecutor:
    def __init__(self, *_args, **_kwargs):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def submit(self, fn):
        return _DummyFuture(fn())


class _DummyProgress:
    def __init__(self, *_args, **_kwargs):
        self.marked = []

    def start(self):
        return None

    def stop(self):
        return None

    def mark_done(self, name, status, duration):
        self.marked.append((name, status, duration))


def _fake_as_completed(futures):
    return list(futures)


def _make_tracking_executor(state: dict):
    class _TrackingExecutor:
        def __init__(self, max_workers):
            state["max_workers"] = max_workers
            self.submitted = []

        def __enter__(self):
            state["instance"] = self
            return self

        def __exit__(self, *_args):
            return False

        def submit(self, fn):
            future = _DummyFuture(fn())
            self.submitted.append(future)
            return future

    return _TrackingExecutor


def test_load_resume_state_returns_none_when_missing(tmp_path):
    """Resume-state loading returns no state when its file is absent."""
    summary_path = tmp_path / run_tests_all_suites.RESUME_FILENAME

    assert run_tests_all_suites.load_resume_state(summary_path) is None


def test_select_suites_for_resume_filters_non_ok():
    """Resume selection includes suites whose previous execution was not successful."""
    suite_runners = [
        ("backend", partial(make_step_result, "backend")),
        ("frontend-unit", partial(make_step_result, "frontend-unit")),
    ]
    resume_state = {
        "suites": {
            "backend": {"status": "ok"},
            "frontend-unit": {"status": "failed"},
        }
    }

    selected, all_passed = run_tests_all_suites.select_suites_for_resume(
        suite_runners,
        resume_state,
    )

    assert [name for name, _runner in selected] == ["frontend-unit"]
    assert all_passed is False


def test_resolve_resume_status_returns_unknown_for_missing_record():
    """A missing suite resume record resolves to unknown status."""
    entry = None

    result = run_tests_all_suites.resolve_resume_status(entry)

    assert result == "unknown"


def test_resolve_resume_status_uses_status_value():
    """An explicit resume status takes precedence in status resolution."""
    entry = {"status": "failed", "returncode": 0}

    assert run_tests_all_suites.resolve_resume_status(entry) == "failed"


def test_resolve_resume_status_uses_returncode_when_status_missing():
    """A resume return code supplies status when no explicit status exists."""
    entry = {"returncode": 0}

    assert run_tests_all_suites.resolve_resume_status(entry) == "ok"


def test_build_suite_summary_sets_log_path_string(tmp_path):
    """Suite summaries serialize the execution log path as a string."""
    log_path = tmp_path / "reports" / "suite.log"
    result = make_step_result("backend", log_path=log_path)

    summary = run_tests_all_suites.build_suite_summary(result)

    assert summary["log_path"] == str(log_path)


def test_resolve_backend_report_root_prefers_core_app(tmp_path):
    """Backend report discovery prefers the configured core application."""
    backend_root = tmp_path / "backend"
    core_root = backend_root / "core_app"
    base_root = backend_root / "base_feature_app"
    base_root.mkdir(parents=True)
    core_root.mkdir()

    assert run_tests_all_suites.resolve_backend_coverage_root(backend_root) == core_root


def test_resolve_backend_report_root_fallback_to_base_feature_app(tmp_path):
    """Backend report discovery falls back to the template application."""
    backend_root = tmp_path / "backend"
    base_root = backend_root / "base_feature_app"
    base_root.mkdir(parents=True)

    assert run_tests_all_suites.resolve_backend_coverage_root(backend_root) == base_root


def _build_backend_summary_lines(tmp_path, monkeypatch):
    """Set up fake coverage infrastructure and return metric lines."""
    backend_root = tmp_path / "backend"
    backend_root.mkdir()
    cov_file = backend_root / ".coverage"
    cov_file.write_text("data", encoding="utf-8")

    sample_path = backend_root / "base_feature_app" / "sample.py"
    sample_path.parent.mkdir(parents=True)
    sample_path.write_text(
        "def alpha():\n    return 1\n\ndef beta():\n    return 2\n",
        encoding="utf-8",
    )

    class FakeNumbers:
        n_statements = 10
        n_missing = 2
        n_branches = 4
        n_missing_branches = 1

    class FakeAnalysis:
        numbers = FakeNumbers()
        executed = {1, 2}

    class FakeRegion:
        def __init__(self, lines):
            self.kind = "function"
            self.lines = lines

    class FakeFileReporter:
        @staticmethod
        def code_regions():
            return [FakeRegion({1, 2}), FakeRegion({10})]

    class FakeCoverageData:
        @staticmethod
        def measured_files():
            return [str(sample_path)]

    class FakeCoverage:
        def __init__(self, data_file):
            self.data_file = data_file

        def load(self):
            return None

        def get_data(self):
            return FakeCoverageData()

        @staticmethod
        def _analyze(_filepath):
            return FakeAnalysis()

        @staticmethod
        def _get_file_reporter(_filepath):
            return FakeFileReporter()

    fake_module = types.ModuleType("coverage")
    fake_module.Coverage = FakeCoverage
    monkeypatch.setitem(sys.modules, "coverage", fake_module)

    return run_tests_all_suites.read_backend_coverage_summary(backend_root)


def test_read_backend_summary_returns_five_metric_lines(tmp_path, monkeypatch):
    """Backend summaries include all five reported metrics."""
    lines = _build_backend_summary_lines(tmp_path, monkeypatch)

    assert len(lines) == 5


def test_read_backend_summary_statements_metric(tmp_path, monkeypatch):
    """Backend summaries preserve the statement coverage metric."""
    lines = _build_backend_summary_lines(tmp_path, monkeypatch)

    assert "Statements:" in lines[0]
    assert "(8/10)" in lines[0]


def test_read_backend_summary_branches_metric(tmp_path, monkeypatch):
    """Backend summaries preserve the branch coverage metric."""
    lines = _build_backend_summary_lines(tmp_path, monkeypatch)

    assert "Branches:" in lines[1]
    assert "(3/4)" in lines[1]


def test_read_backend_summary_functions_metric(tmp_path, monkeypatch):
    """Backend summaries preserve the function coverage metric."""
    lines = _build_backend_summary_lines(tmp_path, monkeypatch)

    assert "Functions:" in lines[2]
    assert "(1/2)" in lines[2]


def test_read_backend_summary_lines_metric(tmp_path, monkeypatch):
    """Backend summaries preserve the line coverage metric."""
    lines = _build_backend_summary_lines(tmp_path, monkeypatch)

    assert "Lines:" in lines[3]
    assert "(8/10)" in lines[3]


def test_read_backend_summary_total_metric(tmp_path, monkeypatch):
    """Backend summaries preserve the combined coverage metric."""
    lines = _build_backend_summary_lines(tmp_path, monkeypatch)

    assert "Total:" in lines[4]
    assert "78.57%" in lines[4]


def test_read_flow_summary_formats_flow_percent(tmp_path):
    """Flow summaries format the covered-flow percentage for display."""
    summary_path = tmp_path / "e2e-results" / "flow-coverage.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "summary": {
                    "total": 10,
                    "covered": 7,
                    "partial": 1,
                    "failing": 0,
                    "missing": 2,
                }
            }
        ),
        encoding="utf-8",
    )

    lines = run_tests_all_suites.read_flow_coverage_summary(tmp_path)

    assert len(lines) == 3
    assert "Flows covered: 7/10" in lines[0]
    assert "(70.00%)" in lines[0]
    assert "Partial: 1" in lines[1]
    assert "Missing: 2" in lines[2]


def test_run_backend_triggers_erase_when_enabled(tmp_path, monkeypatch):
    """Backend execution erases existing report data when requested."""
    calls = []
    captured = {}
    (tmp_path / "base_feature_app").mkdir()

    def fake_erase(root):
        calls.append(root)

    def fake_run_command(**kwargs):
        captured.update(kwargs)
        return make_step_result("backend")

    monkeypatch.setattr(run_tests_all_suites, "erase_backend_coverage_data", fake_erase)
    monkeypatch.setattr(run_tests_all_suites, "run_command", fake_run_command)

    result = run_tests_all_suites.run_backend(
        backend_root=tmp_path,
        report_dir=tmp_path,
        markers="",
        extra_args=[],
        quiet=True,
        append_log=False,
        run_id=None,
        show_coverage=True,
    )

    assert calls == [tmp_path]
    assert f"--cov={tmp_path / 'base_feature_app'}" in captured["command"]
    assert "--cov-report=term-missing" in captured["command"]
    assert result.name == "backend"


def test_run_backend_skips_erase_when_disabled(tmp_path, monkeypatch):
    """Backend execution preserves report data when erasure is disabled."""
    calls = []
    captured = {}
    (tmp_path / "base_feature_app").mkdir()

    def fake_erase(*_args, **_kwargs):
        calls.append("called")

    def fake_run_command(**kwargs):
        captured.update(kwargs)
        return make_step_result("backend")

    monkeypatch.setattr(run_tests_all_suites, "erase_backend_coverage_data", fake_erase)
    monkeypatch.setattr(run_tests_all_suites, "run_command", fake_run_command)

    result = run_tests_all_suites.run_backend(
        backend_root=tmp_path,
        report_dir=tmp_path,
        markers="",
        extra_args=[],
        quiet=False,
        append_log=False,
        run_id=None,
        show_coverage=False,
    )

    assert calls == []
    assert "--cov-report=term-missing" not in captured["command"]
    assert result.name == "backend"


def test_erase_backend_data_invokes_report_module(tmp_path, monkeypatch):
    """Report erasure invokes the backend reporting module."""
    captured = {}

    class FakeCoverage:
        def __init__(self, data_file):
            captured["data_file"] = data_file

        def erase(self):
            captured["erased"] = True

    fake_module = types.ModuleType("coverage")
    fake_module.Coverage = FakeCoverage
    monkeypatch.setitem(sys.modules, "coverage", fake_module)

    run_tests_all_suites.erase_backend_coverage_data(tmp_path)

    assert captured["data_file"] == str(tmp_path / ".coverage")
    assert captured["erased"] is True


def test_build_log_separator_includes_suite_metadata():
    """The execution-log separator includes the suite's identifying metadata."""
    header = run_tests_all_suites.build_log_separator("run123", "backend", ["pytest", "-q"])

    assert "Run ID: run123" in header
    assert "Suite: backend" in header
    assert "Command: pytest -q" in header
    assert "Timestamp:" in header


def test_record_suite_result_writes_resume_file(tmp_path):
    """Recording a suite result persists its resume-state file."""
    resume_path = tmp_path / "reports" / run_tests_all_suites.RESUME_FILENAME
    backend_log = tmp_path / "backend.log"
    result_backend = make_step_result("backend", log_path=backend_log)

    payload = run_tests_all_suites.record_suite_result(
        resume_path,
        resume_state=None,
        result=result_backend,
        run_id="run123",
    )

    saved = json.loads(resume_path.read_text(encoding="utf-8"))
    suite_payload = saved["suites"]["backend"]

    assert payload["run_id"] == "run123"
    assert saved["run_id"] == "run123"
    assert suite_payload["suite"] == "backend"
    assert suite_payload["log_path"] == str(backend_log)
    assert saved["updated_at"]


def test_run_command_writes_log_separator(tmp_path):
    """run_command prepends the log separator and captures subprocess output in the log file."""
    log_path = tmp_path / "suite.log"
    command = [sys.executable, "-c", "print('hello')"]

    result = run_tests_all_suites.run_command(
        name="backend",
        command=command,
        cwd=tmp_path,
        log_path=log_path,
        append_log=True,
        quiet=True,
        run_id="run123",
    )

    assert result.status == "ok"
    content = log_path.read_text(encoding="utf-8")
    assert "Run ID: run123" in content
    assert "Suite: backend" in content
    assert "Command:" in content
    assert "hello" in content


def test_extract_backend_report_table_reads_header(tmp_path):
    """Backend report extraction preserves the table header."""
    log_path = tmp_path / "backend.log"
    log_path.write_text(
        "\n".join(
            [
                "random line",
                "===================== Coverage Report  (production files) =====================",
                "File  Stmts  Miss  Cover  Bar",
                "base_feature_app/sample.py  1  0  100%  ██████",
                "===================== 24 passed in 2.0s =====================",
                "tail line",
            ]
        ),
        encoding="utf-8",
    )

    lines = run_tests_all_suites.extract_backend_coverage_table(log_path)

    assert len(lines) == 3
    assert "Coverage Report" in lines[0]
    assert "base_feature_app/sample.py" in lines[2]


def test_main_runs_sequential_by_default(tmp_path, monkeypatch):
    """main() runs all three suites sequentially and does not use ThreadPoolExecutor by default."""
    calls = []
    append_logs = []
    quiet_flags = []

    def fake_backend(**kwargs):
        append_logs.append(kwargs["append_log"])
        quiet_flags.append(kwargs["quiet"])
        calls.append("backend")
        return make_step_result("backend")

    def fake_unit(**kwargs):
        append_logs.append(kwargs["append_log"])
        quiet_flags.append(kwargs["quiet"])
        calls.append("frontend-unit")
        return make_step_result("frontend-unit")

    def fake_e2e(**kwargs):
        append_logs.append(kwargs["append_log"])
        quiet_flags.append(kwargs["quiet"])
        calls.append("frontend-e2e")
        return make_step_result("frontend-e2e")

    class BoomExecutor:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("ThreadPoolExecutor should not be used")

    monkeypatch.setattr(run_tests_all_suites, "run_backend", fake_backend)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_unit", fake_unit)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_e2e", fake_e2e)
    monkeypatch.setattr(run_tests_all_suites, "print_final_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_tests_all_suites, "ThreadPoolExecutor", BoomExecutor)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run-tests-all-suites.py", "--report-dir", str(tmp_path)],
    )

    exit_code = run_tests_all_suites.main()

    assert exit_code == 0
    assert calls == ["backend", "frontend-unit", "frontend-e2e"]
    assert append_logs == [False, False, False]
    assert quiet_flags == [True, True, True]


def test_main_parallel_verbose_sets_quiet_false(tmp_path, monkeypatch):
    """--parallel --verbose forces quiet=False on every suite runner call."""
    quiet_flags = []

    def fake_backend(**kwargs):
        quiet_flags.append(kwargs["quiet"])
        return make_step_result("backend")

    def fake_unit(**kwargs):
        quiet_flags.append(kwargs["quiet"])
        return make_step_result("frontend-unit")

    def fake_e2e(**kwargs):
        quiet_flags.append(kwargs["quiet"])
        return make_step_result("frontend-e2e")

    monkeypatch.setattr(run_tests_all_suites, "run_backend", fake_backend)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_unit", fake_unit)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_e2e", fake_e2e)
    monkeypatch.setattr(run_tests_all_suites, "ThreadPoolExecutor", _SimpleParallelExecutor)
    monkeypatch.setattr(run_tests_all_suites, "as_completed", _fake_as_completed)
    monkeypatch.setattr(run_tests_all_suites, "print_final_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-tests-all-suites.py",
            "--parallel",
            "--verbose",
            "--report-dir",
            str(tmp_path),
        ],
    )

    exit_code = run_tests_all_suites.main()

    assert exit_code == 0
    assert quiet_flags == [False, False, False]


def test_main_sequential_quiet_sets_quiet_true(tmp_path, monkeypatch):
    """--quiet flag propagates quiet=True to every suite runner call in sequential mode."""
    quiet_flags = []

    def fake_backend(**kwargs):
        quiet_flags.append(kwargs["quiet"])
        return make_step_result("backend")

    def fake_unit(**kwargs):
        quiet_flags.append(kwargs["quiet"])
        return make_step_result("frontend-unit")

    def fake_e2e(**kwargs):
        quiet_flags.append(kwargs["quiet"])
        return make_step_result("frontend-e2e")

    monkeypatch.setattr(run_tests_all_suites, "run_backend", fake_backend)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_unit", fake_unit)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_e2e", fake_e2e)
    monkeypatch.setattr(run_tests_all_suites, "print_final_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run-tests-all-suites.py",
            "--quiet",
            "--report-dir",
            str(tmp_path),
        ],
    )

    exit_code = run_tests_all_suites.main()

    assert exit_code == 0
    assert quiet_flags == [True, True, True]


def test_main_parallel_uses_thread_pool(tmp_path, monkeypatch):
    """--parallel mode uses ThreadPoolExecutor with max_workers=3 and submits all three suites."""
    calls = []
    executor_state = {}

    def fake_backend(**_kwargs):
        calls.append("backend")
        return make_step_result("backend")

    def fake_unit(**_kwargs):
        calls.append("frontend-unit")
        return make_step_result("frontend-unit")

    def fake_e2e(**_kwargs):
        calls.append("frontend-e2e")
        return make_step_result("frontend-e2e")

    monkeypatch.setattr(run_tests_all_suites, "run_backend", fake_backend)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_unit", fake_unit)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_e2e", fake_e2e)
    monkeypatch.setattr(run_tests_all_suites, "ThreadPoolExecutor", _make_tracking_executor(executor_state))
    monkeypatch.setattr(run_tests_all_suites, "as_completed", _fake_as_completed)
    monkeypatch.setattr(run_tests_all_suites, "_LiveProgress", _DummyProgress)
    monkeypatch.setattr(run_tests_all_suites, "print_final_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run-tests-all-suites.py", "--parallel", "--report-dir", str(tmp_path)],
    )

    exit_code = run_tests_all_suites.main()

    assert exit_code == 0
    assert executor_state["max_workers"] == 3
    assert len(executor_state["instance"].submitted) == 3
    assert calls == ["backend", "frontend-unit", "frontend-e2e"]


def test_main_resume_runs_suites_when_summary_missing(tmp_path, monkeypatch):
    """--resume runs all suites with append_log=True when no resume summary file exists."""
    calls = []
    append_logs = []

    def fake_backend(**kwargs):
        append_logs.append(kwargs["append_log"])
        calls.append("backend")
        return make_step_result("backend")

    def fake_unit(**kwargs):
        append_logs.append(kwargs["append_log"])
        calls.append("frontend-unit")
        return make_step_result("frontend-unit")

    def fake_e2e(**kwargs):
        append_logs.append(kwargs["append_log"])
        calls.append("frontend-e2e")
        return make_step_result("frontend-e2e")

    monkeypatch.setattr(run_tests_all_suites, "run_backend", fake_backend)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_unit", fake_unit)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_e2e", fake_e2e)
    monkeypatch.setattr(run_tests_all_suites, "print_final_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run-tests-all-suites.py", "--resume", "--report-dir", str(tmp_path)],
    )

    exit_code = run_tests_all_suites.main()

    assert exit_code == 0
    assert calls == ["backend", "frontend-unit", "frontend-e2e"]
    assert append_logs == [True, True, True]


def test_main_resume_exits_when_suites_ok(tmp_path, monkeypatch):
    """--resume skips execution and exits 0 when the summary file shows all suites passed."""
    resume_path = tmp_path / run_tests_all_suites.RESUME_FILENAME
    summary = {
        "run_id": "run123",
        "schema_version": 1,
        "suites": {
            "backend": {"status": "ok"},
            "frontend-unit": {"status": "ok"},
            "frontend-e2e": {"status": "ok"},
        },
    }
    resume_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    printed = []

    def fail_backend(**_kwargs):
        raise AssertionError("Runner should not execute")

    def fake_print(message, *_args, **_kwargs):
        printed.append(message)

    monkeypatch.setattr(run_tests_all_suites, "run_backend", fail_backend)
    monkeypatch.setattr(run_tests_all_suites, "print_final_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(builtins, "print", fake_print)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run-tests-all-suites.py", "--resume", "--report-dir", str(tmp_path)],
    )

    exit_code = run_tests_all_suites.main()

    assert exit_code == 0
    assert "Todas las suites ya pasaron" in " ".join(printed)


def test_main_resume_runs_failed_suites_only(tmp_path, monkeypatch):
    """--resume re-runs only the suites marked failed in the existing summary file."""
    resume_path = tmp_path / run_tests_all_suites.RESUME_FILENAME
    summary = {
        "run_id": "run123",
        "schema_version": 1,
        "suites": {
            "backend": {"status": "ok"},
            "frontend-unit": {"status": "failed", "returncode": 1},
            "frontend-e2e": {"status": "ok"},
        },
    }
    resume_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    calls = []
    append_logs = []

    def fake_backend(**kwargs):
        append_logs.append(kwargs["append_log"])
        calls.append("backend")
        return make_step_result("backend")

    def fake_unit(**kwargs):
        append_logs.append(kwargs["append_log"])
        calls.append("frontend-unit")
        return make_step_result("frontend-unit")

    def fake_e2e(**kwargs):
        append_logs.append(kwargs["append_log"])
        calls.append("frontend-e2e")
        return make_step_result("frontend-e2e")

    monkeypatch.setattr(run_tests_all_suites, "run_backend", fake_backend)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_unit", fake_unit)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_e2e", fake_e2e)
    monkeypatch.setattr(run_tests_all_suites, "print_final_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run-tests-all-suites.py", "--resume", "--report-dir", str(tmp_path)],
    )

    exit_code = run_tests_all_suites.main()

    assert exit_code == 0
    assert calls == ["frontend-unit"]
    assert append_logs == [True]


def test_main_writes_resume_summary_file(tmp_path, monkeypatch):
    """main() writes a resume summary JSON file containing a run_id after a successful run."""
    def fake_backend(**_kwargs):
        return make_step_result("backend")

    def fake_unit(**_kwargs):
        return make_step_result("frontend-unit")

    def fake_e2e(**_kwargs):
        return make_step_result("frontend-e2e")

    monkeypatch.setattr(run_tests_all_suites, "run_backend", fake_backend)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_unit", fake_unit)
    monkeypatch.setattr(run_tests_all_suites, "run_frontend_e2e", fake_e2e)
    monkeypatch.setattr(run_tests_all_suites, "print_final_report", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run-tests-all-suites.py", "--report-dir", str(tmp_path)],
    )

    exit_code = run_tests_all_suites.main()

    resume_path = tmp_path / run_tests_all_suites.RESUME_FILENAME
    payload = json.loads(resume_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["run_id"]
    assert set(payload["suites"].keys()) == {"backend", "frontend-unit", "frontend-e2e"}
