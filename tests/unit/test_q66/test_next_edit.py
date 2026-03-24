"""Tests for NextEditPredictor — T450."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.prediction.next_edit import (
    EditEvent,
    EditSuggestion,
    NextEditPredictor,
    _build_prompt,
    _parse_response,
)


def make_edit(file="a.py", line=10, old="foo", new="bar") -> EditEvent:
    return EditEvent(file=file, line=line, old=old, new=new)


class TestNextEditPredictor:
    def test_starts_disabled(self):
        p = NextEditPredictor()
        assert not p.enabled

    def test_enable(self):
        p = NextEditPredictor()
        p.enable()
        assert p.enabled

    def test_disable(self):
        p = NextEditPredictor()
        p.enable()
        p.disable()
        assert not p.enabled

    def test_toggle_on(self):
        p = NextEditPredictor()
        result = p.toggle()
        assert result is True

    def test_toggle_off(self):
        p = NextEditPredictor()
        p.enable()
        result = p.toggle()
        assert result is False

    def test_predict_disabled_returns_none(self):
        async def fake_llm(prompt, max_tokens, temperature):
            return '{"file": "x.py", "line": 5, "old": "a", "new": "b"}'

        p = NextEditPredictor(llm_fn=fake_llm)
        # Not enabled
        result = asyncio.run(p.predict([make_edit()]))
        assert result is None

    def test_predict_no_llm_returns_none(self):
        p = NextEditPredictor(llm_fn=None)
        p.enable()
        result = asyncio.run(p.predict([make_edit()]))
        assert result is None

    def test_predict_returns_suggestion(self):
        async def fake_llm(prompt, max_tokens, temperature):
            return '{"file": "b.py", "line": 15, "old": "old_text", "new": "new_text"}'

        p = NextEditPredictor(llm_fn=fake_llm)
        p.enable()
        suggestion = asyncio.run(p.predict([make_edit()]))
        assert suggestion is not None
        assert suggestion.file == "b.py"
        assert suggestion.line == 15

    def test_predict_caches_result(self):
        call_count = {"n": 0}

        async def fake_llm(prompt, max_tokens, temperature):
            call_count["n"] += 1
            return '{"file": "x.py", "line": 1, "old": "", "new": "x"}'

        p = NextEditPredictor(llm_fn=fake_llm)
        p.enable()
        edits = [make_edit()]
        asyncio.run(p.predict(edits))
        asyncio.run(p.predict(edits))  # same edits
        assert call_count["n"] == 1

    def test_clear_cache(self):
        call_count = {"n": 0}

        async def fake_llm(prompt, max_tokens, temperature):
            call_count["n"] += 1
            return '{"file": "x.py", "line": 1, "old": "", "new": "x"}'

        p = NextEditPredictor(llm_fn=fake_llm)
        p.enable()
        edits = [make_edit()]
        asyncio.run(p.predict(edits))
        p.clear_cache()
        asyncio.run(p.predict(edits))
        assert call_count["n"] == 2

    def test_predict_timeout_returns_none(self):
        async def slow_llm(prompt, max_tokens, temperature):
            await asyncio.sleep(100)
            return "{}"

        p = NextEditPredictor(llm_fn=slow_llm)
        p.enable()
        # Reduce timeout for test
        p.TIMEOUT = 0.01
        result = asyncio.run(p.predict([make_edit()]))
        assert result is None

    def test_predict_llm_exception_returns_none(self):
        async def bad_llm(prompt, max_tokens, temperature):
            raise RuntimeError("LLM down")

        p = NextEditPredictor(llm_fn=bad_llm)
        p.enable()
        result = asyncio.run(p.predict([make_edit()]))
        assert result is None


class TestParseResponse:
    def test_valid_json(self):
        s = _parse_response('{"file": "x.py", "line": 5, "old": "a", "new": "b"}')
        assert s is not None
        assert s.file == "x.py"
        assert s.line == 5

    def test_json_embedded_in_text(self):
        s = _parse_response('Here is the prediction: {"file": "y.py", "line": 3, "old": "x", "new": "y"} done.')
        assert s is not None
        assert s.file == "y.py"

    def test_invalid_json(self):
        assert _parse_response("not json") is None

    def test_missing_keys(self):
        assert _parse_response('{"file": "x.py"}') is None

    def test_empty_string(self):
        assert _parse_response("") is None


class TestBuildPrompt:
    def test_contains_edit_info(self):
        edits = [make_edit(file="foo.py", line=10, old="old", new="new")]
        prompt = _build_prompt(edits, "some context")
        assert "foo.py" in prompt
        assert "old" in prompt
        assert "new" in prompt

    def test_contains_json_instruction(self):
        prompt = _build_prompt([], "")
        assert "JSON" in prompt or "json" in prompt


class TestEditSuggestion:
    def test_display(self):
        s = EditSuggestion(file="a.py", line=5, old="x", new="y")
        assert "a.py:5" in s.display()
        assert "Tab" in s.display()

    def test_confidence_default(self):
        s = EditSuggestion(file="a.py", line=1, old="", new="")
        assert s.confidence == 1.0
