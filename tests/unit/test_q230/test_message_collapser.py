"""Tests for lidco.budget.message_collapser."""
from __future__ import annotations

import pytest

from lidco.budget.message_collapser import CollapseResult, MessageCollapser


class TestCollapseResult:
    def test_frozen(self) -> None:
        r = CollapseResult(original_count=3, collapsed_count=1)
        with pytest.raises(AttributeError):
            r.original_count = 5  # type: ignore[misc]

    def test_defaults(self) -> None:
        r = CollapseResult(original_count=0, collapsed_count=0)
        assert r.tokens_saved == 0
        assert r.merges == ()


class TestMessageCollapser:
    def test_empty_list(self) -> None:
        c = MessageCollapser()
        msgs, result = c.collapse([])
        assert msgs == []
        assert result.original_count == 0

    def test_single_message(self) -> None:
        c = MessageCollapser()
        msgs, result = c.collapse([{"role": "user", "content": "hi"}])
        assert len(msgs) == 1
        assert result.collapsed_count == 1

    def test_merge_adjacent_same_role(self) -> None:
        c = MessageCollapser()
        inp = [
            {"role": "assistant", "content": "Hello"},
            {"role": "assistant", "content": "World"},
        ]
        msgs, result = c.collapse(inp)
        assert len(msgs) == 1
        assert "Hello" in msgs[0]["content"]
        assert "World" in msgs[0]["content"]
        assert result.merges == ((0, 1),)

    def test_no_merge_different_roles(self) -> None:
        c = MessageCollapser()
        inp = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello"},
        ]
        msgs, result = c.collapse(inp)
        assert len(msgs) == 2
        assert result.merges == ()

    def test_system_messages_not_merged(self) -> None:
        c = MessageCollapser()
        inp = [
            {"role": "system", "content": "A"},
            {"role": "system", "content": "B"},
        ]
        msgs, result = c.collapse(inp)
        # System messages are not merged (role == "system" excluded)
        assert len(msgs) == 2

    def test_short_confirmations_dedup(self) -> None:
        c = MessageCollapser()
        inp = [
            {"role": "assistant", "content": "OK"},
            {"role": "assistant", "content": "Done"},
            {"role": "assistant", "content": "Sure"},
        ]
        msgs, result = c.collapse(inp)
        assert len(msgs) == 1
        assert msgs[0]["content"] == "OK"

    def test_are_similar(self) -> None:
        c = MessageCollapser(similarity_threshold=0.5)
        assert c._are_similar("hello world foo", "hello world bar") is True
        assert c._are_similar("alpha beta", "gamma delta") is False

    def test_are_similar_empty(self) -> None:
        c = MessageCollapser()
        assert c._are_similar("", "") is True

    def test_collapse_tool_results_single(self) -> None:
        c = MessageCollapser()
        inp = [{"role": "tool", "content": "file ok"}]
        result = c.collapse_tool_results(inp)
        assert len(result) == 1

    def test_collapse_tool_results_multiple(self) -> None:
        c = MessageCollapser()
        inp = [
            {"role": "tool", "content": "file1: OK"},
            {"role": "tool", "content": "file2: OK"},
            {"role": "tool", "content": "file3: OK"},
        ]
        result = c.collapse_tool_results(inp)
        assert len(result) == 1
        assert "3 tool results" in result[0]["content"]

    def test_collapse_tool_results_mixed(self) -> None:
        c = MessageCollapser()
        inp = [
            {"role": "user", "content": "run"},
            {"role": "tool", "content": "r1"},
            {"role": "tool", "content": "r2"},
            {"role": "assistant", "content": "done"},
        ]
        result = c.collapse_tool_results(inp)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "tool"
        assert "2 tool results" in result[1]["content"]

    def test_estimate_tokens(self) -> None:
        c = MessageCollapser()
        assert c.estimate_tokens("abcd") == 1
        assert c.estimate_tokens("") == 0

    def test_summary(self) -> None:
        c = MessageCollapser()
        r = CollapseResult(original_count=5, collapsed_count=3, tokens_saved=10, merges=((0, 1),))
        s = c.summary(r)
        assert "5" in s
        assert "3" in s
        assert "10" in s
