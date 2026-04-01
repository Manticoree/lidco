"""Tests for ConversationTemplate, ConversationRenderer, and helpers."""
from __future__ import annotations

import unittest

from lidco.templates.conversation import (
    ConversationBranch,
    ConversationRenderer,
    ConversationTemplate,
    ConversationTurn,
    TemplateVariable,
    UndefinedVariableError,
    _eval_condition,
    substitute,
    template_from_dict,
    template_to_dict,
    template_to_yaml,
)


def _sample_template() -> ConversationTemplate:
    return ConversationTemplate(
        name="greeting",
        description="A simple greeting template",
        variables=(
            TemplateVariable(name="user_name", description="The user's name"),
            TemplateVariable(name="style", default="formal", required=False),
        ),
        turns=(
            ConversationTurn(role="system", content="You are a helpful assistant."),
            ConversationTurn(role="user", content="Hello, my name is {{user_name}}."),
            ConversationTurn(
                role="assistant",
                content="Nice to meet you, {{user_name}}!",
                condition="style == \"formal\"",
            ),
        ),
        branches=(
            ConversationBranch(
                condition="style == \"casual\"",
                turns=(
                    ConversationTurn(role="assistant", content="Hey {{user_name}}!"),
                ),
            ),
        ),
        tags=("greeting", "demo"),
        version="1.0",
    )


class TestTemplateVariable(unittest.TestCase):
    def test_frozen(self):
        v = TemplateVariable(name="x")
        with self.assertRaises(AttributeError):
            v.name = "y"  # type: ignore[misc]

    def test_defaults(self):
        v = TemplateVariable(name="x")
        self.assertTrue(v.required)
        self.assertIsNone(v.default)


class TestConversationTemplate(unittest.TestCase):
    def test_variable_names(self):
        tmpl = _sample_template()
        self.assertEqual(tmpl.variable_names(), ["user_name", "style"])

    def test_required_variables(self):
        tmpl = _sample_template()
        self.assertEqual(tmpl.required_variables(), ["user_name"])


class TestSubstitute(unittest.TestCase):
    def test_basic_substitution(self):
        result = substitute("Hello {{name}}, welcome!", {"name": "Alice"})
        self.assertEqual(result, "Hello Alice, welcome!")

    def test_missing_var_left_as_is(self):
        result = substitute("Hello {{name}}", {})
        self.assertEqual(result, "Hello {{name}}")


class TestEvalCondition(unittest.TestCase):
    def test_equality(self):
        self.assertTrue(_eval_condition('x == "hello"', {"x": "hello"}))
        self.assertFalse(_eval_condition('x == "hello"', {"x": "world"}))

    def test_not(self):
        self.assertTrue(_eval_condition("not missing", {"missing": False}))
        self.assertFalse(_eval_condition("not present", {"present": True}))

    def test_and_or(self):
        vs = {"a": True, "b": False}
        self.assertFalse(_eval_condition("a and b", vs))
        self.assertTrue(_eval_condition("a or b", vs))

    def test_numeric_comparison(self):
        self.assertTrue(_eval_condition("x > 5", {"x": 10}))
        self.assertFalse(_eval_condition("x < 5", {"x": 10}))


class TestConversationRenderer(unittest.TestCase):
    def test_render_basic(self):
        tmpl = _sample_template()
        renderer = ConversationRenderer()
        turns = renderer.render(tmpl, {"user_name": "Alice", "style": "formal"})
        self.assertEqual(len(turns), 3)
        self.assertIn("Alice", turns[1].content)
        self.assertIn("Alice", turns[2].content)

    def test_render_branch(self):
        tmpl = _sample_template()
        renderer = ConversationRenderer()
        turns = renderer.render(tmpl, {"user_name": "Bob", "style": "casual"})
        # System + user + branch assistant (conditional turn skipped)
        contents = [t.content for t in turns]
        self.assertTrue(any("Hey Bob" in c for c in contents))

    def test_render_text(self):
        tmpl = _sample_template()
        renderer = ConversationRenderer()
        text = renderer.render_text(tmpl, {"user_name": "Eve", "style": "formal"})
        self.assertIn("[user]", text)
        self.assertIn("Eve", text)

    def test_strict_mode_raises(self):
        tmpl = _sample_template()
        renderer = ConversationRenderer(strict=True)
        with self.assertRaises(UndefinedVariableError):
            renderer.render(tmpl, {})  # missing required user_name


class TestSerialization(unittest.TestCase):
    def test_round_trip_dict(self):
        tmpl = _sample_template()
        data = template_to_dict(tmpl)
        restored = template_from_dict(data)
        self.assertEqual(restored.name, tmpl.name)
        self.assertEqual(len(restored.turns), len(tmpl.turns))
        self.assertEqual(len(restored.branches), len(tmpl.branches))
        self.assertEqual(len(restored.variables), len(tmpl.variables))

    def test_to_yaml_contains_name(self):
        tmpl = _sample_template()
        yaml_text = template_to_yaml(tmpl)
        self.assertIn("name: greeting", yaml_text)
        self.assertIn("tags:", yaml_text)
        self.assertIn("variables:", yaml_text)


if __name__ == "__main__":
    unittest.main()
