"""Q55/369,370 — Fuzzy slash-command completion and @mention file auto-complete."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock


def _completions(completer, text: str) -> list[str]:
    from prompt_toolkit.document import Document
    doc = Document(text, cursor_position=len(text))
    return [c.text for c in completer.get_completions(doc, MagicMock())]


class TestFuzzySlashCompletion:
    def _make_completer(self):
        from lidco.cli.completer import LidcoCompleter
        return LidcoCompleter(command_meta={
            "commit": "Commit changes",
            "compact": "Compact history",
            "cost": "Show cost",
            "clear": "Clear session",
            "checkpoint": "Manage checkpoints",
        })

    def test_prefix_match(self):
        c = self._make_completer()
        results = _completions(c, "/co")
        # Should include commit, compact, cost
        assert "commit" in results
        assert "compact" in results
        assert "cost" in results

    def test_fuzzy_match_non_prefix(self):
        c = self._make_completer()
        results = _completions(c, "/cmt")
        # "cmt" fuzzy-matches "commit"
        assert "commit" in results

    def test_no_false_positives(self):
        c = self._make_completer()
        results = _completions(c, "/zzzzzz")
        # No commands match a completely unrelated prefix
        assert results == []

    def test_empty_prefix_returns_all_commands(self):
        c = self._make_completer()
        results = _completions(c, "/")
        assert len(results) == 5

    def test_agent_arg_completion(self):
        from lidco.cli.completer import LidcoCompleter
        c = LidcoCompleter(
            command_meta={"as": "Switch agent"},
            agent_names=["coder", "architect", "tester"],
        )
        results = _completions(c, "/as co")
        assert "coder " in results


class TestAtMentionFileCompletion:
    def test_at_mention_agent_completion(self):
        from lidco.cli.completer import LidcoCompleter
        c = LidcoCompleter(agent_names=["coder", "architect"])
        results = _completions(c, "@cod")
        assert "coder " in results

    def test_at_mention_file_completion(self, tmp_path):
        """@src/f should complete to files matching 'src/f'."""
        from lidco.cli.completer import LidcoCompleter
        # Create some test files
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "foo.py").write_text("x=1")
        (tmp_path / "src" / "bar.py").write_text("y=2")

        c = LidcoCompleter(project_dir=tmp_path)
        results = _completions(c, "@src/foo")
        # Should suggest "src/foo.py "
        assert any("foo.py" in r for r in results)

    def test_at_mention_dot_triggers_file(self, tmp_path):
        """@foo.py should trigger file completion (dot in partial)."""
        from lidco.cli.completer import LidcoCompleter
        (tmp_path / "foo.py").write_text("x=1")
        c = LidcoCompleter(project_dir=tmp_path)
        results = _completions(c, "@foo.py")
        assert any("foo.py" in r for r in results)


class TestContextWindowMeter:
    def test_set_context_usage(self):
        from lidco.cli.stream_display import _StatusBar
        bar = _StatusBar()
        bar.set_context_usage(64_000, 128_000)
        assert bar._ctx_used == 64_000
        assert bar._ctx_max == 128_000

    def test_meter_clamped_at_zero(self):
        from lidco.cli.stream_display import _StatusBar
        bar = _StatusBar()
        bar.set_context_usage(-100, 128_000)
        assert bar._ctx_used == 0

    def test_meter_not_shown_when_zero(self):
        from lidco.cli.stream_display import _StatusBar
        from rich.text import Text
        bar = _StatusBar()
        rendered = bar.__rich__()
        assert "░" not in rendered.plain and "█" not in rendered.plain

    def test_meter_shown_when_set(self):
        from lidco.cli.stream_display import _StatusBar
        bar = _StatusBar()
        bar.set_context_usage(100_000, 128_000)
        rendered = bar.__rich__()
        assert "%" in rendered.plain
