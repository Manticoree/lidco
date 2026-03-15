"""Tests for ConfidenceRouter — Task 318."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.ai.confidence_router import ConfidenceRouter, RoutingDecision, _DEFAULT_THRESHOLD


def _mock_session(response_json: dict) -> MagicMock:
    session = MagicMock()
    resp = MagicMock()
    resp.content = json.dumps(response_json)
    session.llm.complete = AsyncMock(return_value=resp)
    return session


# ---------------------------------------------------------------------------
# RoutingDecision
# ---------------------------------------------------------------------------

class TestRoutingDecision:
    def test_confident_above_threshold(self):
        d = RoutingDecision(agent="coder", confidence=0.9)
        assert d.confident is True

    def test_not_confident_below_threshold(self):
        d = RoutingDecision(agent="coder", confidence=0.3)
        assert d.confident is False

    def test_str_representation(self):
        d = RoutingDecision(agent="debugger", confidence=0.75)
        s = str(d)
        assert "debugger" in s
        assert "75" in s

    def test_custom_threshold(self):
        d = RoutingDecision(agent="coder", confidence=0.5, threshold=0.4)
        assert d.confident is True


# ---------------------------------------------------------------------------
# ConfidenceRouter.route()
# ---------------------------------------------------------------------------

class TestConfidenceRouterRoute:
    def test_routes_to_correct_agent(self):
        session = _mock_session({"agent": "debugger", "confidence": 0.9, "reasoning": "debug task"})
        router = ConfidenceRouter(session=session)
        result = asyncio.run(router.route("Fix the crash", candidates=["coder", "debugger"]))
        assert result.agent == "debugger"
        assert result.confidence == 0.9

    def test_low_confidence_sets_fallback(self):
        session = _mock_session({"agent": "coder", "confidence": 0.2, "reasoning": "unsure"})
        router = ConfidenceRouter(session=session, fallback_agent="architect")
        result = asyncio.run(router.route("Design something"))
        assert result.confident is False
        assert result.fallback_agent == "architect"

    def test_high_confidence_no_fallback(self):
        session = _mock_session({"agent": "coder", "confidence": 0.95, "reasoning": "clear"})
        router = ConfidenceRouter(session=session)
        result = asyncio.run(router.route("Write a function"))
        assert result.fallback_agent == ""

    def test_no_session_returns_fallback(self):
        router = ConfidenceRouter(session=None, fallback_agent="coder")
        result = asyncio.run(router.route("hello"))
        assert result.agent == "coder"
        assert result.confidence == 0.0

    def test_agent_not_in_candidates_fallback(self):
        session = _mock_session({"agent": "unknown_agent", "confidence": 0.9, "reasoning": "x"})
        router = ConfidenceRouter(session=session, fallback_agent="coder")
        result = asyncio.run(router.route("hi", candidates=["coder", "debugger"]))
        assert result.agent == "coder"

    def test_llm_error_returns_fallback(self):
        session = MagicMock()
        session.llm.complete = AsyncMock(side_effect=RuntimeError("API down"))
        router = ConfidenceRouter(session=session, fallback_agent="coder")
        result = asyncio.run(router.route("hi"))
        assert result.agent == "coder"
        assert result.confidence == 0.0

    def test_malformed_json_returns_fallback(self):
        session = MagicMock()
        resp = MagicMock()
        resp.content = "not json at all"
        session.llm.complete = AsyncMock(return_value=resp)
        router = ConfidenceRouter(session=session, fallback_agent="coder")
        result = asyncio.run(router.route("hi"))
        assert result.agent == "coder"


# ---------------------------------------------------------------------------
# ConfidenceRouter._parse_response
# ---------------------------------------------------------------------------

class TestConfidenceRouterParse:
    def test_parse_valid_json(self):
        router = ConfidenceRouter()
        agent, conf, reason = router._parse_response(
            '{"agent": "tester", "confidence": 0.7, "reasoning": "tests needed"}',
            candidates=["tester", "coder"],
        )
        assert agent == "tester"
        assert conf == 0.7

    def test_parse_clamps_confidence(self):
        router = ConfidenceRouter()
        agent, conf, _ = router._parse_response(
            '{"agent": "coder", "confidence": 1.5}',
            candidates=None,
        )
        assert conf <= 1.0

    def test_parse_json_embedded_in_text(self):
        router = ConfidenceRouter()
        raw = 'Sure! Here is my answer: {"agent": "coder", "confidence": 0.8, "reasoning": "writing code"}'
        agent, conf, _ = router._parse_response(raw, candidates=None)
        assert agent == "coder"
        assert conf == 0.8
