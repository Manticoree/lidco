"""Tests for CrossLanguageLinker (Q250)."""
from __future__ import annotations

import unittest

from lidco.polyglot.linker import CrossLanguageLinker, Link
from lidco.polyglot.parser import Symbol


class TestLink(unittest.TestCase):
    def test_frozen(self):
        src = Symbol(name="x", kind="function", language="python")
        tgt = Symbol(name="x", kind="function", language="go")
        link = Link(source=src, target=tgt, link_type="name_match")
        with self.assertRaises(AttributeError):
            link.link_type = "other"  # type: ignore[misc]

    def test_fields(self):
        src = Symbol(name="a", kind="class", language="java")
        tgt = Symbol(name="a", kind="class", language="typescript")
        link = Link(source=src, target=tgt, link_type="api_boundary")
        self.assertEqual(link.source.language, "java")
        self.assertEqual(link.target.language, "typescript")
        self.assertEqual(link.link_type, "api_boundary")


class TestFindLinks(unittest.TestCase):
    def setUp(self):
        self.linker = CrossLanguageLinker()

    def test_cross_language_match(self):
        self.linker.add_symbols([
            Symbol(name="process", kind="function", language="python", line=1),
            Symbol(name="process", kind="function", language="javascript", line=5),
        ])
        links = self.linker.find_links()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].link_type, "name_match")
        self.assertEqual(links[0].source.language, "python")
        self.assertEqual(links[0].target.language, "javascript")

    def test_same_language_no_link(self):
        self.linker.add_symbols([
            Symbol(name="foo", kind="function", language="python"),
            Symbol(name="foo", kind="class", language="python"),
        ])
        links = self.linker.find_links()
        self.assertEqual(len(links), 0)

    def test_no_match(self):
        self.linker.add_symbols([
            Symbol(name="alpha", kind="function", language="python"),
            Symbol(name="beta", kind="function", language="go"),
        ])
        links = self.linker.find_links()
        self.assertEqual(len(links), 0)

    def test_multiple_languages(self):
        self.linker.add_symbols([
            Symbol(name="init", kind="function", language="python"),
            Symbol(name="init", kind="function", language="go"),
            Symbol(name="init", kind="function", language="rust"),
        ])
        links = self.linker.find_links()
        self.assertEqual(len(links), 3)  # py-go, py-rs, go-rs

    def test_add_symbols_immutable(self):
        batch1 = [Symbol(name="a", kind="function", language="python")]
        batch2 = [Symbol(name="a", kind="function", language="go")]
        self.linker.add_symbols(batch1)
        self.linker.add_symbols(batch2)
        links = self.linker.find_links()
        self.assertEqual(len(links), 1)

    def test_no_duplicate_links(self):
        self.linker.add_symbols([
            Symbol(name="x", kind="function", language="python"),
            Symbol(name="x", kind="function", language="go"),
        ])
        links1 = self.linker.find_links()
        links2 = self.linker.find_links()
        self.assertEqual(len(links1), len(links2))


class TestFindApiBoundaries(unittest.TestCase):
    def setUp(self):
        self.linker = CrossLanguageLinker()

    def test_api_functions(self):
        self.linker.add_symbols([
            Symbol(name="handle", kind="function", language="python"),
            Symbol(name="handle", kind="function", language="javascript"),
        ])
        links = self.linker.find_api_boundaries()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].link_type, "api_boundary")

    def test_non_api_kinds_excluded(self):
        self.linker.add_symbols([
            Symbol(name="MAX", kind="macro", language="c"),
            Symbol(name="MAX", kind="variable", language="javascript"),
        ])
        links = self.linker.find_api_boundaries()
        self.assertEqual(len(links), 0)

    def test_methods_included(self):
        self.linker.add_symbols([
            Symbol(name="run", kind="method", language="go"),
            Symbol(name="run", kind="function", language="python"),
        ])
        links = self.linker.find_api_boundaries()
        self.assertEqual(len(links), 1)

    def test_empty(self):
        self.assertEqual(self.linker.find_api_boundaries(), [])


class TestSummary(unittest.TestCase):
    def test_no_links(self):
        linker = CrossLanguageLinker()
        self.assertEqual(linker.summary(), "No cross-language links found.")

    def test_with_links(self):
        linker = CrossLanguageLinker()
        linker.add_symbols([
            Symbol(name="run", kind="function", language="python"),
            Symbol(name="run", kind="function", language="go"),
        ])
        s = linker.summary()
        self.assertIn("1 cross-language link(s)", s)
        self.assertIn("2 language(s)", s)
        self.assertIn("python:run", s)
        self.assertIn("go:run", s)
        self.assertIn("name_match", s)

    def test_multiple_links(self):
        linker = CrossLanguageLinker()
        linker.add_symbols([
            Symbol(name="a", kind="function", language="python"),
            Symbol(name="a", kind="function", language="go"),
            Symbol(name="b", kind="class", language="java"),
            Symbol(name="b", kind="class", language="rust"),
        ])
        s = linker.summary()
        self.assertIn("2 cross-language link(s)", s)


if __name__ == "__main__":
    unittest.main()
