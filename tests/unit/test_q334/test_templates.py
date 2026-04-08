"""Tests for lidco.writing.templates — TemplateLibrary."""

from __future__ import annotations

import unittest

from lidco.writing.templates import (
    TemplateLibrary,
    TemplateSection,
    WritingTemplate,
)


class TestTemplateSection(unittest.TestCase):
    def test_defaults(self):
        s = TemplateSection(title="Intro", placeholder="Write here.")
        self.assertTrue(s.required)

    def test_optional(self):
        s = TemplateSection(title="Notes", placeholder="Optional.", required=False)
        self.assertFalse(s.required)


class TestWritingTemplate(unittest.TestCase):
    def test_render_basic(self):
        tpl = WritingTemplate(
            name="Test",
            description="A test template",
            sections=[TemplateSection("Summary", "Hello {{name}}.")],
            variables=["name"],
        )
        rendered = tpl.render({"name": "World"})
        self.assertIn("# Test", rendered)
        self.assertIn("## Summary", rendered)
        self.assertIn("Hello World.", rendered)

    def test_render_no_values(self):
        tpl = WritingTemplate(
            name="Test",
            description="A test template",
            sections=[TemplateSection("Summary", "Hello {{name}}.")],
            variables=["name"],
        )
        rendered = tpl.render()
        self.assertIn("{{name}}", rendered)

    def test_required_sections(self):
        tpl = WritingTemplate(
            name="Test",
            description="desc",
            sections=[
                TemplateSection("A", "a", required=True),
                TemplateSection("B", "b", required=False),
                TemplateSection("C", "c", required=True),
            ],
        )
        self.assertEqual(len(tpl.required_sections), 2)


class TestTemplateLibrary(unittest.TestCase):
    def setUp(self):
        self.lib = TemplateLibrary()

    def test_default_templates_loaded(self):
        self.assertGreaterEqual(self.lib.count, 5)

    def test_list_templates(self):
        templates = self.lib.list_templates()
        self.assertGreater(len(templates), 0)
        names = {t.name.lower() for t in templates}
        self.assertIn("rfc", names)
        self.assertIn("design document", names)
        self.assertIn("postmortem", names)
        self.assertIn("runbook", names)
        self.assertIn("readme", names)

    def test_get_rfc(self):
        tpl = self.lib.get("RFC")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.name, "RFC")
        self.assertGreater(len(tpl.sections), 0)

    def test_get_case_insensitive(self):
        tpl = self.lib.get("rfc")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.name, "RFC")

    def test_get_not_found(self):
        self.assertIsNone(self.lib.get("nonexistent"))

    def test_add_custom_template(self):
        custom = WritingTemplate(name="ADR", description="Architecture Decision Record")
        self.lib.add(custom)
        self.assertIsNotNone(self.lib.get("ADR"))

    def test_remove_template(self):
        self.assertTrue(self.lib.remove("RFC"))
        self.assertIsNone(self.lib.get("RFC"))

    def test_remove_not_found(self):
        self.assertFalse(self.lib.remove("nonexistent"))

    def test_render_by_name(self):
        rendered = self.lib.render("RFC", {"author": "Alice"})
        self.assertIsNotNone(rendered)
        self.assertIn("# RFC", rendered)

    def test_render_not_found(self):
        self.assertIsNone(self.lib.render("nonexistent"))

    def test_postmortem_has_sections(self):
        tpl = self.lib.get("Postmortem")
        self.assertIsNotNone(tpl)
        titles = [s.title for s in tpl.sections]
        self.assertIn("Root Cause", titles)
        self.assertIn("Timeline", titles)
        self.assertIn("Action Items", titles)

    def test_runbook_has_sections(self):
        tpl = self.lib.get("Runbook")
        self.assertIsNotNone(tpl)
        titles = [s.title for s in tpl.sections]
        self.assertIn("Troubleshooting", titles)
        self.assertIn("Recovery Procedures", titles)

    def test_readme_render_with_project_name(self):
        rendered = self.lib.render("README", {"project_name": "MyApp"})
        self.assertIsNotNone(rendered)
        self.assertIn("MyApp", rendered)


if __name__ == "__main__":
    unittest.main()
