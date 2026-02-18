"""Tests for the clarification system."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from lidco.core.clarification import (
    ClarificationEntry,
    ClarificationManager,
    ClarificationNeeded,
)
from lidco.core.memory import MemoryStore


class TestClarificationNeeded:
    def test_is_exception(self):
        exc = ClarificationNeeded(
            question="Which auth method?",
            options=["JWT", "Session"],
            context="Need to decide auth strategy",
        )
        assert isinstance(exc, Exception)

    def test_frozen(self):
        exc = ClarificationNeeded(
            question="Which DB?", options=[], context=""
        )
        with pytest.raises(AttributeError):
            exc.question = "changed"

    def test_str_returns_question(self):
        exc = ClarificationNeeded(
            question="Which framework?", options=[], context=""
        )
        assert str(exc) == "Which framework?"

    def test_fields(self):
        exc = ClarificationNeeded(
            question="Q?",
            options=["A", "B"],
            context="ctx",
        )
        assert exc.question == "Q?"
        assert exc.options == ["A", "B"]
        assert exc.context == "ctx"


class TestClarificationEntry:
    def test_to_dict(self):
        entry = ClarificationEntry(
            question="Q?",
            answer="A",
            context="ctx",
            agent="coder",
            timestamp="2026-01-01T00:00:00",
        )
        d = entry.to_dict()
        assert d["question"] == "Q?"
        assert d["answer"] == "A"
        assert d["context"] == "ctx"
        assert d["agent"] == "coder"
        assert d["timestamp"] == "2026-01-01T00:00:00"

    def test_from_dict(self):
        entry = ClarificationEntry.from_dict({
            "question": "Q?",
            "answer": "A",
            "context": "ctx",
            "agent": "planner",
            "timestamp": "2026-01-01",
        })
        assert entry.question == "Q?"
        assert entry.answer == "A"
        assert entry.agent == "planner"

    def test_from_dict_defaults(self):
        entry = ClarificationEntry.from_dict({
            "question": "Q?",
            "answer": "A",
        })
        assert entry.context == ""
        assert entry.agent == ""
        assert entry.timestamp == ""

    def test_roundtrip(self):
        original = ClarificationEntry(
            question="Method?",
            answer="JWT",
            context="auth",
            agent="architect",
            timestamp="2026-02-01T12:00:00",
        )
        restored = ClarificationEntry.from_dict(original.to_dict())
        assert restored.question == original.question
        assert restored.answer == original.answer
        assert restored.context == original.context
        assert restored.agent == original.agent
        assert restored.timestamp == original.timestamp

    def test_frozen(self):
        entry = ClarificationEntry(
            question="Q?", answer="A", context="", agent="", timestamp=""
        )
        with pytest.raises(AttributeError):
            entry.question = "changed"


class TestClarificationManager:
    def test_save_and_find_decision(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)

        mgr.save_decision(
            question="Which auth method?",
            answer="JWT",
            context="auth implementation",
            agent="coder",
        )

        results = mgr.find_relevant("auth")
        assert len(results) >= 1
        assert results[0].answer == "JWT"

    def test_list_recent(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)

        mgr.save_decision(question="Q1?", answer="A1")
        mgr.save_decision(question="Q2?", answer="A2")

        recent = mgr.list_recent(10)
        assert len(recent) == 2

    def test_build_context_string_empty(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)
        assert mgr.build_context_string() == ""

    def test_build_context_string_with_decisions(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)

        mgr.save_decision(question="Framework?", answer="FastAPI")
        ctx = mgr.build_context_string()
        assert "Past Decisions" in ctx
        assert "Framework?" in ctx
        assert "FastAPI" in ctx

    def test_clear(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)

        mgr.save_decision(question="Q1?", answer="A1")
        mgr.save_decision(question="Q2?", answer="A2")

        count = mgr.clear()
        assert count == 2
        assert mgr.list_recent(10) == []

    def test_clear_empty(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)
        assert mgr.clear() == 0

    @pytest.mark.asyncio
    async def test_analyze_ambiguity_clear_request(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)

        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"clear": true}'
        mock_llm.complete.return_value = mock_response

        result = await mgr.analyze_ambiguity("fix the typo in README", mock_llm)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_ambiguity_with_questions(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)

        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = (
            '{"clear": false, "questions": ['
            '{"question": "Which auth method?", "options": ["JWT", "Session"], "context": "auth"}'
            ']}'
        )
        mock_llm.complete.return_value = mock_response

        result = await mgr.analyze_ambiguity("add authentication to the application with user management", mock_llm)
        assert result is not None
        assert len(result) == 1
        assert result[0].question == "Which auth method?"
        assert result[0].options == ["JWT", "Session"]

    @pytest.mark.asyncio
    async def test_analyze_ambiguity_parse_error(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)

        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "not valid json at all"
        mock_llm.complete.return_value = mock_response

        result = await mgr.analyze_ambiguity("something", mock_llm)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_ambiguity_llm_error(self, tmp_path):
        store = MemoryStore(global_dir=tmp_path / "memory", max_entries=100)
        mgr = ClarificationManager(store)

        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = RuntimeError("LLM unavailable")

        result = await mgr.analyze_ambiguity("something", mock_llm)
        assert result is None
