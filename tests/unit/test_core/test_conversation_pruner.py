"""Tests for conversation pruning."""

import pytest
from unittest.mock import AsyncMock

from lidco.core.conversation_pruner import (
    _has_existing_summary,
    _needs_summarization,
    _summarize_tool_message,
    _trim_assistant_message,
    compress_tool_results,
    prune_conversation,
    summarize_conversation_if_needed,
)
from lidco.llm.base import LLMResponse, Message


def _make_exchange(step: int, tool_content: str = "") -> list[Message]:
    """Create an assistant + tool message pair."""
    content = tool_content or f"Tool output for step {step}\n" * 50
    return [
        Message(
            role="assistant",
            content=f"I will do step {step}.",
            tool_calls=[{"id": f"call_{step}", "type": "function", "function": {"name": "file_read", "arguments": "{}"}}],
        ),
        Message(
            role="tool",
            content=content,
            tool_call_id=f"call_{step}",
            name="file_read",
        ),
    ]


class TestPruneConversation:
    """Tests for the main prune_conversation function."""

    def test_empty_messages(self):
        assert prune_conversation([]) == []

    def test_small_conversation_unchanged(self):
        messages = [
            Message(role="system", content="System prompt"),
            Message(role="user", content="Do something"),
            Message(role="assistant", content="Done!"),
        ]
        result = prune_conversation(messages, max_chars=100_000)
        assert len(result) == 3
        assert result[0].content == "System prompt"
        assert result[2].content == "Done!"

    def test_large_conversation_prunes_old_tool_results(self):
        messages = [
            Message(role="system", content="System prompt"),
            Message(role="user", content="Read files"),
        ]
        # Add 10 exchanges with large tool outputs
        for i in range(10):
            messages.extend(_make_exchange(i, "x" * 5000))

        result = prune_conversation(messages, max_chars=20_000, keep_recent_exchanges=3)

        # System and user kept
        assert result[0].content == "System prompt"
        assert result[1].content == "Read files"

        # Old tool messages should be summarized (short)
        old_tool_msgs = [m for m in result if m.role == "tool" and "[file_read:" in m.content]
        assert len(old_tool_msgs) > 0

        # Recent exchanges should be full
        recent_tools = [m for m in result if m.role == "tool" and len(m.content) > 1000]
        assert len(recent_tools) >= 3

    def test_system_prompt_always_preserved(self):
        messages = [
            Message(role="system", content="S" * 50_000),
            Message(role="user", content="Go"),
        ]
        messages.extend(_make_exchange(0, "x" * 50_000))

        result = prune_conversation(messages, max_chars=10_000)
        assert result[0].content == "S" * 50_000


class TestSummarizeToolMessage:
    """Tests for tool message summarization."""

    def test_summary_contains_tool_name(self):
        msg = Message(role="tool", content="line1\nline2\nline3", name="grep")
        result = _summarize_tool_message(msg)
        assert "grep" in result.content

    def test_summary_contains_line_count(self):
        msg = Message(role="tool", content="a\nb\nc\nd", name="file_read")
        result = _summarize_tool_message(msg)
        assert "4 lines" in result.content

    def test_preserves_tool_call_id(self):
        msg = Message(role="tool", content="data", tool_call_id="call_42", name="bash")
        result = _summarize_tool_message(msg)
        assert result.tool_call_id == "call_42"


class TestTrimAssistantMessage:
    """Tests for assistant message trimming."""

    def test_short_message_unchanged(self):
        msg = Message(role="assistant", content="short")
        result = _trim_assistant_message(msg)
        assert result.content == "short"

    def test_long_message_trimmed(self):
        msg = Message(role="assistant", content="a" * 500)
        result = _trim_assistant_message(msg, max_chars=200)
        assert len(result.content) < 250
        assert "trimmed" in result.content

    def test_tool_calls_preserved_on_trim(self):
        calls = [{"id": "c1", "type": "function", "function": {"name": "bash", "arguments": "{}"}}]
        msg = Message(role="assistant", content="a" * 500, tool_calls=calls)
        result = _trim_assistant_message(msg, max_chars=200)
        assert result.tool_calls == calls


# ── Conversation Summarizer ──────────────────────────────────────────────────

def _make_long_conversation(n_exchanges: int = 12) -> list[Message]:
    """Build a conversation with n_exchanges assistant+tool pairs."""
    msgs = [
        Message(role="system", content="You are a coder."),
        Message(role="user", content="Build a feature."),
    ]
    for i in range(n_exchanges):
        msgs.append(Message(role="assistant", content=f"Calling tool {i}."))
        msgs.append(Message(role="tool", content=f"Tool output {i}", name="file_read"))
    return msgs


class TestCompressToolResults:
    """Tests for compress_tool_results() — tool result compression."""

    def _tool_msg(self, content: str, name: str = "file_read", tool_id: str = "c1") -> Message:
        return Message(role="tool", content=content, tool_call_id=tool_id, name=name)

    def test_empty_returns_empty(self):
        assert compress_tool_results([]) == []

    def test_no_tool_messages_unchanged(self):
        msgs = [
            Message(role="system", content="sys"),
            Message(role="user", content="go"),
        ]
        assert compress_tool_results(msgs) == msgs

    def test_small_results_unchanged(self):
        msgs = [
            Message(role="system", content="sys"),
            self._tool_msg("short content", tool_id="c1"),
        ]
        result = compress_tool_results(msgs, max_chars=2000)
        assert result[1].content == "short content"

    def test_returns_new_list(self):
        msgs = [self._tool_msg("x" * 3000, tool_id="c1")]
        result = compress_tool_results(msgs)
        assert result is not msgs

    def test_large_recent_result_truncated(self):
        large = "x" * 5000
        msgs = [self._tool_msg(large, tool_id="c1")]
        result = compress_tool_results(msgs, max_chars=2000, keep_recent=3)
        assert len(result[0].content) < len(large)
        assert "truncated" in result[0].content

    def test_truncation_marker_shows_remaining_chars(self):
        large = "a" * 4000
        msgs = [self._tool_msg(large, tool_id="c1")]
        result = compress_tool_results(msgs, max_chars=2000, keep_recent=3)
        assert "2000 chars truncated" in result[0].content

    def test_old_results_summarized(self):
        msgs = [
            self._tool_msg("x" * 3000, tool_id="c1"),
            self._tool_msg("y" * 3000, tool_id="c2"),
            self._tool_msg("z" * 3000, tool_id="c3"),
            self._tool_msg("w" * 3000, tool_id="c4"),
        ]
        # With keep_recent=2, first two should be summarized
        result = compress_tool_results(msgs, max_chars=2000, keep_recent=2)
        # c1 and c2 are old → summarized to short content
        assert "[file_read:" in result[0].content
        assert "[file_read:" in result[1].content
        assert len(result[0].content) < 200

    def test_recent_results_kept(self):
        msgs = [
            self._tool_msg("x" * 3000, tool_id="c1"),
            self._tool_msg("y" * 1000, tool_id="c2"),
            self._tool_msg("z" * 1000, tool_id="c3"),
        ]
        result = compress_tool_results(msgs, max_chars=2000, keep_recent=2)
        # c2 and c3 (last 2) should be kept
        assert result[1].content == "y" * 1000
        assert result[2].content == "z" * 1000

    def test_preserves_tool_call_id(self):
        msgs = [self._tool_msg("x" * 5000, tool_id="call_xyz")]
        result = compress_tool_results(msgs, max_chars=2000, keep_recent=3)
        assert result[0].tool_call_id == "call_xyz"

    def test_non_tool_messages_untouched(self):
        msgs = [
            Message(role="system", content="sys"),
            Message(role="user", content="go"),
            self._tool_msg("x" * 5000, tool_id="c1"),
            Message(role="assistant", content="done"),
        ]
        result = compress_tool_results(msgs, max_chars=2000)
        assert result[0].content == "sys"
        assert result[1].content == "go"
        assert result[3].content == "done"

    def test_all_small_no_compression_needed(self):
        msgs = [
            self._tool_msg("small" * 3, tool_id=f"c{i}")
            for i in range(5)
        ]
        result = compress_tool_results(msgs, max_chars=2000)
        # All small, no compression needed — returns a list but content unchanged
        for i, (orig, res) in enumerate(zip(msgs, result)):
            assert orig.content == res.content


class TestNeedsSummarization:
    def test_short_conversation_false(self):
        msgs = _make_long_conversation(3)  # 8 messages
        assert _needs_summarization(msgs, threshold=20) is False

    def test_long_conversation_true(self):
        msgs = _make_long_conversation(11)  # 24 messages
        assert _needs_summarization(msgs, threshold=20) is True

    def test_exactly_at_threshold_false(self):
        msgs = _make_long_conversation(9)  # 20 messages
        assert _needs_summarization(msgs, threshold=20) is False


class TestSummarizeConversationIfNeeded:
    def _make_llm_mock(self, summary: str = "Summary of earlier work.") -> AsyncMock:
        mock = AsyncMock()
        mock.complete.return_value = LLMResponse(
            content=summary, model="openai/glm-4.7"
        )
        return mock

    @pytest.mark.asyncio
    async def test_short_conversation_unchanged(self):
        msgs = _make_long_conversation(3)
        llm = self._make_llm_mock()
        result = await summarize_conversation_if_needed(msgs, llm, threshold=20)
        assert result == msgs
        llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_long_conversation_triggers_summarization(self):
        msgs = _make_long_conversation(11)  # 24 messages
        llm = self._make_llm_mock("Fixed auth bug, created Session class.")
        result = await summarize_conversation_if_needed(msgs, llm, threshold=20, keep_recent=6)

        # LLM was called once for summarization
        llm.complete.assert_called_once()

        # Result is shorter than original
        assert len(result) < len(msgs)

    @pytest.mark.asyncio
    async def test_system_and_first_user_preserved(self):
        msgs = _make_long_conversation(11)
        llm = self._make_llm_mock()
        result = await summarize_conversation_if_needed(msgs, llm, threshold=20, keep_recent=6)

        assert result[0].role == "system"
        assert result[0].content == "You are a coder."
        assert result[1].role == "user"
        assert result[1].content == "Build a feature."

    @pytest.mark.asyncio
    async def test_summary_message_injected(self):
        msgs = _make_long_conversation(11)
        llm = self._make_llm_mock("Earlier: created auth module.")
        result = await summarize_conversation_if_needed(msgs, llm, threshold=20, keep_recent=6)

        summary_msgs = [m for m in result if "Earlier Conversation Summary" in m.content]
        assert len(summary_msgs) == 1
        assert "Earlier: created auth module." in summary_msgs[0].content
        # Summary is injected as assistant role (avoids second system message)
        assert summary_msgs[0].role == "assistant"

    @pytest.mark.asyncio
    async def test_already_summarized_skips_second_call(self):
        msgs = _make_long_conversation(11)
        # Pre-inject a summary to simulate already-summarized state
        msgs.insert(2, Message(role="assistant", content="## Earlier Conversation Summary\nPrevious work."))
        llm = self._make_llm_mock()
        result = await summarize_conversation_if_needed(msgs, llm, threshold=20, keep_recent=6)

        llm.complete.assert_not_called()
        assert result == msgs

    @pytest.mark.asyncio
    async def test_too_few_turns_to_summarize_skips(self):
        msgs = _make_long_conversation(11)  # 24 total
        # With keep_recent=20, to_summarize = msgs[2:4] = only 2 messages
        llm = self._make_llm_mock()
        result = await summarize_conversation_if_needed(
            msgs, llm, threshold=20, keep_recent=20, min_turns=4
        )
        llm.complete.assert_not_called()
        assert result == msgs

    @pytest.mark.asyncio
    async def test_recent_turns_preserved_verbatim(self):
        msgs = _make_long_conversation(11)
        keep_recent = 6
        llm = self._make_llm_mock()
        result = await summarize_conversation_if_needed(
            msgs, llm, threshold=20, keep_recent=keep_recent
        )
        # The last keep_recent messages of the original should appear at the tail
        tail_original = msgs[-keep_recent:]
        tail_result = result[-keep_recent:]
        assert tail_original == tail_result

    @pytest.mark.asyncio
    async def test_llm_failure_returns_original(self):
        msgs = _make_long_conversation(11)
        llm = AsyncMock()
        llm.complete.side_effect = RuntimeError("LLM unavailable")
        result = await summarize_conversation_if_needed(msgs, llm, threshold=20)

        # On failure, original is returned unchanged
        assert result == msgs
