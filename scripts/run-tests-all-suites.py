#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Callable, Sequence

TAIL_LINES = 40

# ── ANSI helpers ─────────────────────────────────────────────────────────────
_COLOR = os.environ.get("NO_COLOR") is None and sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text

def _bold(t: str) -> str:    return _c("1", t)
def _dim(t: str) -> str:     return _c("2", t)
def _green(t: str) -> str:   return _c("32", t)
def _red(t: str) -> str:     return _c("31", t)
def _yellow(t: str) -> str:  return _c("33", t)
def _cyan(t: str) -> str:    return _c("36", t)

def _pct_color(pct: float) -> Callable[[str], str]:
    if pct >= 80:
        return _green
    if pct >= 50:
        return _yellow
    return _red


_BACKEND_COV_RE = re.compile(r'(\d+\.?\d*)%((\s+)(\[[^\]]*\]))?')
_JEST_SEP_RE = re.compile(r'^[\s\-|]+$')
_JEST_DATA_PCT_RE = re.compile(r'^\s*(\d+\.?\d*)\s*$')
_JEST_SUMMARY_LINE_RE = re.compile(r'(Statements|Branches|Functions|Lines)\s*:\s*(\d+\.?\d*)%')
_SUMMARY_PCT_RE = re.compile(r'(\d+\.?\d*)%')


def colorize_backend_line(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith('=') and 'COVERAGE' in stripped:
        return _bold(line)
    if 'fully covered' in stripped:
        return _bold(_green(line))
    m = _BACKEND_COV_RE.search(line)
    if not m:
        return line
    try:
        pct = float(m.group(1))
    except ValueError:
        return line
    color_fn = _pct_color(pct)
    pct_colored = color_fn(f"{m.group(1)}%")
    if m.group(4):
        replacement = pct_colored + m.group(3) + _bold(color_fn(m.group(4)))
    else:
        replacement = pct_colored
    return line[:m.start()] + replacement + line[m.end():]


def colorize_jest_line(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith('=') and ('Coverage summary' in stripped or not stripped.replace('=', '').strip()):
        return _bold(line)
    m = _JEST_SUMMARY_LINE_RE.search(line)
    if m:
        try:
            pct = float(m.group(2))
        except ValueError:
            return line
        color_fn = _pct_color(pct)
        pct_colored = color_fn(f"{m.group(2)}%")
        return line[:m.start(2)] + pct_colored + line[m.end(2) + 1:]
    if _JEST_SEP_RE.match(stripped) and '|' in stripped:
        return _dim(line)
    if 'File' in stripped and '% Stmts' in stripped:
        return _bold(line)
    if '|' in line:
        parts = line.split('|')
        if len(parts) >= 5:
            colorized = [parts[0]]
            for i, part in enumerate(parts[1:], 1):
                if i <= 4:
                    pm = _JEST_DATA_PCT_RE.match(part)
                    if pm:
                        try:
                            pct = float(pm.group(1))
                        except ValueError:
                            colorized.append(part)
                            continue
                        color_fn = _pct_color(pct)
                        colorized.append(part.replace(pm.group(1), color_fn(pm.group(1)), 1))
                    else:
                        colorized.append(part)
                else:
                    colorized.append(part)
            return '|'.join(colorized)
    return line


def colorize_coverage_summary_line(line: str) -> str:
    m = _SUMMARY_PCT_RE.search(line)
    if not m:
        return _dim(line)
    try:
        pct = float(m.group(1))
    except ValueError:
        return _dim(line)
    color_fn = _pct_color(pct)
    return line[:m.start()] + color_fn(f"{m.group(1)}%") + line[m.end():]


_SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]


class _LiveProgress:
    """Background thread that redraws a multi-line status block every 0.3s."""

    def __init__(self, suite_names: list[str]):
        self._names = suite_names
        self._status: dict[str, str] = {n: "running" for n in suite_names}
        self._durations: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._start = time.monotonic()
        self._frame = 0
        self._lines_printed = 0

    def mark_done(self, name: str, status: str, duration: float) -> None:
        with self._lock:
            self._status[name] = status
            self._durations[name] = duration

    def _erase(self) -> None:
        if self._lines_printed > 0:
            sys.stdout.write(f"\033[{self._lines_printed}A")
            sys.stdout.write("\033[J")

    def _draw(self) -> None:
        elapsed = time.monotonic() - self._start
        sp = _SPINNER[self._frame % len(_SPINNER)] if _COLOR else "-"
        self._frame += 1
        header = f"  {_cyan(sp)} {_bold('Elapsed')}: {elapsed:.0f}s"
        lines = [header]
        with self._lock:
            for name in self._names:
                st = self._status[name]
                dur = self._durations.get(name)
                if st == "running":
                    tag = _yellow("running...")
                    extra = ""
                elif st == "ok":
                    tag = _green("OK")
                    extra = f" ({dur:.1f}s)" if dur else ""
                else:
                    tag = _red("FAILED")
                    extra = f" ({dur:.1f}s)" if dur else ""
                lines.append(f"    {name:<18} {tag}{extra}")
        done = sum(1 for s in self._status.values() if s != "running")
        total = len(self._names)
        bar_w = 20
        filled = int(done / total * bar_w)
        bar = _green("█" * filled) + _dim("░" * (bar_w - filled))
        lines.append(f"  [{bar}] {done}/{total} suites done")
        out = "\n".join(lines) + "\n"
        sys.stdout.write(out)
        sys.stdout.flush()
        self._lines_printed = len(lines)

    def _loop(self) -> None:
        while not self._stop.wait(0.3):
            self._erase()
            self._draw()

    def start(self) -> None:
        self._draw()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self._erase()
        self._draw()


@dataclass
class SuiteInvocation:
    """Capture the exact child process inputs before deciding whether to resume."""

    command: list[str]
    cwd: Path
    env: dict[str, str]

    def identity(self) -> dict[str, object]:
        """Describe process inputs without persisting environment values."""
        environment = json.dumps(self.env, sort_keys=True, separators=(",", ":"))
        return {
            "command": list(self.command),
            "cwd": str(self.cwd.resolve()),
            "environment_sha256": hashlib.sha256(environment.encode("utf-8")).hexdigest(),
        }


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    duration: float
    status: str
    output_tail: list[str] = field(default_factory=list)
    coverage: list[str] = field(default_factory=list)
    log_path: Path | None = None
    identity: dict[str, object] | None = None


RESUME_FILENAME = "last-run.json"
VALID_STATUSES = {"ok", "failed"}
SUITE_LOG_FILES = {
    "backend": "backend.log",
    "frontend-unit": "frontend-unit.log",
    "frontend-e2e": "frontend-e2e.log",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run backend pytest, frontend unit, and E2E tests with reporting. "
            "Defaults to sequential execution; use --parallel to run concurrently."
        )
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--verbose", action="store_true",
                              help="Show full per-test output (default: only summary tables)")
    output_group.add_argument("--quiet", action="store_true",
                              help="(default) Suppress per-test output, show only summary tables")
    parser.add_argument("--backend-markers", default="",
                        help="pytest marker expression (-m)")
    parser.add_argument("--backend-args", default="",
                        help="Extra args forwarded to pytest")
    parser.add_argument("--unit-args", default="",
                        help="Extra args forwarded to Jest")
    parser.add_argument("--e2e-args", default="",
                        help="Extra args forwarded to Playwright")
    parser.add_argument("--unit-workers", default=None,
                        help="Jest --maxWorkers value (default: auto)")
    parser.add_argument("--e2e-workers", default=None,
                        help="Playwright --workers value (default: per config)")
    parser.add_argument("--skip-backend", action="store_true")
    parser.add_argument("--skip-unit", action="store_true")
    parser.add_argument("--skip-e2e", action="store_true")
    parser.add_argument("--parallel", action="store_true",
                        help="Run suites in parallel instead of sequentially")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last-run.json and re-run failed/unknown suites")
    parser.add_argument("--coverage", action="store_true",
                        help="Show per-suite coverage report in the final summary (default: off)")
    parser.add_argument("--report-dir", default="test-reports")
    return parser


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def create_run_id() -> str:
    return uuid.uuid4().hex


def build_log_separator(run_id: str | None, name: str, command: Sequence[str]) -> str:
    command_text = " ".join(str(item) for item in command)
    run_id_value = run_id or "unknown"
    return (
        "\n"
        + "=" * 80
        + "\n"
        + f"Run ID: {run_id_value}\n"
        + f"Timestamp: {_timestamp()}\n"
        + f"Suite: {name}\n"
        + f"Command: {command_text}\n"
        + "=" * 80
        + "\n"
    )


def _ensure_resume_state(state: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(state, dict):
        state = {}
    if not isinstance(state.get("suites"), dict):
        state["suites"] = {}
    if not isinstance(state.get("schema_version"), int):
        state["schema_version"] = 1
    return state


def load_resume_state(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def write_resume_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def clear_resume_state(path: Path) -> None:
    if path.exists():
        path.unlink()


def clear_suite_logs(report_dir: Path, suite_names: Sequence[str]) -> None:
    if not report_dir.exists():
        return
    for name in suite_names:
        log_name = SUITE_LOG_FILES.get(name)
        if not log_name:
            continue
        log_path = report_dir / log_name
        if log_path.exists():
            log_path.unlink()


def resolve_resume_status(record: object) -> str:
    if not isinstance(record, dict):
        return "unknown"
    status = record.get("status")
    if isinstance(status, str):
        normalized = status.lower()
        if normalized in VALID_STATUSES:
            return normalized
    returncode = record.get("returncode")
    if isinstance(returncode, int):
        return "ok" if returncode == 0 else "failed"
    return "unknown"


def select_suites_for_resume(
    suite_runners: Sequence[tuple[str, partial[StepResult]]],
    resume_state: dict[str, object] | None,
    identities: dict[str, dict[str, object]],
) -> tuple[list[tuple[str, partial[StepResult]]], bool]:
    if not isinstance(resume_state, dict):
        return list(suite_runners), False
    suites = resume_state.get("suites")
    if not isinstance(suites, dict):
        return list(suite_runners), False
    selected: list[tuple[str, partial[StepResult]]] = []
    for name, runner in suite_runners:
        record = suites.get(name)
        identity = record.get("identity") if isinstance(record, dict) else None
        expected = identities.get(name)
        valid = (
            isinstance(identity, dict)
            and isinstance(identity.get("command"), list)
            and bool(identity["command"])
            and all(isinstance(arg, str) for arg in identity["command"])
            and isinstance(identity.get("cwd"), str)
            and Path(identity["cwd"]).is_absolute()
            and isinstance(identity.get("environment_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", identity["environment_sha256"]) is not None
        )
        if resolve_resume_status(record) != "ok" or not valid or identity != expected:
            selected.append((name, runner))
    all_passed = len(selected) == 0 and len(suite_runners) > 0
    return selected, all_passed


def build_suite_summary(result: StepResult) -> dict[str, object]:
    return {
        "suite": result.name,
        "status": result.status,
        "returncode": result.returncode,
        "duration": result.duration,
        "command": result.command,
        "timestamp": _timestamp(),
        "log_path": str(result.log_path) if result.log_path else None,
        "identity": result.identity,
    }


def record_suite_result(
    resume_path: Path,
    resume_state: dict[str, object] | None,
    result: StepResult,
    run_id: str | None = None,
) -> dict[str, object]:
    state = _ensure_resume_state(resume_state)
    suites = state["suites"]
    if isinstance(suites, dict):
        suites[result.name] = build_suite_summary(result)
    if run_id:
        state["run_id"] = run_id
    state["updated_at"] = _timestamp()
    write_resume_state(resume_path, state)
    return state


def split_args(value: str | None) -> list[str]:
    if not value:
        return []
    return shlex.split(value)


def _format_pct(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return str(value)


def resolve_backend_coverage_root(backend_root: Path) -> Path:
    core_path = backend_root / "core_app"
    if core_path.exists():
        return core_path
    base_path = backend_root / "base_feature_app"
    if base_path.exists():
        return base_path
    return core_path


def erase_backend_coverage_data(backend_root: Path) -> None:
    try:
        import coverage as coverage_module
    except ImportError:
        return

    try:
        cov = coverage_module.Coverage(data_file=str(backend_root / ".coverage"))
        cov.erase()
    except Exception:
        return


def read_backend_coverage_summary(backend_root: Path) -> list[str]:
    coverage_path = backend_root / ".coverage"
    if not coverage_path.exists():
        return []
    coverage_root = resolve_backend_coverage_root(backend_root)
    coverage_token = coverage_root.name
    try:
        import coverage as coverage_module
    except ImportError:
        return []
    try:
        cov = coverage_module.Coverage(data_file=str(coverage_path))
        cov.load()
    except Exception:
        return []

    try:
        measured = cov.get_data().measured_files()
    except Exception:
        return []

    total_statements = 0
    total_missing = 0
    total_branches = 0
    total_missing_branches = 0
    total_functions = 0
    total_missing_functions = 0
    total_lines = 0
    total_missing_lines = 0

    for filepath in measured:
        norm = filepath.replace("\\", "/")
        if coverage_token not in norm or "/tests/" in norm:
            continue
        try:
            analysis = cov._analyze(filepath)
            file_reporter = cov._get_file_reporter(filepath)
        except Exception:
            continue
        numbers = analysis.numbers
        if numbers.n_statements == 0:
            continue

        total_statements += numbers.n_statements
        total_missing += numbers.n_missing
        total_branches += numbers.n_branches
        total_missing_branches += numbers.n_missing_branches
        total_lines += numbers.n_statements
        total_missing_lines += numbers.n_missing

        try:
            regions = [
                region
                for region in file_reporter.code_regions()
                if region.kind == "function" and region.lines
            ]
        except Exception:
            regions = []

        if regions:
            executed_lines = analysis.executed
            functions_hit = sum(
                1
                for region in regions
                if set(region.lines) & executed_lines
            )
            total_functions += len(regions)
            total_missing_functions += len(regions) - functions_hit

    if total_statements == 0:
        return []

    statements_covered = total_statements - total_missing
    branches_covered = total_branches - total_missing_branches
    functions_covered = total_functions - total_missing_functions
    lines_covered = total_lines - total_missing_lines

    def _pct(covered: int, total: int) -> float:
        return (covered / total * 100) if total > 0 else 100.0

    total_covered = statements_covered + branches_covered
    total_possible = total_statements + total_branches

    return [
        f"Statements: {_format_pct(_pct(statements_covered, total_statements))}% "
        f"({statements_covered}/{total_statements})",
        f"Branches: {_format_pct(_pct(branches_covered, total_branches))}% "
        f"({branches_covered}/{total_branches})",
        f"Functions: {_format_pct(_pct(functions_covered, total_functions))}% "
        f"({functions_covered}/{total_functions})",
        f"Lines: {_format_pct(_pct(lines_covered, total_lines))}% "
        f"({lines_covered}/{total_lines})",
        f"Total: {_format_pct(_pct(total_covered, total_possible))}%",
    ]


def read_jest_coverage_summary(frontend_root: Path) -> list[str]:
    summary_path = frontend_root / "coverage" / "coverage-summary.json"
    if not summary_path.exists():
        return []
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    total = data.get("total")
    if not isinstance(total, dict):
        return []

    labels = [
        ("Statements", total.get("statements")),
        ("Branches", total.get("branches")),
        ("Functions", total.get("functions")),
        ("Lines", total.get("lines")),
    ]
    lines: list[str] = []
    for label, metric in labels:
        if not isinstance(metric, dict):
            continue
        pct = metric.get("pct")
        covered = metric.get("covered")
        total_count = metric.get("total")
        if pct is None or covered is None or total_count is None:
            continue
        lines.append(f"{label}: {_format_pct(pct)}% ({covered}/{total_count})")
    return lines


def read_flow_coverage_summary(frontend_root: Path) -> list[str]:
    summary_path = frontend_root / "e2e-results" / "flow-coverage.json"
    if not summary_path.exists():
        return []
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return []

    totals = summary.get("totals")
    if isinstance(totals, dict):
        total_flows = totals.get("total")
        covered_flows = totals.get("covered")
        partial_flows = totals.get("partial")
        failing_flows = totals.get("failing")
        missing_flows = totals.get("missing")
        coverage_percent = summary.get("coveredPercent")
    else:
        total_flows = summary.get("total")
        covered_flows = summary.get("covered")
        partial_flows = summary.get("partial")
        failing_flows = summary.get("failing")
        missing_flows = summary.get("missing")
        coverage_percent = summary.get("coveredPercent")
        if (
            coverage_percent is None
            and isinstance(total_flows, (int, float))
            and total_flows > 0
            and isinstance(covered_flows, (int, float))
        ):
            coverage_percent = covered_flows / total_flows * 100

    lines: list[str] = []
    if total_flows is not None and covered_flows is not None:
        pct_value = _format_pct(coverage_percent) if coverage_percent is not None else "0"
        lines.append(f"Flows covered: {covered_flows}/{total_flows} ({pct_value}%)")
    if partial_flows is not None and partial_flows > 0:
        lines.append(f"Partial: {partial_flows}")
    if failing_flows is not None and failing_flows > 0:
        lines.append(f"Failing: {failing_flows}")
    if missing_flows is not None and missing_flows > 0:
        lines.append(f"Missing: {missing_flows}")
    return lines


def extract_backend_coverage_table(log_path: Path) -> list[str]:
    """Extract the pytest COVERAGE REPORT table from the backend log."""
    if not log_path or not log_path.exists():
        return []
    try:
        lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    result: list[str] = []
    in_section = False
    for line in lines:
        if not in_section:
            if 'coverage report' in line.lower():
                in_section = True
                result.append(line)
        else:
            stripped = line.strip()
            stripped_lower = stripped.lower()
            if stripped.startswith('=') and (
                'passed' in stripped_lower
                or 'failed' in stripped_lower
                or 'error' in stripped_lower
            ):
                break
            result.append(line)
    return result


def extract_jest_coverage_table(log_path: Path) -> list[str]:
    """Extract the Jest file coverage table and Coverage summary from the frontend-unit log."""
    if not log_path or not log_path.exists():
        return []
    try:
        lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    result: list[str] = []
    in_section = False
    seen_summary = False
    for line in lines:
        stripped = line.strip()
        if not in_section:
            if re.search(r'^-{5,}\|', stripped):
                in_section = True
                result.append(line)
        else:
            result.append(line)
            if 'Coverage summary' in line:
                seen_summary = True
            if seen_summary and stripped.startswith('=') and 'Coverage summary' not in stripped:
                break
    return result


def extract_flow_coverage_report(log_path: Path) -> list[str]:
    """Extract the full FLOW COVERAGE REPORT section from the frontend-e2e log."""
    if not log_path or not log_path.exists():
        return []
    try:
        lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return []
    result: list[str] = []
    in_section = False
    prev_line = ''
    for line in lines:
        if not in_section:
            if 'FLOW COVERAGE REPORT' in line:
                in_section = True
                if prev_line.strip():
                    result.append(prev_line)
                result.append(line)
        else:
            result.append(line)
            if 'Flow coverage report written to' in line:
                break
        prev_line = line
    return result


def print_suite_coverage_table(result: StepResult) -> None:
    """Print the full coverage table extracted from a suite's log file."""
    if not result.log_path:
        return
    if result.name == 'backend':
        table_lines = extract_backend_coverage_table(result.log_path)
        color_fn: Callable[[str], str] | None = colorize_backend_line
    elif result.name == 'frontend-unit':
        table_lines = extract_jest_coverage_table(result.log_path)
        color_fn = colorize_jest_line
    elif result.name == 'frontend-e2e':
        table_lines = extract_flow_coverage_report(result.log_path)
        color_fn = None
    else:
        return
    if not table_lines:
        return
    print()
    for line in table_lines:
        if color_fn is not None and _COLOR:
            print(color_fn(line))
        else:
            print(line)


_PYTEST_FILE_RE = re.compile(r'^\s*(\S+\.py)\s+[.FEsxX]')


def _make_backend_progress() -> Callable[[str], str | None]:
    """Returns a stateful filter: prints the test file name once per file in quiet mode."""
    last: list[str] = ['']

    def _fn(line: str) -> str | None:
        m = _PYTEST_FILE_RE.match(line)
        if m:
            file_path = m.group(1)
            if file_path != last[0]:
                last[0] = file_path
                return f"    {_dim('→')} {file_path}"
        return None

    return _fn


def run_command(
    name: str,
    command: Sequence[str],
    cwd: Path,
    log_path: Path | None,
    env: dict[str, str] | None = None,
    capture_coverage: bool = False,
    append_log: bool = False,
    quiet: bool = False,
    run_id: str | None = None,
    line_transform: Callable[[str], str] | None = None,
    quiet_progress: Callable[[str], str | None] | None = None,
) -> StepResult:
    cmd_list = [str(item) for item in command]
    invocation = SuiteInvocation(cmd_list, cwd.resolve(), dict(os.environ if env is None else env))
    identity = invocation.identity()
    if not quiet:
        print("\n" + "=" * 80)
        print(f"Running step: {name}")
        print(f"Command: {' '.join(cmd_list)}")

    output_tail: deque[str] = deque(maxlen=TAIL_LINES)
    coverage_lines: list[str] = []
    coverage_active = False

    log_file = None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("a" if append_log else "w", encoding="utf-8")
        if append_log:
            log_file.write(build_log_separator(run_id, name, cmd_list))

    start_time = time.monotonic()
    try:
        process = subprocess.Popen(
            cmd_list,
            cwd=invocation.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=invocation.env,
        )
    except FileNotFoundError as exc:
        if log_file:
            log_file.write(f"{exc}\n")
            log_file.close()
        duration = time.monotonic() - start_time
        return StepResult(
            name=name,
            command=cmd_list,
            returncode=127,
            duration=duration,
            status="failed",
            output_tail=[str(exc)],
            log_path=log_path,
            identity=identity,
        )

    if process.stdout is None:
        if log_file:
            log_file.close()
        duration = time.monotonic() - start_time
        return StepResult(
            name=name,
            command=cmd_list,
            returncode=1,
            duration=duration,
            status="failed",
            output_tail=["Failed to capture command output."],
            log_path=log_path,
            identity=identity,
        )

    for line in process.stdout:
        if not quiet:
            if line_transform is not None and _COLOR:
                print(line_transform(line.rstrip('\n')), end='\n')
            else:
                print(line, end="")
        elif quiet_progress is not None:
            msg = quiet_progress(line.rstrip('\n'))
            if msg is not None:
                print(msg, flush=True)
        if log_file:
            log_file.write(line)
        stripped = line.rstrip("\n")
        output_tail.append(stripped)
        if capture_coverage:
            if "Coverage summary" in stripped:
                coverage_lines = [stripped]
                coverage_active = True
                continue
            if coverage_active:
                coverage_lines.append(stripped)
                if stripped.startswith("=") and "Coverage summary" not in stripped:
                    coverage_active = False

    returncode = process.wait()
    duration = time.monotonic() - start_time

    if log_file:
        log_file.flush()
        log_file.close()

    status = "ok" if returncode == 0 else "failed"
    return StepResult(
        name=name,
        command=cmd_list,
        returncode=returncode,
        duration=duration,
        status=status,
        output_tail=list(output_tail),
        coverage=coverage_lines,
        log_path=log_path,
        identity=identity,
    )


def prepare_backend_invocation(
    backend_root: Path,
    markers: str,
    extra_args: Sequence[str],
    show_coverage: bool,
) -> SuiteInvocation:
    """Prepare pytest arguments without modifying coverage data."""
    coverage_root = resolve_backend_coverage_root(backend_root)
    command = [
        sys.executable, "-m", "pytest", f"--cov={coverage_root}",
        "--cov-branch", "--override-ini=addopts=",
    ]
    if show_coverage:
        command.append("--cov-report=term-missing")
    if markers:
        command.extend(["-m", markers])
    command.extend(extra_args)
    return SuiteInvocation(command, backend_root.resolve(), dict(os.environ))


def prepare_unit_invocation(
    frontend_root: Path,
    extra_args: Sequence[str],
    workers: str | None,
    show_coverage: bool,
) -> SuiteInvocation:
    """Prepare Jest arguments with a captured working directory and environment."""
    command = ["npm", "run", "test", "--"]
    if show_coverage:
        command.append("--coverage")
    if workers:
        command.append(f"--maxWorkers={workers}")
    command.extend(extra_args)
    return SuiteInvocation(command, frontend_root.resolve(), dict(os.environ))


def prepare_e2e_invocation(
    frontend_root: Path,
    extra_args: Sequence[str],
    workers: str | None,
) -> SuiteInvocation:
    """Prepare Playwright arguments with a captured working directory and environment."""
    command = ["npx", "playwright", "test"]
    if workers:
        command.append(f"--workers={workers}")
    command.extend(extra_args)
    return SuiteInvocation(command, frontend_root.resolve(), dict(os.environ))


def run_backend(
    backend_root: Path,
    report_dir: Path,
    markers: str,
    extra_args: Sequence[str],
    quiet: bool = False,
    append_log: bool = False,
    run_id: str | None = None,
    show_coverage: bool = False,
    invocation: SuiteInvocation | None = None,
) -> StepResult:
    invocation = invocation or prepare_backend_invocation(backend_root, markers, extra_args, show_coverage)
    if show_coverage:
        erase_backend_coverage_data(backend_root)

    result = run_command(
        name="backend",
        command=invocation.command,
        cwd=invocation.cwd,
        env=invocation.env,
        log_path=report_dir / "backend.log",
        capture_coverage=show_coverage,
        append_log=append_log,
        quiet=quiet,
        run_id=run_id,
        line_transform=colorize_backend_line if show_coverage else None,
        quiet_progress=_make_backend_progress() if quiet else None,
    )
    if show_coverage and result.status == "ok":
        result.coverage = read_backend_coverage_summary(backend_root)
    return result


def run_frontend_unit(
    frontend_root: Path,
    report_dir: Path,
    extra_args: Sequence[str],
    workers: str | None = None,
    quiet: bool = False,
    append_log: bool = False,
    run_id: str | None = None,
    show_coverage: bool = False,
    invocation: SuiteInvocation | None = None,
) -> StepResult:
    invocation = invocation or prepare_unit_invocation(frontend_root, extra_args, workers, show_coverage)

    result = run_command(
        name="frontend-unit",
        command=invocation.command,
        cwd=invocation.cwd,
        env=invocation.env,
        log_path=report_dir / "frontend-unit.log",
        capture_coverage=show_coverage,
        append_log=append_log,
        quiet=quiet,
        run_id=run_id,
        line_transform=colorize_jest_line if show_coverage else None,
    )
    if show_coverage and result.status == "ok":
        result.coverage = read_jest_coverage_summary(frontend_root)
    return result


def run_frontend_e2e(
    frontend_root: Path,
    report_dir: Path,
    extra_args: Sequence[str],
    workers: str | None = None,
    quiet: bool = False,
    append_log: bool = False,
    run_id: str | None = None,
    show_coverage: bool = False,
    invocation: SuiteInvocation | None = None,
) -> StepResult:
    invocation = invocation or prepare_e2e_invocation(frontend_root, extra_args, workers)

    result = run_command(
        name="frontend-e2e",
        command=invocation.command,
        cwd=invocation.cwd,
        log_path=report_dir / "frontend-e2e.log",
        env=invocation.env,
        capture_coverage=False,
        append_log=append_log,
        quiet=quiet,
        run_id=run_id,
    )
    if show_coverage:
        result.coverage = read_flow_coverage_summary(frontend_root)
    return result


def print_final_report(results: list[StepResult], duration: float) -> None:
    sep = _bold("=" * 80)
    print(f"\n{sep}")
    print(_bold("Final suite report"))
    print(f"Total wall-clock duration: {_cyan(f'{duration:.2f}s')}")

    sum_duration = sum(r.duration for r in results)
    if len(results) > 1:
        print(f"Sum of individual durations: {sum_duration:.2f}s")
        saved = sum_duration - duration
        if saved > 0:
            print(f"Time saved by parallelism: {_green(f'{saved:.2f}s')}")

    print()
    for result in results:
        if result.status == "ok":
            tag = _green("OK")
        else:
            tag = _red("FAILED")
        print(f"  {result.name:<18} {tag}  ({result.duration:.2f}s)")
        if result.coverage:
            for line in result.coverage:
                print(f"    {colorize_coverage_summary_line(line)}")
        if result.log_path:
            print(f"    {_dim(f'Log: {result.log_path}')}")

    failed = [result for result in results if result.status == "failed"]
    if failed:
        print(f"\n{_red('!' * 80)}")
        print(_red(_bold("Failures (tail output):")))
        for result in failed:
            print(f"\n{_red('-' * 80)}")
            print(_red(f"{result.name} (exit {result.returncode})"))
            for line in result.output_tail:
                print(line)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    backend_root = repo_root / "backend"
    frontend_root = repo_root / "frontend"
    report_dir = repo_root / args.report_dir
    resume_path = report_dir / RESUME_FILENAME

    parallel = args.parallel
    if args.verbose:
        quiet = False
    else:
        quiet = True
    append_log = args.resume
    show_coverage = args.coverage
    run_id = create_run_id()

    suite_runners: list[tuple[str, partial[StepResult]]] = []
    invocations: dict[str, SuiteInvocation] = {}

    if not args.skip_backend:
        invocations["backend"] = prepare_backend_invocation(
            backend_root, args.backend_markers, split_args(args.backend_args), show_coverage,
        )
        suite_runners.append((
            "backend",
            partial(
                run_backend,
                backend_root=backend_root,
                report_dir=report_dir,
                markers=args.backend_markers,
                extra_args=split_args(args.backend_args),
                quiet=quiet,
                append_log=append_log,
                run_id=run_id,
                show_coverage=show_coverage,
                invocation=invocations["backend"],
            ),
        ))

    if not args.skip_unit:
        invocations["frontend-unit"] = prepare_unit_invocation(
            frontend_root, split_args(args.unit_args), args.unit_workers, show_coverage,
        )
        suite_runners.append((
            "frontend-unit",
            partial(
                run_frontend_unit,
                frontend_root=frontend_root,
                report_dir=report_dir,
                extra_args=split_args(args.unit_args),
                workers=args.unit_workers,
                quiet=quiet,
                append_log=append_log,
                run_id=run_id,
                show_coverage=show_coverage,
                invocation=invocations["frontend-unit"],
            ),
        ))

    if not args.skip_e2e:
        invocations["frontend-e2e"] = prepare_e2e_invocation(
            frontend_root, split_args(args.e2e_args), args.e2e_workers,
        )
        suite_runners.append((
            "frontend-e2e",
            partial(
                run_frontend_e2e,
                frontend_root=frontend_root,
                report_dir=report_dir,
                extra_args=split_args(args.e2e_args),
                workers=args.e2e_workers,
                quiet=quiet,
                append_log=append_log,
                run_id=run_id,
                show_coverage=show_coverage,
                invocation=invocations["frontend-e2e"],
            ),
        ))

    if not args.resume:
        clear_resume_state(resume_path)
        clear_suite_logs(report_dir, [name for name, _ in suite_runners])

    if not suite_runners:
        print("All suites skipped. Nothing to run.")
        return 0

    resume_state = load_resume_state(resume_path) if args.resume else None
    if args.resume:
        selected_suites, all_passed = select_suites_for_resume(
            suite_runners, resume_state,
            {name: invocation.identity() for name, invocation in invocations.items()},
        )
        if resume_state is not None and all_passed:
            print(
                "Todas las suites ya pasaron. Si deseas ejecutarlas de nuevo, "
                "ejecuta el comando sin --resume."
            )
            return 0
        suite_runners = selected_suites
        if not suite_runners:
            print("All suites skipped. Nothing to run.")
            return 0

    results: list[StepResult] = []
    wall_start = time.monotonic()

    if parallel and len(suite_runners) > 1:
        names = [n for n, _ in suite_runners]
        print(_bold(f"Running {len(names)} suites in parallel..."))
        print()
        progress = _LiveProgress(names) if quiet else None
        if progress:
            progress.start()

        with ThreadPoolExecutor(max_workers=len(suite_runners)) as executor:
            futures = {
                executor.submit(runner): name
                for name, runner in suite_runners
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    if progress:
                        progress.mark_done(name, result.status, result.duration)
                    results.append(result)
                    resume_state = record_suite_result(
                        resume_path,
                        resume_state,
                        result,
                        run_id=run_id,
                    )
                except Exception as exc:
                    if progress:
                        progress.mark_done(name, "failed", 0.0)
                    result = StepResult(
                        name=name,
                        command=[],
                        returncode=1,
                        duration=0.0,
                        status="failed",
                        output_tail=[str(exc)],
                    )
                    results.append(result)
                    resume_state = record_suite_result(
                        resume_path,
                        resume_state,
                        result,
                        run_id=run_id,
                    )

        if progress:
            progress.stop()
        if quiet and show_coverage:
            suite_order = {name: i for i, (name, _) in enumerate(suite_runners)}
            for r in sorted(results, key=lambda r: suite_order.get(r.name, 999)):
                print_suite_coverage_table(r)
    else:
        for _name, runner in suite_runners:
            if quiet:
                print(f"  {_cyan('⏳')} {_bold(_name)} running...")
            result = runner()
            if quiet:
                tag = _green('OK') if result.status == 'ok' else _red('FAILED')
                print(f"  {_cyan('✓') if result.status == 'ok' else _red('✗')} {_bold(_name)} {tag} ({result.duration:.1f}s)")
                if show_coverage:
                    print_suite_coverage_table(result)
            results.append(result)
            resume_state = record_suite_result(
                resume_path,
                resume_state,
                result,
                run_id=run_id,
            )

    wall_duration = time.monotonic() - wall_start

    order = {name: i for i, (name, _) in enumerate(suite_runners)}
    results.sort(key=lambda r: order.get(r.name, 999))

    print_final_report(results, wall_duration)
    failed = any(r.status == "failed" for r in results)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
