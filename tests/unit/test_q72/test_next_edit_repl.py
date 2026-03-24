"""Tests for NextEditDisplay — T486."""
from __future__ import annotations
import asyncio
import pytest
from lidco.prediction.next_edit import EditEvent, EditSuggestion, NextEditPredictor
from lidco.prediction.repl_display import DisplayConfig, NextEditDisplay


def make_predictor(response_json: str | None = None) -> NextEditPredictor:
    if response_json is None:
        return NextEditPredictor(llm_fn=None)

    async def llm_fn(prompt, max_tokens, temperature):
        return response_json

    p = NextEditPredictor(llm_fn=llm_fn)
    return p


class TestNextEditDisplay:
    def test_disabled_by_default(self):
        p = make_predictor()
        display = NextEditDisplay(p)
        assert not display.config.enabled

    def test_enable(self):
        p = make_predictor()
        display = NextEditDisplay(p)
        display.enable()
        assert display.config.enabled
        assert p.enabled

    def test_disable(self):
        p = make_predictor()
        display = NextEditDisplay(p)
        display.enable()
        display.disable()
        assert not display.config.enabled

    def test_after_edit_disabled_returns_none(self):
        p = make_predictor()
        display = NextEditDisplay(p)
        result = asyncio.run(display.after_edit([EditEvent("a.py", 1, "x", "y")]))
        assert result is None

    def test_after_edit_returns_suggestion(self):
        p = make_predictor('{"file": "b.py", "line": 5, "old": "a", "new": "b"}')
        display = NextEditDisplay(p)
        display.enable()
        result = asyncio.run(display.after_edit([EditEvent("a.py", 1, "x", "y")]))
        assert result is not None
        assert result.file == "b.py"

    def test_format_suggestion(self):
        p = make_predictor()
        display = NextEditDisplay(p)
        s = EditSuggestion(file="x.py", line=10, old="a", new="b")
        formatted = display.format_suggestion(s)
        assert "x.py:10" in formatted
        assert "Tab" in formatted

    def test_accept_clears_pending(self):
        p = make_predictor('{"file": "c.py", "line": 3, "old": "x", "new": "y"}')
        display = NextEditDisplay(p)
        display.enable()
        asyncio.run(display.after_edit([EditEvent("a.py", 1, "x", "y")]))
        s = display.accept()
        assert s is not None
        assert not display.has_pending

    def test_dismiss_clears_pending(self):
        p = make_predictor('{"file": "c.py", "line": 3, "old": "x", "new": "y"}')
        display = NextEditDisplay(p)
        display.enable()
        asyncio.run(display.after_edit([EditEvent("a.py", 1, "x", "y")]))
        display.dismiss()
        assert not display.has_pending

    def test_no_pending_by_default(self):
        p = make_predictor()
        display = NextEditDisplay(p)
        assert not display.has_pending
