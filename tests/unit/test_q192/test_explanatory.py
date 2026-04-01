"""Tests for ExplanatoryStyle — task 1073."""
from __future__ import annotations

import unittest

from lidco.output.explanatory import ExplanatoryStyle
from lidco.output.style_registry import OutputStyle


class TestExplanatoryProtocol(unittest.TestCase):
    def test_is_output_style(self):
        self.assertIsInstance(ExplanatoryStyle(), OutputStyle)


class TestExplanatoryName(unittest.TestCase):
    def test_name(self):
        self.assertEqual(ExplanatoryStyle().name, "explanatory")


class TestExplanatoryTransform(unittest.TestCase):
    def test_trigger_word_adds_why(self):
        result = ExplanatoryStyle().transform("Changed the config file")
        self.assertTrue(result.startswith("Why:"))

    def test_no_trigger_passes_through(self):
        text = "This is normal text"
        result = ExplanatoryStyle().transform(text)
        self.assertEqual(result, text)

    def test_empty_passthrough(self):
        self.assertEqual(ExplanatoryStyle().transform(""), "")

    def test_added_trigger(self):
        result = ExplanatoryStyle().transform("Added a new module")
        self.assertIn("Why:", result)
        self.assertIn("Added a new module", result)

    def test_whitespace_only(self):
        self.assertEqual(ExplanatoryStyle().transform("   "), "   ")


class TestExplanatoryWrapResponse(unittest.TestCase):
    def test_wraps_with_footer(self):
        result = ExplanatoryStyle().wrap_response("Some response")
        self.assertIn("Explanatory mode", result)
        self.assertIn("Some response", result)

    def test_empty_response(self):
        self.assertEqual(ExplanatoryStyle().wrap_response(""), "")

    def test_whitespace_response(self):
        self.assertEqual(ExplanatoryStyle().wrap_response("  "), "  ")


class TestAddContext(unittest.TestCase):
    def test_adds_label(self):
        result = ExplanatoryStyle().add_context("Some text", "rationale")
        self.assertEqual(result, "[Rationale] Some text")

    def test_custom_context_type(self):
        result = ExplanatoryStyle().add_context("Info", "tradeoff")
        self.assertIn("[Tradeoff]", result)

    def test_empty_text(self):
        result = ExplanatoryStyle().add_context("", "rationale")
        self.assertEqual(result, "")

    def test_preserves_content(self):
        result = ExplanatoryStyle().add_context("important info", "alternative")
        self.assertIn("important info", result)


class TestExplainChoice(unittest.TestCase):
    def test_no_alternatives(self):
        result = ExplanatoryStyle().explain_choice("Python", ())
        self.assertIn("Python", result)
        self.assertIn("no alternatives", result)

    def test_with_alternatives(self):
        result = ExplanatoryStyle().explain_choice("Python", ("Ruby", "Go"))
        self.assertIn("Python", result)
        self.assertIn("Ruby", result)
        self.assertIn("Go", result)
        self.assertIn("Alternatives considered", result)

    def test_single_alternative(self):
        result = ExplanatoryStyle().explain_choice("A", ("B",))
        self.assertIn("B", result)

    def test_result_is_string(self):
        result = ExplanatoryStyle().explain_choice("X", ("Y",))
        self.assertIsInstance(result, str)
