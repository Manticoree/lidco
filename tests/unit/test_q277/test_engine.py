"""Tests for AnnotationEngine."""
from __future__ import annotations

import json
import unittest

from lidco.annotations.engine import Annotation, AnnotationEngine


class TestAnnotation(unittest.TestCase):
    def test_dataclass_fields(self):
        a = Annotation(id="abc", file_path="f.py", line=1, text="hi")
        self.assertEqual(a.id, "abc")
        self.assertEqual(a.category, "note")
        self.assertEqual(a.author, "system")
        self.assertIsInstance(a.created_at, float)


class TestAnnotationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AnnotationEngine()

    def test_add_and_get(self):
        ann = self.engine.add("f.py", 10, "fix this")
        self.assertIsNotNone(ann.id)
        self.assertEqual(self.engine.get(ann.id), ann)

    def test_remove_existing(self):
        ann = self.engine.add("f.py", 1, "x")
        self.assertTrue(self.engine.remove(ann.id))
        self.assertIsNone(self.engine.get(ann.id))

    def test_remove_missing(self):
        self.assertFalse(self.engine.remove("nonexistent"))

    def test_for_file(self):
        self.engine.add("a.py", 5, "a1")
        self.engine.add("a.py", 2, "a2")
        self.engine.add("b.py", 1, "b1")
        result = self.engine.for_file("a.py")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].line, 2)  # sorted

    def test_for_line(self):
        self.engine.add("a.py", 3, "x")
        self.engine.add("a.py", 3, "y")
        self.engine.add("a.py", 4, "z")
        self.assertEqual(len(self.engine.for_line("a.py", 3)), 2)

    def test_by_category(self):
        self.engine.add("f.py", 1, "a", category="warning")
        self.engine.add("f.py", 2, "b", category="note")
        self.engine.add("f.py", 3, "c", category="warning")
        self.assertEqual(len(self.engine.by_category("warning")), 2)

    def test_all_and_count(self):
        self.assertEqual(self.engine.count(), 0)
        self.engine.add("f.py", 1, "a")
        self.engine.add("f.py", 2, "b")
        self.assertEqual(self.engine.count(), 2)
        self.assertEqual(len(self.engine.all_annotations()), 2)

    def test_clear_all(self):
        self.engine.add("a.py", 1, "x")
        self.engine.add("b.py", 1, "y")
        n = self.engine.clear()
        self.assertEqual(n, 2)
        self.assertEqual(self.engine.count(), 0)

    def test_clear_by_file(self):
        self.engine.add("a.py", 1, "x")
        self.engine.add("b.py", 1, "y")
        n = self.engine.clear("a.py")
        self.assertEqual(n, 1)
        self.assertEqual(self.engine.count(), 1)

    def test_export_json(self):
        self.engine.add("f.py", 1, "note")
        data = json.loads(self.engine.export("json"))
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["text"], "note")

    def test_export_csv(self):
        self.engine.add("f.py", 1, "note")
        csv = self.engine.export("csv")
        self.assertIn("id,file_path", csv)

    def test_summary(self):
        self.engine.add("a.py", 1, "x", category="warning")
        self.engine.add("b.py", 2, "y", category="note")
        s = self.engine.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["files"], 2)
        self.assertIn("warning", s["categories"])

    def test_add_custom_author(self):
        ann = self.engine.add("f.py", 1, "x", author="alice")
        self.assertEqual(ann.author, "alice")


if __name__ == "__main__":
    unittest.main()
