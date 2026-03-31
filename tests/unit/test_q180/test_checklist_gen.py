"""Tests for ReviewChecklistGenerator."""

from __future__ import annotations

import unittest

from lidco.review.checklist_gen import (
    ChecklistItem,
    ReviewChecklist,
    ReviewChecklistGenerator,
)


class TestChecklistItem(unittest.TestCase):
    def test_defaults(self) -> None:
        item = ChecklistItem(category="General", description="Test")
        self.assertEqual(item.priority, "medium")
        self.assertFalse(item.checked)

    def test_custom_fields(self) -> None:
        item = ChecklistItem(
            category="Security", description="Check auth", priority="high", checked=True
        )
        self.assertEqual(item.category, "Security")
        self.assertTrue(item.checked)


class TestReviewChecklist(unittest.TestCase):
    def test_empty(self) -> None:
        cl = ReviewChecklist()
        self.assertEqual(cl.items, [])
        self.assertEqual(cl.high_priority_count, 0)

    def test_high_priority_count(self) -> None:
        cl = ReviewChecklist(items=[
            ChecklistItem("A", "a", "high"),
            ChecklistItem("B", "b", "low"),
            ChecklistItem("C", "c", "high"),
        ])
        self.assertEqual(cl.high_priority_count, 2)

    def test_format_empty(self) -> None:
        cl = ReviewChecklist(summary="No items.")
        self.assertIn("No items.", cl.format())

    def test_format_with_items(self) -> None:
        cl = ReviewChecklist(
            summary="Review checklist: 1 items",
            items=[ChecklistItem("API", "Check auth", "high")],
        )
        text = cl.format()
        self.assertIn("[HIGH]", text)
        self.assertIn("API", text)
        self.assertIn("[ ]", text)

    def test_format_checked(self) -> None:
        cl = ReviewChecklist(
            summary="Done",
            items=[ChecklistItem("A", "Done", "low", checked=True)],
        )
        self.assertIn("[x]", cl.format())


class TestReviewChecklistGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = ReviewChecklistGenerator()

    def test_empty_diff(self) -> None:
        result = self.gen.generate("")
        self.assertEqual(result.items, [])
        self.assertIn("No review items", result.summary)

    def test_api_endpoint_detected(self) -> None:
        diff = "@app.get('/users')\ndef list_users():\n    pass"
        result = self.gen.generate(diff)
        categories = [i.category for i in result.items]
        self.assertIn("API", categories)

    def test_db_migration_detected(self) -> None:
        diff = "ALTER TABLE users ADD COLUMN age INT;"
        result = self.gen.generate(diff)
        categories = [i.category for i in result.items]
        self.assertIn("Database", categories)

    def test_bare_except_detected(self) -> None:
        diff = "except:\n    pass"
        result = self.gen.generate(diff)
        categories = [i.category for i in result.items]
        self.assertIn("Error Handling", categories)

    def test_config_change_detected(self) -> None:
        diff = 'db_url = os.environ["DB_URL"]'
        result = self.gen.generate(diff)
        categories = [i.category for i in result.items]
        self.assertIn("Configuration", categories)

    def test_custom_rules(self) -> None:
        rules = [
            {
                "pattern": r"TODO",
                "category": "Cleanup",
                "description": "TODO found",
                "priority": "low",
            }
        ]
        result = self.gen.generate("# TODO: fix later", rules=rules)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].category, "Cleanup")

    def test_invalid_regex_skipped(self) -> None:
        rules = [{"pattern": "[invalid", "category": "X", "description": "Y"}]
        result = self.gen.generate("any text", rules=rules)
        self.assertEqual(len(result.items), 0)

    def test_dedup_same_category_description(self) -> None:
        diff = "@app.get('/a')\n@app.post('/b')"
        result = self.gen.generate(diff)
        # Each rule should only produce one item even with multiple matches
        cats = [(i.category, i.description) for i in result.items]
        self.assertEqual(len(cats), len(set(cats)))

    def test_summary_format(self) -> None:
        diff = "except:\n    pass\n@app.get('/x')"
        result = self.gen.generate(diff)
        self.assertIn("high", result.summary)

    def test_new_file_rule(self) -> None:
        diff = "+++ b/new_module.py\n+class Foo:\n+    pass"
        result = self.gen.generate(diff)
        categories = [i.category for i in result.items]
        self.assertIn("Testing", categories)

    def test_empty_pattern_skipped(self) -> None:
        rules = [{"pattern": "", "category": "X", "description": "Y"}]
        result = self.gen.generate("anything", rules=rules)
        self.assertEqual(len(result.items), 0)


if __name__ == "__main__":
    unittest.main()
