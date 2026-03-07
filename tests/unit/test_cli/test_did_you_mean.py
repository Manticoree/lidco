"""Tests for 'did you mean?' fuzzy command suggestion — Task 163."""

from __future__ import annotations

from lidco.cli.app import _levenshtein, _find_similar_command
from lidco.cli.commands import CommandRegistry


# ── _levenshtein ──────────────────────────────────────────────────────────────

class TestLevenshtein:
    def test_identical(self):
        assert _levenshtein("abc", "abc") == 0

    def test_single_insert(self):
        assert _levenshtein("clear", "cler") == 1

    def test_single_delete(self):
        assert _levenshtein("cler", "clear") == 1

    def test_single_substitute(self):
        assert _levenshtein("clear", "clEar") == 1

    def test_empty_a(self):
        assert _levenshtein("", "abc") == 3

    def test_empty_b(self):
        assert _levenshtein("abc", "") == 3

    def test_both_empty(self):
        assert _levenshtein("", "") == 0

    def test_completely_different(self):
        d = _levenshtein("abc", "xyz")
        assert d == 3


# ── _find_similar_command ─────────────────────────────────────────────────────

class TestFindSimilarCommand:
    def _commands(self):
        return CommandRegistry().list_commands()

    def test_clear_typo(self):
        result = _find_similar_command("cler", self._commands())
        assert result == "clear"

    def test_exit_typo(self):
        result = _find_similar_command("exot", self._commands())
        assert result == "export" or result == "exit"

    def test_exact_match_distance_zero(self):
        result = _find_similar_command("clear", self._commands())
        assert result == "clear"

    def test_completely_wrong_returns_none(self):
        result = _find_similar_command("zzzzzzz", self._commands())
        assert result is None

    def test_status_typo(self):
        result = _find_similar_command("staus", self._commands())
        assert result == "status"

    def test_debug_typo(self):
        result = _find_similar_command("debuf", self._commands())
        assert result == "debug"

    def test_help_typo(self):
        result = _find_similar_command("hlep", self._commands())
        assert result == "help"

    def test_returns_string_or_none(self):
        result = _find_similar_command("xyz123", self._commands())
        assert result is None or isinstance(result, str)
