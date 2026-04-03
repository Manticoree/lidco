"""Tests for SmellCatalog — Q254."""

from __future__ import annotations

import unittest

from lidco.smells.catalog import SmellCatalog, SmellDef


class TestSmellDef(unittest.TestCase):
    """SmellDef dataclass basics."""

    def test_create_minimal(self):
        s = SmellDef(id="x", name="X", severity="low", description="desc")
        self.assertEqual(s.id, "x")
        self.assertEqual(s.language, "any")
        self.assertEqual(s.fix_template, "")

    def test_create_full(self):
        s = SmellDef("y", "Y", "high", "d", language="python", fix_template="fix it")
        self.assertEqual(s.language, "python")
        self.assertEqual(s.fix_template, "fix it")

    def test_frozen(self):
        s = SmellDef("z", "Z", "medium", "d")
        with self.assertRaises(AttributeError):
            s.id = "other"  # type: ignore[misc]


class TestSmellCatalogRegister(unittest.TestCase):
    """register / get basics."""

    def test_register_and_get(self):
        cat = SmellCatalog()
        s = SmellDef("a", "A", "low", "desc")
        cat.register(s)
        self.assertIs(cat.get("a"), s)

    def test_get_missing_returns_none(self):
        cat = SmellCatalog()
        self.assertIsNone(cat.get("nope"))

    def test_register_override(self):
        cat = SmellCatalog()
        s1 = SmellDef("a", "A1", "low", "d1")
        s2 = SmellDef("a", "A2", "high", "d2")
        cat.register(s1)
        cat.register(s2)
        self.assertEqual(cat.get("a").name, "A2")


class TestSmellCatalogQueries(unittest.TestCase):
    """by_severity / by_language / list_all."""

    def setUp(self):
        self.cat = SmellCatalog()
        self.cat.register(SmellDef("a", "A", "high", "d", language="python"))
        self.cat.register(SmellDef("b", "B", "low", "d", language="any"))
        self.cat.register(SmellDef("c", "C", "high", "d", language="javascript"))

    def test_by_severity(self):
        highs = self.cat.by_severity("high")
        self.assertEqual(len(highs), 2)
        ids = {s.id for s in highs}
        self.assertEqual(ids, {"a", "c"})

    def test_by_severity_empty(self):
        self.assertEqual(self.cat.by_severity("critical"), [])

    def test_by_language_specific(self):
        py = self.cat.by_language("python")
        ids = {s.id for s in py}
        # "any" language smells also match
        self.assertIn("a", ids)
        self.assertIn("b", ids)
        self.assertNotIn("c", ids)

    def test_by_language_any(self):
        any_smells = self.cat.by_language("any")
        # only exact "any" language
        ids = {s.id for s in any_smells}
        self.assertIn("b", ids)

    def test_list_all(self):
        self.assertEqual(len(self.cat.list_all()), 3)


class TestSmellCatalogWithDefaults(unittest.TestCase):
    """with_defaults factory."""

    def test_has_defaults(self):
        cat = SmellCatalog.with_defaults()
        smells = cat.list_all()
        self.assertGreaterEqual(len(smells), 10)

    def test_long_method_present(self):
        cat = SmellCatalog.with_defaults()
        self.assertIsNotNone(cat.get("long_method"))

    def test_god_class_present(self):
        cat = SmellCatalog.with_defaults()
        self.assertIsNotNone(cat.get("god_class"))

    def test_magic_number_present(self):
        cat = SmellCatalog.with_defaults()
        self.assertIsNotNone(cat.get("magic_number"))

    def test_dead_code_present(self):
        cat = SmellCatalog.with_defaults()
        self.assertIsNotNone(cat.get("dead_code"))

    def test_deep_nesting_present(self):
        cat = SmellCatalog.with_defaults()
        self.assertIsNotNone(cat.get("deep_nesting"))

    def test_defaults_have_severity(self):
        cat = SmellCatalog.with_defaults()
        for s in cat.list_all():
            self.assertIn(s.severity, ("critical", "high", "medium", "low"))


if __name__ == "__main__":
    unittest.main()
