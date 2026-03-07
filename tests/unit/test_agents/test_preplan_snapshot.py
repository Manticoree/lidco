"""Tests for Q16 pre-planning snapshot: symbol extraction + git/coverage snapshot."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.agents.graph import GraphOrchestrator
from lidco.agents.registry import AgentRegistry


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_orch(preplan_snapshot: bool = True) -> GraphOrchestrator:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=MagicMock(
        content="plan",
        model="m",
        tool_calls=[],
        usage={"total_tokens": 10},
        finish_reason="stop",
        cost_usd=0.0,
    ))
    reg = AgentRegistry()
    orch = GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)
    orch.set_preplan_snapshot(preplan_snapshot)
    return orch


# ── _extract_mentioned_symbols ────────────────────────────────────────────────


class TestExtractMentionedSymbols:
    def test_single_backtick_symbol(self):
        result = GraphOrchestrator._extract_mentioned_symbols("Fix the `foo_bar` function")
        assert "foo_bar" in result

    def test_multiple_symbols(self):
        result = GraphOrchestrator._extract_mentioned_symbols(
            "Refactor `handle()` and update `GraphOrchestrator`"
        )
        assert "handle()" in result
        assert "GraphOrchestrator" in result

    def test_no_backticks_returns_empty(self):
        result = GraphOrchestrator._extract_mentioned_symbols("Fix the function")
        assert result == []

    def test_symbol_with_space_excluded(self):
        result = GraphOrchestrator._extract_mentioned_symbols("`some text with spaces`")
        assert result == []

    def test_long_symbol_excluded(self):
        long_sym = "a" * 61
        result = GraphOrchestrator._extract_mentioned_symbols(f"`{long_sym}`")
        assert result == []

    def test_capped_at_ten(self):
        text = " ".join(f"`sym{i}`" for i in range(15))
        result = GraphOrchestrator._extract_mentioned_symbols(text)
        assert len(result) == 10

    def test_empty_backticks_excluded(self):
        result = GraphOrchestrator._extract_mentioned_symbols("see ``")
        assert result == []

    def test_path_like_symbol(self):
        result = GraphOrchestrator._extract_mentioned_symbols("edit `src/lidco/agents/graph.py`")
        assert "src/lidco/agents/graph.py" in result


# ── _run_git_status ───────────────────────────────────────────────────────────


class TestRunGitStatus:
    def test_returns_stdout_on_success(self):
        orch = _make_orch()
        mock_result = MagicMock()
        mock_result.stdout = " M src/foo.py\n?? new_file.py\n"
        with patch("subprocess.run", return_value=mock_result):
            result = orch._run_git_status()
        assert "src/foo.py" in result
        assert "new_file.py" in result

    def test_returns_empty_string_on_exception(self):
        orch = _make_orch()
        with patch("subprocess.run", side_effect=Exception("git not found")):
            result = orch._run_git_status()
        assert result == ""


# ── _build_preplan_snapshot ───────────────────────────────────────────────────


class TestBuildPreplanSnapshot:
    def test_returns_empty_when_disabled(self):
        orch = _make_orch(preplan_snapshot=False)
        result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert result == ""

    def test_returns_section_header_when_git_log_available(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", return_value="abc123 fix thing"):
            with patch("lidco.agents.graph.build_coverage_context", side_effect=Exception("no cov"), create=True):
                result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert "Pre-planning Snapshot" in result
        assert "abc123 fix thing" in result

    def test_returns_empty_when_both_sources_empty(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", return_value=""):
            with patch.object(orch, "_run_git_status", return_value=""):
                with patch("lidco.core.coverage_reader.build_coverage_context", side_effect=Exception):
                    with patch("lidco.core.risk_scorer.compute_all_risk_scores", return_value=[]):
                        result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert result == ""

    def test_failure_safe_on_git_log_exception(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", side_effect=RuntimeError("git failed")):
            # Should not raise
            result = asyncio.run(orch._build_preplan_snapshot("msg"))
        # May return "" if coverage also fails — just verify no exception
        assert isinstance(result, str)

    def test_coverage_section_included(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", return_value=""):
            with patch("lidco.core.coverage_reader.build_coverage_context",
                       return_value="## Coverage\n80%"):
                result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert "80%" in result

    def test_includes_uncommitted_changes_when_nonempty(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", return_value="abc123 fix"):
            with patch.object(orch, "_run_git_status", return_value="M src/foo.py"):
                with patch("lidco.core.coverage_reader.build_coverage_context",
                           side_effect=Exception):
                    result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert "Uncommitted Changes" in result
        assert "M src/foo.py" in result

    def test_skips_uncommitted_changes_section_when_empty(self):
        orch = _make_orch()
        with patch.object(orch, "_run_git_log", return_value="abc123 fix"):
            with patch.object(orch, "_run_git_status", return_value=""):
                with patch("lidco.core.coverage_reader.build_coverage_context",
                           side_effect=Exception):
                    result = asyncio.run(orch._build_preplan_snapshot("add feature"))
        assert "Uncommitted Changes" not in result


# ── _build_symbol_context ─────────────────────────────────────────────────────


class TestBuildSymbolContext:
    def test_empty_symbols_returns_empty(self):
        orch = _make_orch()
        result = asyncio.run(orch._build_symbol_context([]))
        assert result == ""

    def test_returns_section_when_grep_finds_matches(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:10:def handle():"):
            result = asyncio.run(orch._build_symbol_context(["handle"]))
        assert "Referenced Symbols" in result
        assert "handle" in result

    def test_returns_empty_when_grep_finds_nothing(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value=""):
            with patch.object(orch, "_grep_callers", return_value=""):
                result = asyncio.run(orch._build_symbol_context(["no_match"]))
        assert result == ""

    def test_timeout_per_symbol_is_handled(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", side_effect=RuntimeError("err")):
            with patch.object(orch, "_grep_callers", return_value=""):
                # Should not raise, just skip the symbol
                result = asyncio.run(orch._build_symbol_context(["bad_sym"]))
        assert isinstance(result, str)

    def test_definition_header_shown_when_definition_found(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:10:def handle():"):
            with patch.object(orch, "_grep_callers", return_value=""):
                result = asyncio.run(orch._build_symbol_context(["handle"]))
        assert "**Definition:**" in result

    def test_call_sites_header_shown_when_callers_found(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value=""):
            with patch.object(orch, "_grep_callers", return_value="src/bar.py:20:    handle(x)"):
                result = asyncio.run(orch._build_symbol_context(["handle"]))
        assert "**Call sites" in result
        assert "1 found" in result

    def test_both_sections_shown_when_both_found(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:10:def handle():"):
            with patch.object(orch, "_grep_callers",
                               return_value="src/bar.py:20:    handle(x)\nsrc/baz.py:5:    handle(y)"):
                result = asyncio.run(orch._build_symbol_context(["handle"]))
        assert "**Definition:**" in result
        assert "**Call sites (2 found):**" in result

    def test_symbol_skipped_when_both_empty(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value=""):
            with patch.object(orch, "_grep_callers", return_value=""):
                result = asyncio.run(orch._build_symbol_context(["ghost_sym"]))
        assert result == ""

    def test_callers_exception_does_not_fail_symbol(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:1:def fn():"):
            with patch.object(orch, "_grep_callers", side_effect=RuntimeError("grep crash")):
                result = asyncio.run(orch._build_symbol_context(["fn"]))
        # definition still shown; callers section absent
        assert "**Definition:**" in result
        assert "Call sites" not in result

    def test_callers_count_reflects_actual_lines(self):
        orch = _make_orch()
        callers = "\n".join(f"src/f{i}.py:1:    sym()" for i in range(5))
        with patch.object(orch, "_grep_symbol", return_value=""):
            with patch.object(orch, "_grep_callers", return_value=callers):
                result = asyncio.run(orch._build_symbol_context(["sym"]))
        assert "5 found" in result


# ── _grep_callers ─────────────────────────────────────────────────────────────


class TestGrepCallers:
    def test_path_like_symbol_returns_empty(self):
        orch = _make_orch()
        result = orch._grep_callers("src/lidco/agents/graph.py")
        assert result == ""

    def test_single_char_base_returns_empty(self):
        orch = _make_orch()
        result = orch._grep_callers("x")
        assert result == ""

    def test_filters_out_definition_lines(self):
        orch = _make_orch()
        raw_lines = (
            "src/foo.py:10:def handle(self):\n"
            "src/bar.py:20:    result = handle(x)\n"
            "src/baz.py:5:    handle(y, z)\n"
        )
        mock_proc = MagicMock()
        mock_proc.stdout = raw_lines
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_callers("handle")
        lines = result.splitlines()
        assert all("def handle" not in ln for ln in lines)
        assert any("handle(x)" in ln for ln in lines)

    def test_returns_empty_when_no_callers(self):
        orch = _make_orch()
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_callers("no_callers")
        assert result == ""

    def test_caps_at_ten_results(self):
        orch = _make_orch()
        raw_lines = "\n".join(f"src/f{i}.py:1:    fn()" for i in range(15))
        mock_proc = MagicMock()
        mock_proc.stdout = raw_lines
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_callers("fn")
        assert len(result.splitlines()) <= 10

    def test_truncates_lines_at_120_chars(self):
        orch = _make_orch()
        long_line = "src/foo.py:1:    fn(" + "x" * 200 + ")"
        mock_proc = MagicMock()
        mock_proc.stdout = long_line
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_callers("fn")
        for ln in result.splitlines():
            assert len(ln) <= 120

    def test_handles_subprocess_exception(self):
        orch = _make_orch()
        with patch("subprocess.run", side_effect=OSError("grep not found")):
            result = orch._grep_callers("fn")
        assert result == ""

    def test_strips_parens_from_symbol_name(self):
        """Symbol like 'handle()' should be treated as base 'handle'."""
        orch = _make_orch()
        mock_proc = MagicMock()
        mock_proc.stdout = "src/bar.py:5:    handle(x)"
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            orch._grep_callers("handle()")
        # grep was called — base extracted correctly
        assert mock_run.called

    def test_class_definition_line_excluded(self):
        orch = _make_orch()
        raw_lines = (
            "src/foo.py:1:class MyClass(Base):\n"
            "src/bar.py:10:    obj = MyClass(x)\n"
        )
        mock_proc = MagicMock()
        mock_proc.stdout = raw_lines
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_callers("MyClass")
        assert "class MyClass" not in result
        assert "MyClass(x)" in result


# ── _grep_symbol (definitions only) ──────────────────────────────────────────


class TestGrepSymbolDefinitions:
    def test_path_like_symbol_returns_empty(self):
        orch = _make_orch()
        result = orch._grep_symbol("src/lidco/agents/graph.py")
        assert result == ""

    def test_returns_empty_on_subprocess_exception(self):
        orch = _make_orch()
        with patch("subprocess.run", side_effect=OSError("no grep")):
            result = orch._grep_symbol("foo")
        assert result == ""

    def test_returns_def_lines_from_grep_output(self):
        orch = _make_orch()
        mock_proc = MagicMock()
        mock_proc.stdout = "src/foo.py:10:def foo(x):\n"
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_symbol("foo")
        assert "def foo" in result

    def test_caps_at_five_results(self):
        orch = _make_orch()
        raw = "\n".join(f"src/f{i}.py:1:def bar():" for i in range(8))
        mock_proc = MagicMock()
        mock_proc.stdout = raw
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_symbol("bar")
        assert len(result.splitlines()) <= 5


# ── _extract_file_paths ───────────────────────────────────────────────────────


class TestExtractFilePaths:
    def test_unix_path_extracted(self):
        out = "src/foo.py:10:def bar():\n"
        result = GraphOrchestrator._extract_file_paths(out)
        assert result == ["src/foo.py"]

    def test_windows_absolute_path_extracted(self):
        out = "C:\\projects\\foo.py:10:def bar():\n"
        result = GraphOrchestrator._extract_file_paths(out)
        assert result == ["C:\\projects\\foo.py"]

    def test_deduplicates_same_file(self):
        out = "src/foo.py:10:def a():\nsrc/foo.py:20:def b():\n"
        result = GraphOrchestrator._extract_file_paths(out)
        assert result == ["src/foo.py"]

    def test_preserves_order_of_first_occurrence(self):
        out = "src/a.py:1:x\nsrc/b.py:2:y\nsrc/a.py:3:z\n"
        result = GraphOrchestrator._extract_file_paths(out)
        assert result == ["src/a.py", "src/b.py"]

    def test_empty_output_returns_empty_list(self):
        assert GraphOrchestrator._extract_file_paths("") == []

    def test_lines_without_linenum_skipped(self):
        out = "not-a-grep-line\n"
        result = GraphOrchestrator._extract_file_paths(out)
        assert result == []

    def test_multiple_files_returned(self):
        out = "src/a.py:1:x\nsrc/b.py:2:y\nsrc/c.py:3:z\n"
        result = GraphOrchestrator._extract_file_paths(out)
        assert result == ["src/a.py", "src/b.py", "src/c.py"]


# ── _run_git_file_log ─────────────────────────────────────────────────────────


class TestRunGitFileLog:
    def test_returns_stdout_on_success(self):
        orch = _make_orch()
        mock_proc = MagicMock()
        mock_proc.stdout = "abc1234 fix bug\ndef5678 add feature\n"
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._run_git_file_log("src/foo.py")
        assert "abc1234" in result
        assert "def5678" in result

    def test_returns_empty_on_exception(self):
        orch = _make_orch()
        with patch("subprocess.run", side_effect=OSError("git not found")):
            result = orch._run_git_file_log("src/foo.py")
        assert result == ""

    def test_returns_empty_when_stdout_empty(self):
        orch = _make_orch()
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._run_git_file_log("new_file.py")
        assert result == ""

    def test_passes_file_path_to_git(self):
        orch = _make_orch()
        mock_proc = MagicMock()
        mock_proc.stdout = "abc1234 commit\n"
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            orch._run_git_file_log("src/lidco/core/session.py")
        cmd = mock_run.call_args[0][0]
        assert "src/lidco/core/session.py" in cmd


# ── _build_file_history_context ───────────────────────────────────────────────


class TestBuildFileHistoryContext:
    def test_empty_symbols_returns_empty(self):
        orch = _make_orch()
        result = asyncio.run(orch._build_file_history_context([]))
        assert result == ""

    def test_returns_section_when_history_found(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:10:def handle():"):
            with patch.object(orch, "_run_git_file_log", return_value="abc123 fix"):
                result = asyncio.run(orch._build_file_history_context(["handle"]))
        assert "Recent File History" in result
        assert "abc123" in result

    def test_returns_empty_when_grep_finds_no_files(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value=""):
            result = asyncio.run(orch._build_file_history_context(["ghost"]))
        assert result == ""

    def test_returns_empty_when_git_log_empty(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:10:def fn():"):
            with patch.object(orch, "_run_git_file_log", return_value=""):
                result = asyncio.run(orch._build_file_history_context(["fn"]))
        assert result == ""

    def test_deduplicates_files_across_symbols(self):
        orch = _make_orch()
        # Both symbols defined in the same file
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:10:def fn():"):
            with patch.object(orch, "_run_git_file_log", return_value="abc123 fix") as mock_git:
                asyncio.run(orch._build_file_history_context(["fn1", "fn2"]))
        # git log should be called only once (same file)
        assert mock_git.call_count == 1

    def test_caps_at_five_files(self):
        orch = _make_orch()
        # Each symbol has a unique source file
        def make_def(sym):
            return f"src/{sym}.py:1:def {sym}():"

        grep_calls = iter([make_def(f"f{i}") for i in range(8)])
        with patch.object(orch, "_grep_symbol", side_effect=list(grep_calls)):
            with patch.object(orch, "_run_git_file_log", return_value="abc fix") as mock_git:
                asyncio.run(orch._build_file_history_context([f"f{i}" for i in range(8)]))
        assert mock_git.call_count <= 5

    def test_grep_exception_does_not_fail(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", side_effect=RuntimeError("grep err")):
            result = asyncio.run(orch._build_file_history_context(["sym"]))
        assert isinstance(result, str)

    def test_git_exception_per_file_does_not_fail(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:1:def fn():"):
            with patch.object(orch, "_run_git_file_log", side_effect=RuntimeError("git err")):
                result = asyncio.run(orch._build_file_history_context(["fn"]))
        assert isinstance(result, str)

    def test_relative_path_shown_in_output(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:10:def fn():"):
            with patch.object(orch, "_run_git_file_log", return_value="abc123 fix"):
                result = asyncio.run(orch._build_file_history_context(["fn"]))
        # Should contain the file path in some form
        assert "foo.py" in result


# ── _grep_test_files + _build_test_files_context ─────────────────────────────


class TestGrepTestFiles:
    def test_returns_empty_for_short_base(self):
        orch = _make_orch()
        result = orch._grep_test_files("x")
        assert result == []

    def test_returns_empty_when_tests_dir_missing(self, tmp_path):
        orch = _make_orch()
        orch._project_dir = tmp_path  # tmp_path has no tests/ subdir
        result = orch._grep_test_files("foo")
        assert result == []

    def test_returns_file_list_on_success(self, tmp_path):
        orch = _make_orch()
        (tmp_path / "tests").mkdir()  # create tests dir so exists check passes
        orch._project_dir = tmp_path
        mock_proc = MagicMock()
        mock_proc.stdout = "tests/unit/test_foo.py\ntests/unit/test_bar.py\n"
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_test_files("foo_fn")
        assert "tests/unit/test_foo.py" in result
        assert "tests/unit/test_bar.py" in result

    def test_caps_at_five_files(self, tmp_path):
        orch = _make_orch()
        (tmp_path / "tests").mkdir()
        orch._project_dir = tmp_path
        raw = "\n".join(f"tests/test_f{i}.py" for i in range(8))
        mock_proc = MagicMock()
        mock_proc.stdout = raw
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_test_files("fn")
        assert len(result) <= 5

    def test_handles_subprocess_exception(self, tmp_path):
        orch = _make_orch()
        (tmp_path / "tests").mkdir()
        orch._project_dir = tmp_path
        with patch("subprocess.run", side_effect=OSError("no grep")):
            result = orch._grep_test_files("fn")
        assert result == []

    def test_strips_parens_from_symbol(self, tmp_path):
        orch = _make_orch()
        (tmp_path / "tests").mkdir()
        orch._project_dir = tmp_path
        mock_proc = MagicMock()
        mock_proc.stdout = "tests/test_fn.py\n"
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            orch._grep_test_files("handle()")
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        # base "handle" should be in the grep pattern, not "handle()"
        assert any("handle" in arg for arg in cmd)

    def test_returns_empty_list_when_no_matches(self, tmp_path):
        orch = _make_orch()
        (tmp_path / "tests").mkdir()
        orch._project_dir = tmp_path
        mock_proc = MagicMock()
        mock_proc.stdout = ""
        with patch("subprocess.run", return_value=mock_proc):
            result = orch._grep_test_files("ghost_sym")
        assert result == []


class TestBuildTestFilesContext:
    def test_empty_symbols_returns_empty(self):
        orch = _make_orch()
        result = asyncio.run(orch._build_test_files_context([]))
        assert result == ""

    def test_returns_section_header_when_files_found(self, tmp_path):
        orch = _make_orch()
        (tmp_path / "tests").mkdir()
        orch._project_dir = tmp_path
        with patch.object(orch, "_grep_test_files",
                          return_value=["tests/unit/test_foo.py"]):
            result = asyncio.run(orch._build_test_files_context(["foo"]))
        assert "Test Files for Mentioned Symbols" in result
        assert "foo" in result

    def test_returns_empty_when_no_files_found(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_test_files", return_value=[]):
            result = asyncio.run(orch._build_test_files_context(["ghost"]))
        assert result == ""

    def test_shows_file_count(self, tmp_path):
        orch = _make_orch()
        orch._project_dir = tmp_path
        files = [str(tmp_path / f"tests/test_{i}.py") for i in range(3)]
        with patch.object(orch, "_grep_test_files", return_value=files):
            result = asyncio.run(orch._build_test_files_context(["fn"]))
        assert "3 test files" in result

    def test_singular_label_for_one_file(self, tmp_path):
        orch = _make_orch()
        orch._project_dir = tmp_path
        with patch.object(orch, "_grep_test_files",
                          return_value=[str(tmp_path / "tests/test_fn.py")]):
            result = asyncio.run(orch._build_test_files_context(["fn"]))
        assert "1 test file)" in result

    def test_exception_per_symbol_does_not_fail(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_test_files", side_effect=RuntimeError("err")):
            result = asyncio.run(orch._build_test_files_context(["sym"]))
        assert isinstance(result, str)

    def test_multiple_symbols_each_listed(self, tmp_path):
        orch = _make_orch()
        orch._project_dir = tmp_path

        def fake_grep(sym):
            return [f"tests/test_{sym}.py"]

        with patch.object(orch, "_grep_test_files", side_effect=fake_grep):
            result = asyncio.run(orch._build_test_files_context(["alpha", "beta"]))
        assert "alpha" in result
        assert "beta" in result

    def test_skips_symbols_with_no_test_files(self, tmp_path):
        orch = _make_orch()
        orch._project_dir = tmp_path

        def fake_grep(sym):
            return ["tests/test_foo.py"] if sym == "foo" else []

        with patch.object(orch, "_grep_test_files", side_effect=fake_grep):
            result = asyncio.run(orch._build_test_files_context(["foo", "bar"]))
        assert "foo" in result
        assert "bar" not in result


# ── _compute_file_metrics + _build_complexity_context ────────────────────────


class TestComputeFileMetrics:
    def test_returns_empty_dict_on_missing_file(self):
        result = GraphOrchestrator._compute_file_metrics("/no/such/file.py")
        assert result == {}

    def test_counts_loc_skipping_blank_and_comment_lines(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("# comment\n\ndef foo():\n    pass\n    return 1\n")
        result = GraphOrchestrator._compute_file_metrics(str(f))
        assert result["loc"] == 3  # def foo():, pass, return 1

    def test_counts_functions(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("def a():\n    pass\ndef b():\n    pass\nasync def c():\n    pass\n")
        result = GraphOrchestrator._compute_file_metrics(str(f))
        assert result["functions"] == 3

    def test_counts_classes(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("class A:\n    pass\nclass B(A):\n    pass\n")
        result = GraphOrchestrator._compute_file_metrics(str(f))
        assert result["classes"] == 2

    def test_avg_fn_len_computed(self, tmp_path):
        f = tmp_path / "foo.py"
        # 4 code lines, 2 functions → avg = 2
        f.write_text("def a():\n    x = 1\ndef b():\n    y = 2\n")
        result = GraphOrchestrator._compute_file_metrics(str(f))
        assert result["avg_fn_len"] == 2

    def test_avg_fn_len_zero_when_no_functions(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("X = 1\nY = 2\n")
        result = GraphOrchestrator._compute_file_metrics(str(f))
        assert result["avg_fn_len"] == 0

    def test_high_risk_true_when_loc_over_400(self, tmp_path):
        f = tmp_path / "big.py"
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(410)))
        result = GraphOrchestrator._compute_file_metrics(str(f))
        assert result["high_risk"] is True

    def test_high_risk_true_when_functions_over_20(self, tmp_path):
        f = tmp_path / "many_fns.py"
        f.write_text("\n".join(f"def fn_{i}(): pass" for i in range(22)))
        result = GraphOrchestrator._compute_file_metrics(str(f))
        assert result["high_risk"] is True

    def test_high_risk_false_when_within_thresholds(self, tmp_path):
        f = tmp_path / "small.py"
        f.write_text("def foo():\n    pass\n")
        result = GraphOrchestrator._compute_file_metrics(str(f))
        assert result["high_risk"] is False

    def test_empty_file_returns_zeros(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        result = GraphOrchestrator._compute_file_metrics(str(f))
        assert result["loc"] == 0
        assert result["functions"] == 0
        assert result["classes"] == 0
        assert result["high_risk"] is False


class TestBuildComplexityContext:
    def test_empty_symbols_returns_empty(self):
        orch = _make_orch()
        result = asyncio.run(orch._build_complexity_context([]))
        assert result == ""

    def test_returns_section_header_when_files_found(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("def bar():\n    pass\n")
        orch = _make_orch()
        orch._project_dir = tmp_path
        with patch.object(orch, "_grep_symbol", return_value=f"{f}:1:def bar():"):
            result = asyncio.run(orch._build_complexity_context(["bar"]))
        assert "File Complexity" in result

    def test_returns_empty_when_no_source_files_found(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value=""):
            result = asyncio.run(orch._build_complexity_context(["ghost"]))
        assert result == ""

    def test_high_risk_label_in_output(self, tmp_path):
        f = tmp_path / "big.py"
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(410)))
        orch = _make_orch()
        orch._project_dir = tmp_path
        with patch.object(orch, "_grep_symbol", return_value=f"{f}:1:def fn():"):
            result = asyncio.run(orch._build_complexity_context(["fn"]))
        assert "⚠ HIGH" in result

    def test_ok_label_for_small_file(self, tmp_path):
        f = tmp_path / "small.py"
        f.write_text("def foo():\n    pass\n")
        orch = _make_orch()
        orch._project_dir = tmp_path
        with patch.object(orch, "_grep_symbol", return_value=f"{f}:1:def foo():"):
            result = asyncio.run(orch._build_complexity_context(["foo"]))
        assert "| OK |" in result

    def test_exception_per_file_does_not_fail(self):
        orch = _make_orch()
        with patch.object(orch, "_grep_symbol", return_value="src/foo.py:1:def fn():"):
            with patch.object(GraphOrchestrator, "_compute_file_metrics",
                               side_effect=RuntimeError("io err")):
                result = asyncio.run(orch._build_complexity_context(["fn"]))
        assert isinstance(result, str)

    def test_caps_at_five_files(self, tmp_path):
        orch = _make_orch()
        orch._project_dir = tmp_path
        # 8 unique symbols each with a unique source file
        file_paths = []
        for i in range(8):
            f = tmp_path / f"src_{i}.py"
            f.write_text(f"def fn_{i}(): pass\n")
            file_paths.append(f)

        def make_def(sym):
            idx = int(sym.replace("fn_", ""))
            return f"{file_paths[idx]}:1:def {sym}():"

        with patch.object(orch, "_grep_symbol", side_effect=make_def):
            result = asyncio.run(orch._build_complexity_context([f"fn_{i}" for i in range(8)]))
        # At most 5 rows
        rows = [ln for ln in result.splitlines() if ln.startswith("|") and "File" not in ln and "---" not in ln]
        assert len(rows) <= 5

    def test_table_has_correct_columns(self, tmp_path):
        f = tmp_path / "foo.py"
        f.write_text("def bar():\n    pass\n")
        orch = _make_orch()
        orch._project_dir = tmp_path
        with patch.object(orch, "_grep_symbol", return_value=f"{f}:1:def bar():"):
            result = asyncio.run(orch._build_complexity_context(["bar"]))
        assert "LOC" in result
        assert "Fns" in result
        assert "Classes" in result
        assert "Avg fn" in result
        assert "Risk" in result


# ── set_preplan_snapshot setter ───────────────────────────────────────────────


class TestSetPreplanSnapshot:
    def test_default_is_true(self):
        orch = _make_orch()
        assert orch._preplan_snapshot_enabled is True

    def test_set_false(self):
        orch = _make_orch()
        orch.set_preplan_snapshot(False)
        assert orch._preplan_snapshot_enabled is False

    def test_set_true_after_false(self):
        orch = _make_orch()
        orch.set_preplan_snapshot(False)
        orch.set_preplan_snapshot(True)
        assert orch._preplan_snapshot_enabled is True


# ── _detect_ambiguities ───────────────────────────────────────────────────────


def _make_orch_with_llm(llm_response: str | None = None) -> GraphOrchestrator:
    """Helper that wires a real AsyncMock LLM for ambiguity tests."""
    from lidco.llm.base import LLMResponse

    llm = MagicMock()
    if llm_response is not None:
        llm.complete = AsyncMock(return_value=LLMResponse(
            content=llm_response,
            model="cheap",
            tool_calls=[],
            usage={"total_tokens": 30},
            finish_reason="stop",
            cost_usd=0.0,
        ))
    else:
        llm.complete = AsyncMock(side_effect=RuntimeError("LLM down"))
    reg = AgentRegistry()
    return GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)


class TestDetectAmbiguities:
    def test_returns_empty_when_disabled(self):
        orch = _make_orch_with_llm("- [Scope]: unclear")
        orch.set_preplan_ambiguity(False)
        result = asyncio.run(orch._detect_ambiguities("add login feature"))
        assert result == ""

    def test_returns_section_when_ambiguities_found(self):
        orch = _make_orch_with_llm("- [Scope]: unclear → wrong assumption")
        result = asyncio.run(orch._detect_ambiguities("add login feature"))
        assert "Ambiguities Detected" in result
        assert "Scope" in result

    def test_returns_empty_when_llm_says_clear(self):
        orch = _make_orch_with_llm("CLEAR")
        result = asyncio.run(orch._detect_ambiguities("add foo() → returns int"))
        assert result == ""

    def test_returns_empty_when_llm_says_clear_case_insensitive(self):
        orch = _make_orch_with_llm("clear")
        result = asyncio.run(orch._detect_ambiguities("unambiguous request"))
        assert result == ""

    def test_returns_empty_on_llm_exception(self):
        orch = _make_orch_with_llm(None)  # LLM raises RuntimeError
        result = asyncio.run(orch._detect_ambiguities("add feature"))
        assert result == ""

    def test_returns_empty_on_empty_llm_response(self):
        orch = _make_orch_with_llm("")
        result = asyncio.run(orch._detect_ambiguities("add feature"))
        assert result == ""

    def test_uses_routing_role(self):
        orch = _make_orch_with_llm("- [Scope]: unclear")
        asyncio.run(orch._detect_ambiguities("add feature"))
        call_kwargs = orch._llm.complete.call_args
        assert call_kwargs.kwargs.get("role") == "routing"

    def test_max_tokens_is_300(self):
        orch = _make_orch_with_llm("- [Scope]: unclear")
        asyncio.run(orch._detect_ambiguities("add feature"))
        call_kwargs = orch._llm.complete.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 300

    def test_timeout_does_not_raise(self):
        from lidco.llm.base import LLMResponse

        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=asyncio.TimeoutError())
        reg = AgentRegistry()
        orch = GraphOrchestrator(llm=llm, agent_registry=reg, agent_timeout=0)
        result = asyncio.run(orch._detect_ambiguities("add feature"))
        assert result == ""

    def test_default_enabled_is_true(self):
        orch = _make_orch()
        assert orch._preplan_ambiguity_enabled is True

    def test_set_preplan_ambiguity_false(self):
        orch = _make_orch()
        orch.set_preplan_ambiguity(False)
        assert orch._preplan_ambiguity_enabled is False

    def test_set_preplan_ambiguity_true_after_false(self):
        orch = _make_orch()
        orch.set_preplan_ambiguity(False)
        orch.set_preplan_ambiguity(True)
        assert orch._preplan_ambiguity_enabled is True
