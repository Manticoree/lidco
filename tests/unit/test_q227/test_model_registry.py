"""Tests for budget.model_registry — ModelInfo & ModelRegistry."""
from __future__ import annotations

import unittest

from lidco.budget.model_registry import ModelInfo, ModelRegistry


class TestModelInfo(unittest.TestCase):
    def test_frozen(self):
        info = ModelInfo(name="test", context_window=1000)
        with self.assertRaises(AttributeError):
            info.name = "changed"  # type: ignore[misc]

    def test_defaults(self):
        info = ModelInfo(name="m", context_window=100)
        self.assertEqual(info.max_output, 4096)
        self.assertEqual(info.provider, "")
        self.assertFalse(info.supports_caching)
        self.assertFalse(info.supports_vision)


class TestModelRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = ModelRegistry()

    def test_builtins_loaded(self):
        models = self.reg.list_models()
        self.assertGreaterEqual(len(models), 12)

    def test_get_exact_match(self):
        info = self.reg.get("claude-opus-4")
        self.assertIsNotNone(info)
        self.assertEqual(info.context_window, 200000)

    def test_get_substring_match(self):
        info = self.reg.get("claude-sonnet")
        self.assertIsNotNone(info)
        self.assertIn("sonnet", info.name)

    def test_get_unknown_returns_none(self):
        self.assertIsNone(self.reg.get("nonexistent-model-xyz"))

    def test_register_custom_model(self):
        custom = ModelInfo(name="my-model", context_window=50000, provider="custom")
        self.reg.register(custom)
        info = self.reg.get("my-model")
        self.assertIsNotNone(info)
        self.assertEqual(info.context_window, 50000)

    def test_register_overrides(self):
        override = ModelInfo(name="gpt-4o", context_window=999)
        self.reg.register(override)
        info = self.reg.get("gpt-4o")
        self.assertEqual(info.context_window, 999)

    def test_get_context_window(self):
        self.assertEqual(self.reg.get_context_window("claude-opus-4"), 200000)

    def test_get_context_window_default(self):
        self.assertEqual(self.reg.get_context_window("unknown-xyz", default=64000), 64000)

    def test_get_max_output(self):
        self.assertEqual(self.reg.get_max_output("gpt-4o"), 4096)

    def test_get_max_output_default(self):
        self.assertEqual(self.reg.get_max_output("unknown-xyz", default=8192), 8192)

    def test_gemini_large_context(self):
        info = self.reg.get("gemini-2.5-pro")
        self.assertIsNotNone(info)
        self.assertEqual(info.context_window, 1000000)

    def test_summary(self):
        s = self.reg.summary()
        self.assertIn("Model Registry", s)
        self.assertIn("claude-opus-4", s)


if __name__ == "__main__":
    unittest.main()
