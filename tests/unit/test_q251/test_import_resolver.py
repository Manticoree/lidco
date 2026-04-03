"""Tests for ImportResolver (Q251)."""
from __future__ import annotations

import unittest

from lidco.completion.import_resolver import ImportResolver


class TestAddModule(unittest.TestCase):
    def test_add_single(self):
        r = ImportResolver()
        r.add_module("os.path", ["join", "exists", "basename"])
        self.assertEqual(r.resolve("join"), ["os.path"])

    def test_add_multiple(self):
        r = ImportResolver()
        r.add_module("os.path", ["join"])
        r.add_module("pathlib", ["Path"])
        self.assertEqual(r.resolve("Path"), ["pathlib"])


class TestResolve(unittest.TestCase):
    def test_found_single(self):
        r = ImportResolver()
        r.add_module("json", ["dumps", "loads"])
        self.assertEqual(r.resolve("dumps"), ["json"])

    def test_found_multiple(self):
        r = ImportResolver()
        r.add_module("os.path", ["join"])
        r.add_module("posixpath", ["join"])
        paths = r.resolve("join")
        self.assertEqual(len(paths), 2)
        self.assertIn("os.path", paths)
        self.assertIn("posixpath", paths)

    def test_not_found(self):
        r = ImportResolver()
        r.add_module("json", ["dumps"])
        self.assertEqual(r.resolve("loads"), [])

    def test_sorted(self):
        r = ImportResolver()
        r.add_module("zzz", ["Foo"])
        r.add_module("aaa", ["Foo"])
        self.assertEqual(r.resolve("Foo"), ["aaa", "zzz"])

    def test_empty_registry(self):
        r = ImportResolver()
        self.assertEqual(r.resolve("anything"), [])


class TestSuggest(unittest.TestCase):
    def test_basic(self):
        r = ImportResolver()
        r.add_module("collections", ["OrderedDict"])
        stmt = r.suggest("OrderedDict")
        self.assertEqual(stmt, "from collections import OrderedDict")

    def test_prefers_shortest_path(self):
        r = ImportResolver()
        r.add_module("a.b.c.d", ["Foo"])
        r.add_module("x", ["Foo"])
        stmt = r.suggest("Foo")
        self.assertEqual(stmt, "from x import Foo")

    def test_none_on_missing(self):
        r = ImportResolver()
        self.assertIsNone(r.suggest("Unknown"))


class TestDetectMissing(unittest.TestCase):
    def test_detects_missing(self):
        r = ImportResolver()
        r.add_module("typing", ["Optional", "List"])
        source = "x: Optional[List[int]] = None"
        missing = r.detect_missing(source)
        self.assertIn("Optional", missing)
        self.assertIn("List", missing)

    def test_excludes_known(self):
        r = ImportResolver()
        r.add_module("typing", ["Optional", "List"])
        source = "x: Optional[List[int]] = None"
        missing = r.detect_missing(source, known_imports={"Optional"})
        self.assertNotIn("Optional", missing)
        self.assertIn("List", missing)

    def test_no_false_positives(self):
        r = ImportResolver()
        r.add_module("typing", ["Optional"])
        source = "x = 1 + 2"
        missing = r.detect_missing(source)
        self.assertEqual(missing, [])

    def test_empty_source(self):
        r = ImportResolver()
        self.assertEqual(r.detect_missing(""), [])

    def test_only_capitalized_names(self):
        r = ImportResolver()
        r.add_module("builtins", ["print"])
        # "print" is lowercase — detect_missing only looks for capitalized names
        source = "print('hello')"
        missing = r.detect_missing(source)
        self.assertEqual(missing, [])

    def test_sorted_output(self):
        r = ImportResolver()
        r.add_module("typing", ["Callable", "Any"])
        source = "f: Callable[[Any], Any]"
        missing = r.detect_missing(source)
        self.assertEqual(missing, sorted(missing))


if __name__ == "__main__":
    unittest.main()
