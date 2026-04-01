"""Tests for lidco.pairing.suggestion_stream."""

from __future__ import annotations

import unittest

from lidco.pairing.suggestion_stream import (
    CodeSuggestion,
    SuggestionStream,
    SuggestionType,
)


class TestSuggestionType(unittest.TestCase):
    def test_enum_values(self) -> None:
        assert SuggestionType.INSERT == "insert"
        assert SuggestionType.REPLACE == "replace"
        assert SuggestionType.DELETE == "delete"
        assert SuggestionType.COMPLETE == "complete"


class TestCodeSuggestion(unittest.TestCase):
    def test_frozen(self) -> None:
        s = CodeSuggestion(type=SuggestionType.INSERT, content="pass")
        with self.assertRaises(AttributeError):
            s.content = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        s = CodeSuggestion(type=SuggestionType.DELETE, content="x")
        assert s.file == ""
        assert s.line == 0
        assert s.confidence == 0.5
        assert s.explanation == ""


class TestSuggestionStream(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = SuggestionStream(debounce_ms=0.0)

    def test_add_context_and_generate(self) -> None:
        self.stream.add_context("test.py", "def foo():\n    pass", cursor_line=0)
        result = self.stream.generate()
        assert isinstance(result, list)
        # Should produce at least one suggestion (colon at end of line)
        assert len(result) >= 1

    def test_generate_with_prompt(self) -> None:
        self.stream.add_context("test.py", "x = 1", cursor_line=0)
        result = self.stream.generate(prompt="add logging")
        assert any(s.type == SuggestionType.COMPLETE for s in result)

    def test_accept(self) -> None:
        self.stream.add_context("test.py", "def bar():\n    pass", cursor_line=0)
        self.stream.generate()
        pending_before = len(self.stream.pending())
        accepted = self.stream.accept(0)
        assert accepted is not None
        assert isinstance(accepted, CodeSuggestion)
        assert len(self.stream.pending()) == pending_before - 1

    def test_accept_invalid_index(self) -> None:
        assert self.stream.accept(99) is None

    def test_reject(self) -> None:
        self.stream.add_context("test.py", "def baz():\n    pass", cursor_line=0)
        self.stream.generate()
        count = len(self.stream.pending())
        assert self.stream.reject(0) is True
        assert len(self.stream.pending()) == count - 1

    def test_reject_invalid_index(self) -> None:
        assert self.stream.reject(99) is False

    def test_pending_returns_copy(self) -> None:
        self.stream.add_context("a.py", "x = 1\n# TODO: fix", cursor_line=0)
        self.stream.generate()
        p1 = self.stream.pending()
        p2 = self.stream.pending()
        assert p1 == p2
        assert p1 is not p2

    def test_clear(self) -> None:
        self.stream.add_context("a.py", "code", cursor_line=0)
        self.stream.generate()
        self.stream.clear()
        assert self.stream.pending() == []

    def test_history_tracks_accepted(self) -> None:
        self.stream.add_context("a.py", "def f():\n    pass", cursor_line=0)
        self.stream.generate()
        self.stream.accept(0)
        history = self.stream.history()
        assert len(history) == 1
        assert isinstance(history[0], CodeSuggestion)


if __name__ == "__main__":
    unittest.main()
