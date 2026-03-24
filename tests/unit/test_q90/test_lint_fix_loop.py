# tests/unit/test_q90/test_lint_fix_loop.py
"""Tests for LintFixLoop — auto lint-fix iteration loop."""

from __future__ import annotations

import asyncio
from unittest.mock import patch, MagicMock

from lidco.editing.lint_fix_loop import (
    LintFixLoop,
    LintIssue,
    LintResult,
    FixLoopReport,
)


# ---------------------------------------------------------------------------
# parse_lint_output
# ---------------------------------------------------------------------------

def test_parse_lint_output_ruff():
    loop = LintFixLoop()
    raw = (
        "src/foo.py:10:5: E501 Line too long (120 > 88)\n"
        "src/foo.py:20:1: F401 'os' imported but unused"
    )
    results = loop.parse_lint_output(raw, ["src/foo.py"])
    assert len(results) == 1
    assert results[0].file == "src/foo.py"
    assert len(results[0].errors) == 2
    assert results[0].errors[0].line == 10
    assert results[0].errors[0].col == 5
    assert results[0].errors[0].code == "E501"
    assert "Line too long" in results[0].errors[0].message
    assert results[0].errors[1].line == 20
    assert results[0].errors[1].code == "F401"
    assert results[0].clean is False


def test_parse_lint_output_clean():
    loop = LintFixLoop()
    results = loop.parse_lint_output("", ["src/foo.py"])
    assert len(results) == 1
    assert results[0].file == "src/foo.py"
    assert results[0].clean is True
    assert results[0].errors == []


def test_parse_lint_output_multiple_files():
    loop = LintFixLoop()
    raw = (
        "a.py:1:1: E302 blank lines\n"
        "b.py:5:3: W291 trailing whitespace"
    )
    results = loop.parse_lint_output(raw, ["a.py", "b.py"])
    assert len(results) == 2
    files = {r.file for r in results}
    assert files == {"a.py", "b.py"}


def test_parse_lint_output_ignores_unrelated_files():
    loop = LintFixLoop()
    raw = "other.py:1:1: E302 blank lines"
    results = loop.parse_lint_output(raw, ["mine.py"])
    # mine.py should be clean; other.py is not in requested set
    assert len(results) == 1
    assert results[0].file == "mine.py"
    assert results[0].clean is True


def test_parse_lint_output_malformed_lines():
    """Malformed lines are silently skipped."""
    loop = LintFixLoop()
    raw = "not a lint line\nsrc/foo.py:10:5: E501 Line too long"
    results = loop.parse_lint_output(raw, ["src/foo.py"])
    assert len(results) == 1
    assert len(results[0].errors) == 1


# ---------------------------------------------------------------------------
# run_lint
# ---------------------------------------------------------------------------

def test_run_lint_missing_binary():
    loop = LintFixLoop(linter_cmd=["nonexistent_linter_xyz_999"])
    results = loop.run_lint(["src/foo.py"])
    assert results == []


def test_run_lint_success():
    loop = LintFixLoop()
    mock_result = MagicMock()
    mock_result.stdout = "src/foo.py:1:1: E302 Expected 2 blank lines\n"
    mock_result.returncode = 1
    with patch("lidco.editing.lint_fix_loop.subprocess.run", return_value=mock_result):
        results = loop.run_lint(["src/foo.py"])
    assert len(results) == 1
    assert results[0].file == "src/foo.py"
    assert len(results[0].errors) == 1
    assert results[0].errors[0].code == "E302"


def test_run_lint_clean_output():
    loop = LintFixLoop()
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.returncode = 0
    with patch("lidco.editing.lint_fix_loop.subprocess.run", return_value=mock_result):
        results = loop.run_lint(["src/foo.py"])
    assert len(results) == 1
    assert results[0].clean is True


def test_run_lint_timeout():
    """subprocess.TimeoutExpired should be handled gracefully."""
    loop = LintFixLoop(timeout=0.1)
    with patch(
        "lidco.editing.lint_fix_loop.subprocess.run",
        side_effect=subprocess_timeout(),
    ):
        results = loop.run_lint(["src/foo.py"])
    assert results == []


def subprocess_timeout():
    import subprocess
    return subprocess.TimeoutExpired(cmd=["ruff"], timeout=0.1)


# ---------------------------------------------------------------------------
# _detect_linter
# ---------------------------------------------------------------------------

def test_detect_linter_python():
    loop = LintFixLoop()
    cmd = loop._detect_linter("main.py")
    assert cmd[0] == "ruff"
    assert "check" in cmd


def test_detect_linter_js():
    loop = LintFixLoop()
    cmd = loop._detect_linter("app.js")
    assert cmd[0] == "eslint"


def test_detect_linter_ts():
    loop = LintFixLoop()
    cmd = loop._detect_linter("app.tsx")
    assert cmd[0] == "eslint"


def test_detect_linter_go():
    loop = LintFixLoop()
    cmd = loop._detect_linter("main.go")
    assert cmd[0] == "golangci-lint"


def test_detect_linter_unknown():
    loop = LintFixLoop()
    cmd = loop._detect_linter("file.xyz")
    assert cmd == []


def test_detect_linter_respects_explicit_cmd():
    """When linter_cmd is set, _detect_linter is ignored by run_lint."""
    loop = LintFixLoop(linter_cmd=["mypy"])
    # _detect_linter still returns by extension, but run_lint should use linter_cmd
    # We verify run_lint uses the explicit cmd
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.returncode = 0
    with patch("lidco.editing.lint_fix_loop.subprocess.run", return_value=mock_result) as mock_run:
        loop.run_lint(["foo.py"])
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[0] == "mypy"


# ---------------------------------------------------------------------------
# fix_loop
# ---------------------------------------------------------------------------

def test_fix_loop_no_fix_fn():
    """Without fix_fn, loop should still report correctly (no fixing attempted)."""
    loop = LintFixLoop(max_iterations=2)
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.returncode = 0
    with patch("lidco.editing.lint_fix_loop.subprocess.run", return_value=mock_result):
        report = asyncio.run(loop.fix_loop(["src/foo.py"]))
    assert isinstance(report, FixLoopReport)
    assert report.fully_clean is True


def test_fix_loop_cleans_on_first_pass():
    """If first lint clean, fully_clean=True, iterations=1."""
    loop = LintFixLoop()
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.returncode = 0
    with patch("lidco.editing.lint_fix_loop.subprocess.run", return_value=mock_result):
        report = asyncio.run(loop.fix_loop(["src/foo.py"]))
    assert report.fully_clean is True
    assert report.iterations == 1
    assert report.initial_errors == 0
    assert report.final_errors == 0


def test_fix_loop_max_iterations():
    """Even if errors persist, loop stops at max_iterations."""
    call_count = {"n": 0}

    def bad_fix(file, errors):
        call_count["n"] += 1
        return None  # no fix produced

    loop = LintFixLoop(fix_fn=bad_fix, max_iterations=2)
    mock_result = MagicMock()
    mock_result.stdout = "src/foo.py:1:1: E302 Expected 2 blank lines\n"
    mock_result.returncode = 1
    with patch("lidco.editing.lint_fix_loop.subprocess.run", return_value=mock_result):
        report = asyncio.run(loop.fix_loop(["src/foo.py"]))
    assert report.iterations <= 2
    assert report.fully_clean is False
    assert report.final_errors > 0


def test_fix_loop_async_fix_fn():
    """fix_fn can be async — loop should await it."""
    async def async_fix(file, errors):
        return "# fixed content\n"

    calls = []
    mock_clean = MagicMock()
    mock_clean.stdout = ""
    mock_clean.returncode = 0
    mock_dirty = MagicMock()
    mock_dirty.stdout = "f.py:1:1: E302 blank\n"
    mock_dirty.returncode = 1

    side_effects = [mock_dirty, mock_clean]

    loop = LintFixLoop(fix_fn=async_fix, max_iterations=3)
    with patch("lidco.editing.lint_fix_loop.subprocess.run", side_effect=side_effects):
        with patch("builtins.open", MagicMock()):
            report = asyncio.run(loop.fix_loop(["f.py"]))
    assert report.iterations == 2
    assert report.fully_clean is True


def test_fix_loop_sync_fix_fn():
    """fix_fn can be sync — loop handles both."""
    def sync_fix(file, errors):
        return "# fixed\n"

    mock_dirty = MagicMock()
    mock_dirty.stdout = "f.py:1:1: E302 blank\n"
    mock_dirty.returncode = 1
    mock_clean = MagicMock()
    mock_clean.stdout = ""
    mock_clean.returncode = 0

    loop = LintFixLoop(fix_fn=sync_fix, max_iterations=3)
    with patch("lidco.editing.lint_fix_loop.subprocess.run", side_effect=[mock_dirty, mock_clean]):
        with patch("builtins.open", MagicMock()):
            report = asyncio.run(loop.fix_loop(["f.py"]))
    assert report.fully_clean is True
    assert "f.py" in report.files_fixed


def test_fix_loop_fix_fn_returns_none_skips_write():
    """If fix_fn returns None, file is not written."""
    def noop_fix(file, errors):
        return None

    mock_result = MagicMock()
    mock_result.stdout = "f.py:1:1: E302 blank\n"
    mock_result.returncode = 1

    loop = LintFixLoop(fix_fn=noop_fix, max_iterations=1)
    with patch("lidco.editing.lint_fix_loop.subprocess.run", return_value=mock_result):
        with patch("builtins.open", MagicMock()) as mock_open:
            report = asyncio.run(loop.fix_loop(["f.py"]))
    # open should NOT have been called for writing
    mock_open.assert_not_called()
    assert report.files_fixed == []


def test_fix_loop_write_error_handled():
    """If writing fixed content fails, loop continues without crashing."""
    def fix(file, errors):
        return "# fixed\n"

    mock_result = MagicMock()
    mock_result.stdout = "f.py:1:1: E302 blank\n"
    mock_result.returncode = 1

    loop = LintFixLoop(fix_fn=fix, max_iterations=1)
    with patch("lidco.editing.lint_fix_loop.subprocess.run", return_value=mock_result):
        with patch("builtins.open", side_effect=PermissionError("denied")):
            report = asyncio.run(loop.fix_loop(["f.py"]))
    assert isinstance(report, FixLoopReport)


def test_fix_loop_empty_files_list():
    """Empty file list should produce a clean report immediately."""
    loop = LintFixLoop()
    report = asyncio.run(loop.fix_loop([]))
    assert report.fully_clean is True
    assert report.iterations == 0
    assert report.initial_errors == 0


def test_fix_loop_run_lint_failure_graceful():
    """If run_lint returns [] (binary missing), loop handles it."""
    loop = LintFixLoop(linter_cmd=["nonexistent_abc"])
    report = asyncio.run(loop.fix_loop(["f.py"]))
    assert isinstance(report, FixLoopReport)
    assert report.iterations <= 1


# ---------------------------------------------------------------------------
# Dataclass sanity
# ---------------------------------------------------------------------------

def test_lint_issue_fields():
    issue = LintIssue(file="a.py", line=1, col=2, code="E501", message="too long")
    assert issue.file == "a.py"
    assert issue.line == 1
    assert issue.col == 2


def test_lint_result_clean():
    r = LintResult(file="a.py", errors=[], clean=True)
    assert r.clean is True


def test_fix_loop_report_defaults():
    r = FixLoopReport(
        iterations=1,
        initial_errors=0,
        final_errors=0,
        files_fixed=[],
        fully_clean=True,
    )
    assert r.fully_clean is True
    assert r.files_fixed == []
