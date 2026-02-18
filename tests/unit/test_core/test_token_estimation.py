"""Tests for token estimation module."""

from lidco.core.token_estimation import (
    estimate_conversation_tokens,
    estimate_message_tokens,
    estimate_tokens,
)
from lidco.llm.base import Message


class TestEstimateTokens:
    """Tests for the basic text token estimator."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_text(self):
        # "hello" = 5 chars -> 5//4 = 1
        assert estimate_tokens("hello") >= 1

    def test_longer_text(self):
        text = "a" * 400
        result = estimate_tokens(text)
        assert result == 100

    def test_minimum_one_token(self):
        assert estimate_tokens("hi") >= 1


class TestEstimateMessageTokens:
    """Tests for message-level estimation."""

    def test_simple_user_message(self):
        msg = Message(role="user", content="Hello, world!")
        tokens = estimate_message_tokens(msg)
        # 4 overhead + content tokens
        assert tokens > 4

    def test_tool_message_with_name(self):
        msg = Message(
            role="tool",
            content="file contents here",
            tool_call_id="call_123",
            name="file_read",
        )
        tokens = estimate_message_tokens(msg)
        assert tokens > 4

    def test_assistant_with_tool_calls(self):
        msg = Message(
            role="assistant",
            content="Let me read that file.",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "file_read", "arguments": '{"path": "foo.py"}'},
                }
            ],
        )
        tokens = estimate_message_tokens(msg)
        # Should include tool_calls JSON overhead
        assert tokens > 10


class TestEstimateConversationTokens:
    """Tests for full conversation estimation."""

    def test_empty_conversation(self):
        assert estimate_conversation_tokens([]) == 0

    def test_multi_message_conversation(self):
        messages = [
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Read foo.py"),
            Message(role="assistant", content="Sure, reading it now."),
            Message(role="tool", content="x" * 1000, name="file_read"),
        ]
        total = estimate_conversation_tokens(messages)
        # The tool result alone is ~250 tokens + overhead
        assert total > 250
        assert total < 500
