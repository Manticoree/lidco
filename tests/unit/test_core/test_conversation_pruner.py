"""Tests for conversation pruning."""

from lidco.core.conversation_pruner import (
    _summarize_tool_message,
    _trim_assistant_message,
    prune_conversation,
)
from lidco.llm.base import Message


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
