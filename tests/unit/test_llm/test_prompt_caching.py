"""Tests for Anthropic prompt prefix caching in LiteLLMProvider."""

from lidco.llm.litellm_provider import (
    _apply_prompt_caching,
    _is_anthropic_model,
    _maybe_apply_caching,
)


class TestIsAnthropicModel:
    def test_claude_prefix(self):
        assert _is_anthropic_model("claude-3-5-sonnet-20241022") is True

    def test_claude_haiku(self):
        assert _is_anthropic_model("claude-haiku-4-5-20251001") is True

    def test_anthropic_slash_prefix(self):
        assert _is_anthropic_model("anthropic/claude-opus-4") is True

    def test_bedrock_anthropic_prefix(self):
        assert _is_anthropic_model("bedrock/anthropic.claude-3-sonnet") is True

    def test_vertex_ai_claude_prefix(self):
        assert _is_anthropic_model("vertex_ai/claude-3-5-sonnet") is True

    def test_gpt_not_anthropic(self):
        assert _is_anthropic_model("gpt-4o-mini") is False

    def test_ollama_not_anthropic(self):
        assert _is_anthropic_model("ollama/llama3") is False

    def test_empty_string(self):
        assert _is_anthropic_model("") is False


class TestApplyPromptCaching:
    def _system_msg(self, text: str = "You are a helpful assistant.") -> dict:
        return {"role": "system", "content": text}

    def _user_msg(self, text: str = "Hello") -> dict:
        return {"role": "user", "content": text}

    def test_system_message_wrapped_in_array(self):
        messages = [self._system_msg(), self._user_msg()]
        result, _ = _apply_prompt_caching(messages)
        system = result[0]
        assert isinstance(system["content"], list)
        assert len(system["content"]) == 1
        assert system["content"][0]["type"] == "text"
        assert system["content"][0]["text"] == "You are a helpful assistant."

    def test_cache_control_ephemeral_set(self):
        messages = [self._system_msg(), self._user_msg()]
        result, _ = _apply_prompt_caching(messages)
        cache_ctrl = result[0]["content"][0]["cache_control"]
        assert cache_ctrl == {"type": "ephemeral"}

    def test_extra_body_contains_anthropic_beta(self):
        messages = [self._system_msg(), self._user_msg()]
        _, extra_body = _apply_prompt_caching(messages)
        assert "anthropic_beta" in extra_body
        assert "prompt-caching-2024-07-31" in extra_body["anthropic_beta"]

    def test_non_system_messages_unchanged(self):
        user = self._user_msg("Do something")
        messages = [self._system_msg(), user]
        result, _ = _apply_prompt_caching(messages)
        # User message should be unchanged
        assert result[1] == user

    def test_already_list_content_not_double_wrapped(self):
        """System message with content already as list should not be re-wrapped."""
        msg = {"role": "system", "content": [{"type": "text", "text": "existing"}]}
        messages = [msg, self._user_msg()]
        result, _ = _apply_prompt_caching(messages)
        # Non-string content passes through as-is
        assert result[0]["content"] == [{"type": "text", "text": "existing"}]

    def test_original_messages_not_mutated(self):
        original = self._system_msg("original")
        messages = [original, self._user_msg()]
        _apply_prompt_caching(messages)
        # Original dict should be unchanged
        assert original["content"] == "original"

    def test_no_system_message(self):
        messages = [self._user_msg("Hello"), self._user_msg("World")]
        result, extra_body = _apply_prompt_caching(messages)
        assert result == messages
        assert "anthropic_beta" in extra_body


class TestMaybeApplyCaching:
    def test_applies_for_claude_model(self):
        kwargs = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "system", "content": "You are helpful."}],
        }
        _maybe_apply_caching(kwargs)
        assert isinstance(kwargs["messages"][0]["content"], list)
        assert "anthropic_beta" in kwargs["extra_body"]

    def test_skips_for_non_anthropic_model(self):
        kwargs = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": "You are helpful."}],
        }
        _maybe_apply_caching(kwargs)
        # Content should remain a string
        assert isinstance(kwargs["messages"][0]["content"], str)
        assert "extra_body" not in kwargs

    def test_merges_existing_extra_body(self):
        kwargs = {
            "model": "claude-3-haiku-20240307",
            "messages": [{"role": "system", "content": "Prompt."}],
            "extra_body": {"custom_key": "value"},
        }
        _maybe_apply_caching(kwargs)
        assert kwargs["extra_body"]["custom_key"] == "value"
        assert "anthropic_beta" in kwargs["extra_body"]
