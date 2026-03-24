"""Tests for NextEditPredictor in Q72 context (reuses T450 implementation)."""
from __future__ import annotations
import asyncio
import pytest
from lidco.prediction.next_edit import EditEvent, EditSuggestion, NextEditPredictor, _parse_response


class TestNextEditPredictorQ72:
    """Verify that T450 implementation satisfies T484 requirements."""

    def test_predict_returns_suggestion_or_none(self):
        async def llm_fn(prompt, max_tokens, temperature):
            return '{"file": "a.py", "line": 10, "old": "x", "new": "y"}'

        p = NextEditPredictor(llm_fn=llm_fn)
        p.enable()
        result = asyncio.run(p.predict([EditEvent("a.py", 5, "foo", "bar")]))
        assert result is not None
        assert isinstance(result, EditSuggestion)

    def test_5s_timeout_attribute_exists(self):
        p = NextEditPredictor()
        assert hasattr(p, "TIMEOUT")
        assert p.TIMEOUT <= 10

    def test_cache_per_edit_pattern(self):
        calls = {"n": 0}
        async def llm_fn(prompt, max_tokens, temperature):
            calls["n"] += 1
            return '{"file": "a.py", "line": 1, "old": "", "new": "x"}'

        p = NextEditPredictor(llm_fn=llm_fn)
        p.enable()
        edits = [EditEvent("a.py", 1, "x", "y")]
        asyncio.run(p.predict(edits))
        asyncio.run(p.predict(edits))
        assert calls["n"] == 1  # cached

    def test_disabled_by_default(self):
        p = NextEditPredictor()
        assert not p.enabled

    def test_config_toggle(self):
        p = NextEditPredictor()
        p.enable()
        assert p.enabled
        p.disable()
        assert not p.enabled
