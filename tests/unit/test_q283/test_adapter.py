"""Tests for lidco.adaptive.adapter — PromptAdapter."""
from __future__ import annotations

import unittest

from lidco.adaptive.adapter import PromptAdapter


class TestPromptAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = PromptAdapter()

    def test_supported_types_default(self):
        types = self.adapter.supported_types()
        self.assertIn("code", types)
        self.assertIn("explanation", types)
        self.assertIn("debugging", types)
        self.assertEqual(types, sorted(types))

    def test_get_template_known(self):
        tpl = self.adapter.get_template("code")
        self.assertIn("{prompt}", tpl)
        self.assertIn("engineer", tpl.lower())

    def test_get_template_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.adapter.get_template("nonexistent")

    def test_adapt_code(self):
        result = self.adapter.adapt("write a sort function", "code")
        self.assertIn("write a sort function", result)
        self.assertIn("engineer", result.lower())

    def test_adapt_explanation(self):
        result = self.adapter.adapt("how does TCP work", "explanation")
        self.assertIn("how does TCP work", result)

    def test_adapt_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.adapter.adapt("test", "bogus_type")

    def test_adapt_with_model_hint(self):
        adapter = PromptAdapter(model="gpt-4-turbo")
        result = adapter.adapt("fix this", "debugging")
        self.assertIn("precise", result.lower())

    def test_adapt_with_claude_model(self):
        adapter = PromptAdapter(model="claude-3")
        result = adapter.adapt("explain", "explanation")
        self.assertIn("step by step", result.lower())

    def test_add_template(self):
        self.adapter.add_template("custom", "Custom: {prompt}")
        tpl = self.adapter.get_template("custom")
        self.assertEqual(tpl, "Custom: {prompt}")
        self.assertIn("custom", self.adapter.supported_types())

    def test_remove_template(self):
        self.adapter.add_template("temp", "T: {prompt}")
        self.assertTrue(self.adapter.remove_template("temp"))
        self.assertFalse(self.adapter.remove_template("temp"))

    def test_adapt_no_model(self):
        adapter = PromptAdapter(model="")
        result = adapter.adapt("hello", "code")
        # Should not have any model hint prefix
        self.assertTrue(result.startswith("You are"))


if __name__ == "__main__":
    unittest.main()
