"""Tests for BrainstormAgent — T500."""
from __future__ import annotations
import json
import pytest
from lidco.agents.brainstorm import BrainstormAgent, BrainstormResult, _parse_response


class TestBrainstormAgent:
    def test_no_llm_returns_default(self):
        agent = BrainstormAgent()
        result = agent.brainstorm("implement login")
        assert isinstance(result, BrainstormResult)
        assert len(result.alternatives) >= 1
        assert result.recommended_approach

    def test_llm_fn_used(self):
        response = json.dumps({
            "alternatives": ["option A", "option B"],
            "risks": ["scope creep"],
            "clarifying_questions": ["What auth method?"],
            "recommended_approach": "use JWT",
        })
        agent = BrainstormAgent(llm_fn=lambda p: response)
        result = agent.brainstorm("implement auth")
        assert "option A" in result.alternatives
        assert result.recommended_approach == "use JWT"

    def test_llm_exception_falls_back(self):
        def raising_llm(p):
            raise RuntimeError("down")
        agent = BrainstormAgent(llm_fn=raising_llm)
        result = agent.brainstorm("goal")
        assert isinstance(result, BrainstormResult)

    def test_result_has_all_fields(self):
        agent = BrainstormAgent()
        r = agent.brainstorm("fix bug")
        assert hasattr(r, "alternatives")
        assert hasattr(r, "risks")
        assert hasattr(r, "clarifying_questions")
        assert hasattr(r, "recommended_approach")

    def test_parse_response_valid(self):
        raw = json.dumps({"alternatives": ["a"], "risks": ["r"], "clarifying_questions": ["q"], "recommended_approach": "use a"})
        result = _parse_response(raw, "fallback")
        assert result.alternatives == ["a"]

    def test_parse_response_invalid_json(self):
        result = _parse_response("not json", "fallback")
        assert result.alternatives == ["fallback"]

    def test_context_passed_to_llm(self):
        received = {}
        def llm_fn(prompt):
            received["prompt"] = prompt
            return json.dumps({"alternatives": [], "risks": [], "clarifying_questions": [], "recommended_approach": "x"})
        agent = BrainstormAgent(llm_fn=llm_fn)
        agent.brainstorm("goal", context="important context here")
        assert "important context here" in received["prompt"]
