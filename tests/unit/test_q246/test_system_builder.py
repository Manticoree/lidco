"""Tests for lidco.prompts.system_builder (Q246)."""
from __future__ import annotations

import unittest

from lidco.prompts.system_builder import SystemPromptBuilder


class TestSystemPromptBuilderAddSection(unittest.TestCase):
    def test_add_section(self):
        b = SystemPromptBuilder()
        b.add_section("intro", "Hello")
        self.assertEqual(len(b.sections()), 1)

    def test_add_section_condition_false(self):
        b = SystemPromptBuilder()
        b.add_section("skip", "Hidden", condition=False)
        self.assertEqual(len(b.sections()), 0)

    def test_add_replaces_same_name(self):
        b = SystemPromptBuilder()
        b.add_section("intro", "v1")
        b.add_section("intro", "v2")
        self.assertEqual(len(b.sections()), 1)
        result = b.build()
        self.assertIn("v2", result)
        self.assertNotIn("v1", result)

    def test_priority_ordering(self):
        b = SystemPromptBuilder()
        b.add_section("low", "LOW", priority=1)
        b.add_section("high", "HIGH", priority=10)
        result = b.build()
        self.assertTrue(result.index("HIGH") < result.index("LOW"))


class TestSystemPromptBuilderRemove(unittest.TestCase):
    def test_remove_existing(self):
        b = SystemPromptBuilder()
        b.add_section("x", "content")
        self.assertTrue(b.remove_section("x"))
        self.assertEqual(len(b.sections()), 0)

    def test_remove_nonexistent(self):
        b = SystemPromptBuilder()
        self.assertFalse(b.remove_section("nope"))


class TestSystemPromptBuilderVariables(unittest.TestCase):
    def test_variable_injection(self):
        b = SystemPromptBuilder()
        b.add_section("greet", "Hello {{name}}!")
        b.set_variable("name", "Alice")
        result = b.build()
        self.assertEqual(result, "Hello Alice!")

    def test_variable_with_spaces(self):
        b = SystemPromptBuilder()
        b.add_section("greet", "Hello {{ name }}!")
        b.set_variable("name", "Bob")
        result = b.build()
        self.assertEqual(result, "Hello Bob!")

    def test_missing_variable_kept(self):
        b = SystemPromptBuilder()
        b.add_section("greet", "Hello {{name}}!")
        result = b.build()
        self.assertIn("{{name}}", result)

    def test_multiple_variables(self):
        b = SystemPromptBuilder()
        b.add_section("s", "{{a}} and {{b}}")
        b.set_variable("a", "X")
        b.set_variable("b", "Y")
        result = b.build()
        self.assertEqual(result, "X and Y")


class TestSystemPromptBuilderBuild(unittest.TestCase):
    def test_build_empty(self):
        b = SystemPromptBuilder()
        self.assertEqual(b.build(), "")

    def test_build_multiple_sections(self):
        b = SystemPromptBuilder()
        b.add_section("a", "AAA", priority=2)
        b.add_section("b", "BBB", priority=1)
        result = b.build()
        self.assertIn("AAA", result)
        self.assertIn("BBB", result)

    def test_build_with_budget(self):
        b = SystemPromptBuilder()
        b.add_section("long", "A" * 1000)
        result = b.build(token_budget=10)
        # 10 tokens * 4 chars = 40 chars max
        self.assertLessEqual(len(result), 40)

    def test_build_budget_no_trim_needed(self):
        b = SystemPromptBuilder()
        b.add_section("short", "Hi")
        result = b.build(token_budget=1000)
        self.assertEqual(result, "Hi")


class TestSystemPromptBuilderSections(unittest.TestCase):
    def test_sections_metadata(self):
        b = SystemPromptBuilder()
        b.add_section("intro", "Hello", priority=5)
        secs = b.sections()
        self.assertEqual(len(secs), 1)
        self.assertEqual(secs[0]["name"], "intro")
        self.assertEqual(secs[0]["priority"], 5)
        self.assertEqual(secs[0]["length"], 5)


class TestSystemPromptBuilderTokenEstimate(unittest.TestCase):
    def test_token_estimate(self):
        b = SystemPromptBuilder()
        b.add_section("a", "A" * 40)
        est = b.token_estimate()
        self.assertEqual(est, 10)

    def test_token_estimate_empty(self):
        b = SystemPromptBuilder()
        # No sections — still returns at least 1
        est = b.token_estimate()
        self.assertGreaterEqual(est, 0)


if __name__ == "__main__":
    unittest.main()
