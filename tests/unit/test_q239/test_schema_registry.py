"""Tests for lidco.conversation.schema_registry — SchemaRegistry."""
from __future__ import annotations

import unittest

from lidco.conversation.schema_registry import SchemaRegistry


class TestSchemaRegistryBasics(unittest.TestCase):
    def test_empty_registry(self):
        reg = SchemaRegistry()
        self.assertIsNone(reg.get("openai"))
        self.assertFalse(reg.has("openai"))
        self.assertEqual(reg.list_providers(), [])

    def test_register_and_get(self):
        reg = SchemaRegistry()
        schema = {"roles": ["user"], "content_types": ["text"], "required_fields": ["role"], "max_content_length": 500}
        reg.register("custom", schema)
        self.assertTrue(reg.has("custom"))
        got = reg.get("custom")
        self.assertEqual(got["max_content_length"], 500)

    def test_get_returns_copy(self):
        reg = SchemaRegistry()
        reg.register("x", {"roles": ["user"]})
        a = reg.get("x")
        b = reg.get("x")
        self.assertIsNot(a, b)

    def test_register_overwrites(self):
        reg = SchemaRegistry()
        reg.register("x", {"val": 1})
        reg.register("x", {"val": 2})
        self.assertEqual(reg.get("x")["val"], 2)

    def test_list_providers_sorted(self):
        reg = SchemaRegistry()
        reg.register("z", {})
        reg.register("a", {})
        self.assertEqual(reg.list_providers(), ["a", "z"])


class TestWithDefaults(unittest.TestCase):
    def test_has_openai_and_anthropic(self):
        reg = SchemaRegistry.with_defaults()
        self.assertTrue(reg.has("openai"))
        self.assertTrue(reg.has("anthropic"))

    def test_openai_schema(self):
        schema = SchemaRegistry.with_defaults().get("openai")
        self.assertIn("user", schema["roles"])
        self.assertIn("text", schema["content_types"])

    def test_anthropic_schema(self):
        schema = SchemaRegistry.with_defaults().get("anthropic")
        self.assertIn("tool_use", schema["content_types"])
        self.assertEqual(schema["max_content_length"], 200_000)


class TestAutoSelect(unittest.TestCase):
    def setUp(self):
        self.reg = SchemaRegistry.with_defaults()

    def test_claude_model(self):
        schema = self.reg.auto_select("claude-3-opus")
        self.assertIn("tool_use", schema["content_types"])

    def test_gpt_model(self):
        schema = self.reg.auto_select("gpt-4o")
        self.assertIn("image_url", schema["content_types"])

    def test_o1_model(self):
        schema = self.reg.auto_select("o1-preview")
        self.assertEqual(schema["max_content_length"], 100_000)

    def test_unknown_model_returns_default(self):
        schema = self.reg.auto_select("llama-3.1")
        self.assertIn("text", schema["content_types"])
        self.assertEqual(schema["max_content_length"], 100_000)

    def test_case_insensitive(self):
        schema = self.reg.auto_select("Claude-Sonnet")
        self.assertIn("tool_use", schema["content_types"])


if __name__ == "__main__":
    unittest.main()
