"""Tests for lidco.conversation.normalizer — MessageNormalizer."""
from __future__ import annotations

import unittest

from lidco.conversation.normalizer import MessageNormalizer
from lidco.conversation.schema_registry import SchemaRegistry


class TestNormalizerBasics(unittest.TestCase):
    def setUp(self):
        self.n = MessageNormalizer()

    def test_default_target_provider(self):
        self.assertEqual(self.n.target_provider, "openai")

    def test_set_target_provider(self):
        self.n.set_target_provider("anthropic")
        self.assertEqual(self.n.target_provider, "anthropic")

    def test_string_content_to_blocks(self):
        msg = {"role": "user", "content": "hello"}
        result = self.n.normalize(msg)
        self.assertEqual(result["content"], [{"type": "text", "text": "hello"}])

    def test_list_content_preserved(self):
        blocks = [{"type": "text", "text": "hi"}]
        msg = {"role": "user", "content": blocks}
        result = self.n.normalize(msg)
        self.assertEqual(result["content"][0]["type"], "text")

    def test_none_content_preserved(self):
        msg = {"role": "assistant", "content": None}
        result = self.n.normalize(msg)
        self.assertIsNone(result["content"])

    def test_missing_role_defaults_to_user(self):
        msg = {"content": "hi"}
        result = self.n.normalize(msg)
        self.assertEqual(result["role"], "user")

    def test_immutable_input(self):
        msg = {"role": "user", "content": "hello"}
        original = dict(msg)
        self.n.normalize(msg)
        self.assertEqual(msg, original)

    def test_returns_new_dict(self):
        msg = {"role": "user", "content": "hello"}
        result = self.n.normalize(msg)
        self.assertIsNot(result, msg)


class TestNormalizerFieldStripping(unittest.TestCase):
    def setUp(self):
        self.n = MessageNormalizer()

    def test_tool_call_id_kept(self):
        msg = {"role": "tool", "content": "ok", "tool_call_id": "t1"}
        result = self.n.normalize(msg)
        self.assertEqual(result["tool_call_id"], "t1")

    def test_tool_calls_kept(self):
        msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]}
        result = self.n.normalize(msg)
        self.assertIn("tool_calls", result)

    def test_unknown_fields_stripped(self):
        msg = {"role": "user", "content": "hi", "custom_field": "x"}
        result = self.n.normalize(msg)
        self.assertNotIn("custom_field", result)


class TestNormalizeBatch(unittest.TestCase):
    def test_batch(self):
        n = MessageNormalizer()
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        results = n.normalize_batch(msgs)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["role"], "user")
        self.assertEqual(results[1]["role"], "assistant")


class TestNormalizerWithCustomRegistry(unittest.TestCase):
    def test_custom_registry(self):
        reg = SchemaRegistry()
        reg.register("minimal", {
            "roles": ["user"],
            "content_types": ["text"],
            "required_fields": ["role", "content"],
            "max_content_length": 100,
        })
        n = MessageNormalizer(reg, target_provider="minimal")
        result = n.normalize({"role": "user", "content": "hi"})
        self.assertEqual(result["role"], "user")


if __name__ == "__main__":
    unittest.main()
