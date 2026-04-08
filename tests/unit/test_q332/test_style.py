"""Tests for review_learn.style (Q332, task 1774)."""
from __future__ import annotations

import unittest

from lidco.review_learn.style import (
    FeedbackTemplate,
    StyleConvention,
    StyleGuide,
    Tone,
    create_default_style_guide,
)


class TestFeedbackTemplate(unittest.TestCase):
    def test_render(self) -> None:
        t = FeedbackTemplate(
            template_id="t1", category="refactoring", tone=Tone.QUESTIONING,
            template="Consider {{action}} for {{target}}.",
        )
        result = t.render(action="extracting", target="readability")
        self.assertEqual(result, "Consider extracting for readability.")

    def test_render_no_vars(self) -> None:
        t = FeedbackTemplate(template_id="t1", category="c", tone=Tone.NEUTRAL, template="Plain text.")
        self.assertEqual(t.render(), "Plain text.")

    def test_frozen(self) -> None:
        t = FeedbackTemplate(template_id="t1", category="c", tone=Tone.NEUTRAL, template="x")
        with self.assertRaises(AttributeError):
            t.template_id = "new"  # type: ignore[misc]


class TestStyleConvention(unittest.TestCase):
    def test_fields(self) -> None:
        c = StyleConvention(name="c1", description="Be nice", priority=5)
        self.assertEqual(c.name, "c1")
        self.assertEqual(c.priority, 5)

    def test_defaults(self) -> None:
        c = StyleConvention(name="c1", description="d")
        self.assertEqual(c.priority, 0)
        self.assertEqual(c.do_examples, ())
        self.assertEqual(c.dont_examples, ())


class TestStyleGuide(unittest.TestCase):
    def test_add_and_get_convention(self) -> None:
        g = StyleGuide()
        c = StyleConvention(name="c1", description="d")
        g.add_convention(c)
        self.assertEqual(g.convention_count, 1)
        self.assertIs(g.get_convention("c1"), c)

    def test_remove_convention(self) -> None:
        g = StyleGuide()
        g.add_convention(StyleConvention(name="c1", description="d"))
        self.assertTrue(g.remove_convention("c1"))
        self.assertFalse(g.remove_convention("c1"))

    def test_list_conventions_sorted_by_priority(self) -> None:
        g = StyleGuide()
        g.add_convention(StyleConvention(name="low", description="d", priority=1))
        g.add_convention(StyleConvention(name="high", description="d", priority=10))
        convs = g.list_conventions()
        self.assertEqual(convs[0].name, "high")
        self.assertEqual(convs[1].name, "low")

    def test_add_and_get_template(self) -> None:
        g = StyleGuide()
        t = FeedbackTemplate(template_id="t1", category="c", tone=Tone.NEUTRAL, template="x")
        g.add_template(t)
        self.assertEqual(g.template_count, 1)
        self.assertIs(g.get_template("t1"), t)

    def test_remove_template(self) -> None:
        g = StyleGuide()
        g.add_template(FeedbackTemplate(template_id="t1", category="c", tone=Tone.NEUTRAL, template="x"))
        self.assertTrue(g.remove_template("t1"))
        self.assertFalse(g.remove_template("t1"))

    def test_list_templates_filter_category(self) -> None:
        g = StyleGuide()
        g.add_template(FeedbackTemplate(template_id="t1", category="sec", tone=Tone.DIRECT, template="x"))
        g.add_template(FeedbackTemplate(template_id="t2", category="style", tone=Tone.NEUTRAL, template="y"))
        found = g.list_templates(category="sec")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].template_id, "t1")

    def test_list_templates_filter_tone(self) -> None:
        g = StyleGuide()
        g.add_template(FeedbackTemplate(template_id="t1", category="c", tone=Tone.DIRECT, template="x"))
        g.add_template(FeedbackTemplate(template_id="t2", category="c", tone=Tone.ENCOURAGING, template="y"))
        found = g.list_templates(tone=Tone.ENCOURAGING)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].template_id, "t2")

    def test_render_feedback(self) -> None:
        g = StyleGuide()
        g.add_template(FeedbackTemplate(
            template_id="t1", category="c", tone=Tone.NEUTRAL,
            template="Fix {{issue}} please.",
        ))
        result = g.render_feedback("t1", issue="the bug")
        self.assertEqual(result, "Fix the bug please.")

    def test_render_feedback_not_found(self) -> None:
        g = StyleGuide()
        self.assertIsNone(g.render_feedback("nope"))

    def test_to_dict(self) -> None:
        g = StyleGuide(team_name="myteam")
        d = g.to_dict()
        self.assertEqual(d["team_name"], "myteam")
        self.assertEqual(d["default_tone"], "neutral")

    def test_created_at(self) -> None:
        g = StyleGuide()
        self.assertGreater(g.created_at, 0)


class TestCreateDefaultStyleGuide(unittest.TestCase):
    def test_has_conventions(self) -> None:
        g = create_default_style_guide()
        self.assertGreaterEqual(g.convention_count, 3)

    def test_has_templates(self) -> None:
        g = create_default_style_guide()
        self.assertGreaterEqual(g.template_count, 3)

    def test_known_convention(self) -> None:
        g = create_default_style_guide()
        self.assertIsNotNone(g.get_convention("be-constructive"))

    def test_known_template(self) -> None:
        g = create_default_style_guide()
        self.assertIsNotNone(g.get_template("suggest-refactor"))

    def test_custom_team_name(self) -> None:
        g = create_default_style_guide("alpha-team")
        self.assertEqual(g.team_name, "alpha-team")


if __name__ == "__main__":
    unittest.main()
