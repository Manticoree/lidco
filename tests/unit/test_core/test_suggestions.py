"""Tests for contextual next-step suggestions — Task 155."""

from __future__ import annotations

from lidco.core.suggestions import suggest, MAX_SUGGESTIONS


# ── helpers ───────────────────────────────────────────────────────────────────

def _tc(tool: str, **args) -> dict:
    return {"tool": tool, "args": args}


# ── basic contract ────────────────────────────────────────────────────────────

class TestContract:
    def test_returns_list(self):
        result = suggest([])
        assert isinstance(result, list)

    def test_never_exceeds_max(self):
        assert len(suggest([])) <= MAX_SUGGESTIONS

    def test_never_empty(self):
        assert len(suggest([])) >= 1

    def test_all_items_are_strings(self):
        for item in suggest([_tc("file_write", path="x.py"), _tc("file_edit", path="y.py")]):
            assert isinstance(item, str)


# ── file edit suggestions ─────────────────────────────────────────────────────

class TestFileEditSuggestions:
    def test_file_write_suggests_diff(self):
        hints = suggest([_tc("file_write", path="src/main.py")])
        combined = " ".join(hints)
        assert "diff" in combined.lower()

    def test_file_edit_suggests_tests(self):
        hints = suggest([_tc("file_edit", path="src/auth.py")])
        combined = " ".join(hints)
        assert "тест" in combined.lower() or "pytest" in combined.lower()

    def test_mixed_write_and_edit(self):
        hints = suggest([_tc("file_write", path="a.py"), _tc("file_edit", path="b.py")])
        assert len(hints) <= MAX_SUGGESTIONS


# ── bash/test suggestions ─────────────────────────────────────────────────────

class TestBashSuggestions:
    def test_pytest_bash_suggests_coverage(self):
        hints = suggest([_tc("bash", command="python -m pytest -q")])
        combined = " ".join(hints)
        assert "coverage" in combined.lower() or "commit" in combined.lower()

    def test_non_test_bash_suggests_status(self):
        hints = suggest([_tc("bash", command="echo hello")])
        combined = " ".join(hints)
        assert "status" in combined.lower() or "retry" in combined.lower()


# ── search-only suggestions ───────────────────────────────────────────────────

class TestSearchSuggestions:
    def test_grep_only_suggests_edit(self):
        hints = suggest([_tc("grep", pattern="TODO")])
        combined = " ".join(hints)
        assert "редактир" in combined.lower() or "coder" in combined.lower()

    def test_glob_only_suggests_edit(self):
        hints = suggest([_tc("glob", pattern="*.py")])
        combined = " ".join(hints)
        assert len(hints) >= 1

    def test_read_only_no_write_suggests_next(self):
        hints = suggest([_tc("file_read", path="x.py"), _tc("grep", pattern="foo")])
        assert len(hints) >= 1


# ── git suggestions ───────────────────────────────────────────────────────────

class TestGitSuggestions:
    def test_git_suggests_pr(self):
        hints = suggest([_tc("git", subcommand="commit")])
        combined = " ".join(hints)
        assert "pull request" in combined.lower() or "status" in combined.lower()


# ── pure text (no tool calls) ─────────────────────────────────────────────────

class TestTextOnlySuggestions:
    def test_error_content_suggests_debug(self):
        hints = suggest([], content="Traceback: error in auth.py")
        combined = " ".join(hints)
        assert "исправ" in combined.lower() or "debug" in combined.lower()

    def test_explain_content_suggests_implement(self):
        hints = suggest([], content="Объяснение: вот как работает система")
        combined = " ".join(hints)
        assert "реализ" in combined.lower() or "architect" in combined.lower()

    def test_test_content_suggests_write_tests(self):
        hints = suggest([], content="тесты покрывают основные сценарии")
        combined = " ".join(hints)
        assert "тест" in combined.lower() or "tester" in combined.lower()

    def test_generic_content_suggests_retry(self):
        hints = suggest([], content="Вот ответ на ваш вопрос")
        combined = " ".join(hints)
        assert "retry" in combined.lower() or "export" in combined.lower()

    def test_empty_content_still_returns_hints(self):
        hints = suggest([], content="")
        assert len(hints) >= 1


# ── renderer integration ──────────────────────────────────────────────────────

class TestRendererSuggestions:
    """renderer.suggestions() prints a dim hint line."""

    def test_renders_items(self):
        from io import StringIO
        from rich.console import Console
        from lidco.cli.renderer import Renderer

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        renderer = Renderer(console)
        renderer.suggestions(["вариант А", "вариант Б"])
        output = buf.getvalue()
        assert "вариант А" in output
        assert "вариант Б" in output

    def test_renders_what_next_label(self):
        from io import StringIO
        from rich.console import Console
        from lidco.cli.renderer import Renderer

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        renderer = Renderer(console)
        renderer.suggestions(["hint"])
        output = buf.getvalue()
        assert "дальше" in output.lower() or "1." in output

    def test_empty_list_no_output(self):
        from io import StringIO
        from rich.console import Console
        from lidco.cli.renderer import Renderer

        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        renderer = Renderer(console)
        renderer.suggestions([])
        assert buf.getvalue() == ""
