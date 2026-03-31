"""Tests for symbol_index2 — Q125."""
from __future__ import annotations
import unittest
from lidco.analysis.symbol_index2 import SymbolDef, SymbolRef, SymbolIndex


class TestSymbolDef(unittest.TestCase):
    def test_creation(self):
        s = SymbolDef(name="foo", kind="function", module="mod", line=1)
        self.assertEqual(s.name, "foo")
        self.assertEqual(s.kind, "function")
        self.assertEqual(s.module, "mod")
        self.assertEqual(s.line, 1)
        self.assertEqual(s.docstring, "")

    def test_with_docstring(self):
        s = SymbolDef(name="Bar", kind="class", module="m", line=5, docstring="A class.")
        self.assertEqual(s.docstring, "A class.")


class TestSymbolRef(unittest.TestCase):
    def test_creation(self):
        r = SymbolRef(name="foo", module="mod", line=10)
        self.assertEqual(r.name, "foo")


class TestSymbolIndex(unittest.TestCase):
    def setUp(self):
        self.idx = SymbolIndex()

    def test_empty_len(self):
        self.assertEqual(len(self.idx), 0)

    def test_add_definition(self):
        self.idx.add_definition(SymbolDef("foo", "function", "mod", 1))
        self.assertEqual(len(self.idx), 1)

    def test_add_reference(self):
        self.idx.add_reference(SymbolRef("foo", "mod", 10))
        self.assertEqual(len(self.idx), 0)  # refs don't count in len

    def test_find_definition(self):
        self.idx.add_definition(SymbolDef("foo", "function", "mod", 1))
        result = self.idx.find_definition("foo")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "foo")

    def test_find_definition_missing(self):
        self.assertIsNone(self.idx.find_definition("bar"))

    def test_find_all_definitions(self):
        self.idx.add_definition(SymbolDef("foo", "function", "mod1", 1))
        self.idx.add_definition(SymbolDef("foo", "function", "mod2", 5))
        results = self.idx.find_all_definitions("foo")
        self.assertEqual(len(results), 2)

    def test_find_references(self):
        self.idx.add_reference(SymbolRef("foo", "mod", 10))
        self.idx.add_reference(SymbolRef("bar", "mod", 20))
        refs = self.idx.find_references("foo")
        self.assertEqual(len(refs), 1)

    def test_list_symbols_all(self):
        self.idx.add_definition(SymbolDef("foo", "function", "m", 1))
        self.idx.add_definition(SymbolDef("Bar", "class", "m", 5))
        self.assertEqual(len(self.idx.list_symbols()), 2)

    def test_list_symbols_by_kind(self):
        self.idx.add_definition(SymbolDef("foo", "function", "m", 1))
        self.idx.add_definition(SymbolDef("Bar", "class", "m", 5))
        fns = self.idx.list_symbols(kind="function")
        self.assertEqual(len(fns), 1)
        self.assertEqual(fns[0].name, "foo")

    def test_list_symbols_kind_empty(self):
        self.idx.add_definition(SymbolDef("foo", "function", "m", 1))
        self.assertEqual(self.idx.list_symbols(kind="variable"), [])

    def test_clear(self):
        self.idx.add_definition(SymbolDef("foo", "function", "m", 1))
        self.idx.add_reference(SymbolRef("foo", "m", 2))
        self.idx.clear()
        self.assertEqual(len(self.idx), 0)
        self.assertEqual(self.idx.find_references("foo"), [])

    def test_multiple_kinds(self):
        for kind in ["class", "function", "variable", "import"]:
            self.idx.add_definition(SymbolDef(f"x_{kind}", kind, "m", 1))
        self.assertEqual(len(self.idx.list_symbols(kind="class")), 1)
        self.assertEqual(len(self.idx.list_symbols(kind="function")), 1)
        self.assertEqual(len(self.idx.list_symbols()), 4)

    def test_find_first_definition(self):
        self.idx.add_definition(SymbolDef("foo", "function", "mod1", 1))
        self.idx.add_definition(SymbolDef("foo", "function", "mod2", 5))
        first = self.idx.find_definition("foo")
        self.assertEqual(first.module, "mod1")

    def test_refs_not_counted_in_len(self):
        self.idx.add_reference(SymbolRef("x", "m", 1))
        self.idx.add_reference(SymbolRef("y", "m", 2))
        self.assertEqual(len(self.idx), 0)

    def test_list_symbols_none_kind(self):
        self.idx.add_definition(SymbolDef("a", "function", "m", 1))
        self.idx.add_definition(SymbolDef("b", "class", "m", 2))
        result = self.idx.list_symbols(kind=None)
        self.assertEqual(len(result), 2)

    def test_add_multiple_refs_same_name(self):
        self.idx.add_reference(SymbolRef("foo", "mod1", 1))
        self.idx.add_reference(SymbolRef("foo", "mod2", 2))
        refs = self.idx.find_references("foo")
        self.assertEqual(len(refs), 2)

    def test_clear_also_clears_refs(self):
        self.idx.add_definition(SymbolDef("a", "function", "m", 1))
        self.idx.add_reference(SymbolRef("a", "m", 5))
        self.idx.clear()
        self.assertEqual(self.idx.find_references("a"), [])
        self.assertIsNone(self.idx.find_definition("a"))


if __name__ == "__main__":
    unittest.main()
