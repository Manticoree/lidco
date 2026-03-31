"""Tests for SuggestionEngine — Task 413."""

from __future__ import annotations

import pytest

pytest.importorskip("lidco.proactive.suggestions", reason="suggestions.py removed in Q157")
from lidco.proactive.suggestions import Suggestion, SuggestionEngine, _parse_suggestions


class TestSuggestion:

    def test_fields(self) -> None:
        s = Suggestion(text="Run tests", command_hint="/run pytest", confidence=0.9)
        assert s.text == "Run tests"
        assert s.command_hint == "/run pytest"
        assert s.confidence == 0.9

    def test_frozen(self) -> None:
        s = Suggestion(text="a", command_hint="", confidence=1.0)
        with pytest.raises((AttributeError, TypeError)):
            s.text = "b"  # type: ignore[misc]


class TestParseSuggestions:

    def test_three_suggestions(self) -> None:
        raw = (
            "1. Run the unit tests [hint: /run pytest]\n"
            "2. Review the diff before committing\n"
            "3. Update the documentation [hint: /docs]\n"
        )
        results = _parse_suggestions(raw)
        assert len(results) == 3
        assert results[0].text == "Run the unit tests"
        assert results[0].command_hint == "/run pytest"
        assert results[1].command_hint == ""
        assert results[2].command_hint == "/docs"

    def test_empty_input(self) -> None:
        results = _parse_suggestions("")
        assert results == []

    def test_no_numbered_lines(self) -> None:
        raw = "Just some text without numbers"
        results = _parse_suggestions(raw)
        assert results == []

    def test_confidence_descending(self) -> None:
        raw = "1. First action\n2. Second action\n3. Third action\n"
        results = _parse_suggestions(raw)
        assert len(results) == 3
        assert results[0].confidence >= results[1].confidence >= results[2].confidence

    def test_caps_at_three(self) -> None:
        raw = "1. A\n2. B\n3. C\n4. D\n5. E\n"
        results = _parse_suggestions(raw)
        assert len(results) == 3

    def test_hint_stripped_from_text(self) -> None:
        raw = "1. Do something useful [hint: /fix]\n"
        results = _parse_suggestions(raw)
        assert "[hint:" not in results[0].text


class TestSuggestionEngine:

    def test_no_session_returns_empty(self) -> None:
        import asyncio
        engine = SuggestionEngine(session=None)

        async def run():
            return await engine.suggest("Some response")

        result = asyncio.run(run())
        assert result == []

    def test_empty_response_returns_empty(self) -> None:
        import asyncio
        engine = SuggestionEngine(session=None)

        async def run():
            return await engine.suggest("")

        result = asyncio.run(run())
        assert result == []
