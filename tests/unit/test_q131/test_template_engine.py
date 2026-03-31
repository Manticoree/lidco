"""Tests for Q131 PromptTemplateEngine."""
from __future__ import annotations
import unittest
from lidco.prompts.template_engine import PromptTemplateEngine, RenderContext


class TestRenderContext(unittest.TestCase):
    def test_defaults(self):
        ctx = RenderContext(variables={"a": 1})
        self.assertFalse(ctx.strict)
        self.assertEqual(ctx.variables["a"], 1)


class TestPromptTemplateEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PromptTemplateEngine()

    # --- variable substitution ---

    def test_simple_var(self):
        result = self.engine.render_dict("Hello {{name}}!", {"name": "World"})
        self.assertEqual(result, "Hello World!")

    def test_multiple_vars(self):
        result = self.engine.render_dict("{{a}} + {{b}} = {{c}}", {"a": "1", "b": "2", "c": "3"})
        self.assertEqual(result, "1 + 2 = 3")

    def test_undefined_var_non_strict(self):
        result = self.engine.render_dict("Hi {{missing}}", {})
        self.assertEqual(result, "Hi ")

    def test_undefined_var_strict_raises(self):
        ctx = RenderContext(variables={}, strict=True)
        with self.assertRaises(KeyError):
            self.engine.render("Hi {{missing}}", ctx)

    def test_var_as_int(self):
        result = self.engine.render_dict("Count: {{n}}", {"n": 42})
        self.assertEqual(result, "Count: 42")

    # --- if blocks ---

    def test_if_true(self):
        result = self.engine.render_dict("{% if show %}visible{% endif %}", {"show": True})
        self.assertEqual(result, "visible")

    def test_if_false(self):
        result = self.engine.render_dict("{% if show %}visible{% endif %}", {"show": False})
        self.assertEqual(result, "")

    def test_if_missing_var(self):
        result = self.engine.render_dict("{% if missing %}x{% endif %}", {})
        self.assertEqual(result, "")

    def test_if_with_var_inside(self):
        result = self.engine.render_dict("{% if show %}Hello {{name}}{% endif %}", {"show": True, "name": "Bob"})
        self.assertIn("Hello Bob", result)

    # --- for blocks ---

    def test_for_basic(self):
        result = self.engine.render_dict("{% for item in items %}{{item}} {% endfor %}", {"items": ["a", "b", "c"]})
        self.assertIn("a", result)
        self.assertIn("b", result)
        self.assertIn("c", result)

    def test_for_empty_list(self):
        result = self.engine.render_dict("{% for item in items %}{{item}}{% endfor %}", {"items": []})
        self.assertEqual(result, "")

    def test_for_missing_list(self):
        result = self.engine.render_dict("{% for item in items %}{{item}}{% endfor %}", {})
        self.assertEqual(result, "")

    # --- extract_variables ---

    def test_extract_variables(self):
        vars_ = self.engine.extract_variables("Hello {{name}}, you have {{count}} messages.")
        self.assertEqual(vars_, ["name", "count"])

    def test_extract_unique(self):
        vars_ = self.engine.extract_variables("{{x}} and {{x}} again")
        self.assertEqual(vars_, ["x"])

    def test_extract_empty(self):
        self.assertEqual(self.engine.extract_variables("no vars here"), [])

    # --- validate ---

    def test_validate_all_present(self):
        missing = self.engine.validate("{{a}} {{b}}", {"a": 1, "b": 2})
        self.assertEqual(missing, [])

    def test_validate_missing_vars(self):
        missing = self.engine.validate("{{a}} {{b}} {{c}}", {"a": 1})
        self.assertIn("b", missing)
        self.assertIn("c", missing)

    def test_validate_empty_template(self):
        self.assertEqual(self.engine.validate("no vars", {}), [])

    # --- render convenience ---

    def test_render_dict_convenience(self):
        result = self.engine.render_dict("{{x}}", {"x": "hello"})
        self.assertEqual(result, "hello")

    def test_render_with_context(self):
        ctx = RenderContext(variables={"y": "world"})
        result = self.engine.render("{{y}}", ctx)
        self.assertEqual(result, "world")


if __name__ == "__main__":
    unittest.main()
