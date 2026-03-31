"""Tests for cross_reference — Q125."""
from __future__ import annotations
import unittest
from lidco.analysis.symbol_index2 import SymbolDef, SymbolRef, SymbolIndex
from lidco.analysis.cross_reference import CrossReference


def make_index(defs=None, refs=None):
    idx = SymbolIndex()
    for d in (defs or []):
        idx.add_definition(d)
    for r in (refs or []):
        idx.add_reference(r)
    return idx


class TestCrossReference(unittest.TestCase):
    def test_find_usages_empty(self):
        xref = CrossReference(make_index())
        self.assertEqual(xref.find_usages("foo"), [])

    def test_find_usages(self):
        idx = make_index(
            refs=[SymbolRef("foo", "mod", 5), SymbolRef("bar", "mod", 6)]
        )
        xref = CrossReference(idx)
        self.assertEqual(len(xref.find_usages("foo")), 1)

    def test_find_definition(self):
        idx = make_index(defs=[SymbolDef("foo", "function", "mod", 1)])
        xref = CrossReference(idx)
        result = xref.find_definition("foo")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "foo")

    def test_find_definition_missing(self):
        xref = CrossReference(make_index())
        self.assertIsNone(xref.find_definition("bar"))

    def test_unused_definitions_all_unused(self):
        idx = make_index(defs=[
            SymbolDef("foo", "function", "m", 1),
            SymbolDef("bar", "class", "m", 5),
        ])
        xref = CrossReference(idx)
        unused = xref.unused_definitions()
        names = [u.name for u in unused]
        self.assertIn("foo", names)
        self.assertIn("bar", names)

    def test_unused_definitions_with_ref(self):
        idx = make_index(
            defs=[SymbolDef("foo", "function", "m", 1)],
            refs=[SymbolRef("foo", "m", 10)],
        )
        xref = CrossReference(idx)
        self.assertEqual(xref.unused_definitions(), [])

    def test_undefined_references(self):
        idx = make_index(refs=[SymbolRef("undefined_fn", "m", 5)])
        xref = CrossReference(idx)
        undef = xref.undefined_references()
        self.assertEqual(len(undef), 1)
        self.assertEqual(undef[0].name, "undefined_fn")

    def test_undefined_references_empty_when_defined(self):
        idx = make_index(
            defs=[SymbolDef("foo", "function", "m", 1)],
            refs=[SymbolRef("foo", "m", 10)],
        )
        xref = CrossReference(idx)
        self.assertEqual(xref.undefined_references(), [])

    def test_summary_empty(self):
        xref = CrossReference(make_index())
        s = xref.summary()
        self.assertEqual(s["defined"], 0)
        self.assertEqual(s["referenced"], 0)
        self.assertEqual(s["unused"], 0)
        self.assertEqual(s["undefined"], 0)

    def test_summary_keys(self):
        xref = CrossReference(make_index())
        s = xref.summary()
        for key in ("defined", "referenced", "unused", "undefined"):
            self.assertIn(key, s)

    def test_summary_counts(self):
        idx = make_index(
            defs=[
                SymbolDef("foo", "function", "m", 1),
                SymbolDef("bar", "function", "m", 5),
            ],
            refs=[
                SymbolRef("foo", "m", 10),
                SymbolRef("baz", "m", 20),
            ],
        )
        xref = CrossReference(idx)
        s = xref.summary()
        self.assertEqual(s["defined"], 2)
        self.assertEqual(s["referenced"], 2)
        self.assertEqual(s["unused"], 1)   # bar is unused
        self.assertEqual(s["undefined"], 1)  # baz is undefined

    def test_find_multiple_usages(self):
        idx = make_index(refs=[
            SymbolRef("foo", "m1", 1),
            SymbolRef("foo", "m2", 2),
            SymbolRef("foo", "m3", 3),
        ])
        xref = CrossReference(idx)
        self.assertEqual(len(xref.find_usages("foo")), 3)

    def test_mixed_defined_and_referenced(self):
        idx = make_index(
            defs=[SymbolDef("x", "variable", "m", 1)],
            refs=[SymbolRef("x", "m", 5)],
        )
        xref = CrossReference(idx)
        self.assertEqual(xref.unused_definitions(), [])
        self.assertEqual(xref.undefined_references(), [])

    def test_summary_undefined_count(self):
        idx = make_index(
            refs=[SymbolRef("a", "m", 1), SymbolRef("b", "m", 2)]
        )
        xref = CrossReference(idx)
        s = xref.summary()
        self.assertEqual(s["undefined"], 2)

    def test_multiple_refs_to_defined(self):
        idx = make_index(
            defs=[SymbolDef("foo", "function", "m", 1)],
            refs=[SymbolRef("foo", "m", 5), SymbolRef("foo", "m", 10)],
        )
        xref = CrossReference(idx)
        self.assertEqual(xref.unused_definitions(), [])


if __name__ == "__main__":
    unittest.main()
