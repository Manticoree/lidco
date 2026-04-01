"""Tests for APIReference, APIEntry."""
from __future__ import annotations

import unittest

from lidco.doc_intel.api_reference import APIEntry, APIReference


class TestAPIEntryFrozen(unittest.TestCase):
    def test_creation(self):
        e = APIEntry(name="foo", kind="function")
        self.assertEqual(e.name, "foo")
        self.assertEqual(e.kind, "function")
        self.assertEqual(e.signature, "")
        self.assertEqual(e.docstring, "")
        self.assertEqual(e.module, "")
        self.assertEqual(e.line, 0)

    def test_frozen(self):
        e = APIEntry(name="foo", kind="function")
        with self.assertRaises(AttributeError):
            e.name = "bar"  # type: ignore[misc]


class TestAPIReferenceScanSource(unittest.TestCase):
    def test_scan_functions(self):
        src = (
            'def add(a: int, b: int) -> int:\n'
            '    """Add two numbers."""\n'
            '    return a + b\n'
            '\n'
            'def sub(a: int, b: int) -> int:\n'
            '    return a - b\n'
        )
        ref = APIReference()
        entries = ref.scan_source(src, module_name="math_utils")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].name, "add")
        self.assertEqual(entries[0].kind, "function")
        self.assertEqual(entries[0].module, "math_utils")
        self.assertIn("Add two numbers", entries[0].docstring)
        self.assertEqual(entries[1].name, "sub")

    def test_scan_class_and_methods(self):
        src = (
            'class Calc:\n'
            '    """A calculator."""\n'
            '    def multiply(self, a: int, b: int) -> int:\n'
            '        return a * b\n'
        )
        ref = APIReference()
        entries = ref.scan_source(src)
        kinds = [e.kind for e in entries]
        self.assertIn("class", kinds)
        self.assertIn("method", kinds)
        self.assertTrue(any("Calc.multiply" in e.name for e in entries))

    def test_entry_count(self):
        ref = APIReference()
        self.assertEqual(ref.entry_count(), 0)
        ref.add_entry(APIEntry(name="a", kind="function"))
        self.assertEqual(ref.entry_count(), 1)


class TestAPIReferenceMarkdown(unittest.TestCase):
    def test_empty_markdown(self):
        ref = APIReference()
        md = ref.to_markdown()
        self.assertIn("No entries", md)

    def test_markdown_contains_entries(self):
        ref = APIReference()
        ref.add_entry(APIEntry(name="run", kind="function", signature="()", docstring="Run it."))
        md = ref.to_markdown()
        self.assertIn("def run", md)
        self.assertIn("Run it.", md)


class TestAPIReferenceToDict(unittest.TestCase):
    def test_dict_structure(self):
        ref = APIReference()
        ref.add_entry(APIEntry(name="f", kind="function", module="m"))
        d = ref.to_dict()
        self.assertIn("entries", d)
        self.assertIn("count", d)
        self.assertEqual(d["count"], 1)
        self.assertEqual(d["entries"][0]["name"], "f")


class TestAPIReferenceByModule(unittest.TestCase):
    def test_group_by_module(self):
        ref = APIReference()
        ref.add_entry(APIEntry(name="a", kind="function", module="mod1"))
        ref.add_entry(APIEntry(name="b", kind="function", module="mod2"))
        ref.add_entry(APIEntry(name="c", kind="function", module="mod1"))
        grouped = ref.by_module()
        self.assertEqual(len(grouped["mod1"]), 2)
        self.assertEqual(len(grouped["mod2"]), 1)

    def test_unknown_module(self):
        ref = APIReference()
        ref.add_entry(APIEntry(name="x", kind="function"))
        grouped = ref.by_module()
        self.assertIn("<unknown>", grouped)


class TestAPIReferenceClear(unittest.TestCase):
    def test_clear(self):
        ref = APIReference()
        ref.add_entry(APIEntry(name="a", kind="function"))
        ref.clear()
        self.assertEqual(ref.entry_count(), 0)


if __name__ == "__main__":
    unittest.main()
