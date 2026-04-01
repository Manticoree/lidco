"""Tests for docgen.magic_docs — DocSection, MagicDocsGenerator."""
from __future__ import annotations

import os
import tempfile
import unittest

from lidco.docgen.magic_docs import DocSection, MagicDocsGenerator


class TestDocSection(unittest.TestCase):
    def test_frozen(self):
        s = DocSection(title="T", content="C", level=1)
        with self.assertRaises(AttributeError):
            s.title = "X"  # type: ignore[misc]

    def test_fields(self):
        s = DocSection("Title", "Body", 2)
        self.assertEqual(s.title, "Title")
        self.assertEqual(s.content, "Body")
        self.assertEqual(s.level, 2)

    def test_equality(self):
        a = DocSection("T", "C", 1)
        b = DocSection("T", "C", 1)
        self.assertEqual(a, b)


class TestMagicDocsGenerator(unittest.TestCase):
    def _write_temp(self, code):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
        f.write(code)
        f.close()
        return f.name

    def test_generate_from_file(self):
        path = self._write_temp('"""Module doc."""\ndef foo(): pass\n')
        try:
            gen = MagicDocsGenerator()
            sections = gen.generate(path)
            self.assertIsInstance(sections, tuple)
            self.assertGreater(len(sections), 0)
        finally:
            os.unlink(path)

    def test_generate_module_docstring(self):
        path = self._write_temp('"""My module."""\n')
        try:
            gen = MagicDocsGenerator()
            sections = gen.generate(path)
            titles = [s.title for s in sections]
            self.assertIn("Module Overview", titles)
        finally:
            os.unlink(path)

    def test_generate_class(self):
        path = self._write_temp('class Foo:\n    """A class."""\n    pass\n')
        try:
            gen = MagicDocsGenerator()
            sections = gen.generate(path)
            titles = [s.title for s in sections]
            self.assertTrue(any("Foo" in t for t in titles))
        finally:
            os.unlink(path)

    def test_generate_function(self):
        path = self._write_temp('def bar(x: int) -> str:\n    """A func."""\n    return str(x)\n')
        try:
            gen = MagicDocsGenerator()
            sections = gen.generate(path)
            titles = [s.title for s in sections]
            self.assertTrue(any("bar" in t for t in titles))
        finally:
            os.unlink(path)

    def test_generate_nonexistent_file(self):
        gen = MagicDocsGenerator()
        sections = gen.generate("/nonexistent/path.py")
        self.assertEqual(sections, ())

    def test_extract_signatures(self):
        gen = MagicDocsGenerator()
        code = "def add(a: int, b: int) -> int:\n    return a + b\n"
        sigs = gen.extract_signatures(code)
        self.assertIsInstance(sigs, tuple)
        self.assertEqual(len(sigs), 1)
        self.assertIn("add", sigs[0])
        self.assertIn("int", sigs[0])

    def test_extract_signatures_empty(self):
        gen = MagicDocsGenerator()
        self.assertEqual(gen.extract_signatures("x = 1\n"), ())

    def test_extract_signatures_syntax_error(self):
        gen = MagicDocsGenerator()
        self.assertEqual(gen.extract_signatures("def :::"), ())

    def test_generate_examples(self):
        gen = MagicDocsGenerator()
        code = "def greet(name, greeting):\n    pass\n"
        examples = gen.generate_examples("greet", code)
        self.assertIsInstance(examples, tuple)
        self.assertEqual(len(examples), 1)
        self.assertIn("greet(name, greeting)", examples[0])

    def test_generate_examples_not_found(self):
        gen = MagicDocsGenerator()
        examples = gen.generate_examples("missing", "def other(): pass\n")
        self.assertEqual(examples, ())

    def test_format_markdown(self):
        gen = MagicDocsGenerator()
        sections = (
            DocSection("Title", "Content", 1),
            DocSection("Sub", "Detail", 2),
        )
        md = gen.format_markdown(sections)
        self.assertIn("# Title", md)
        self.assertIn("## Sub", md)
        self.assertIn("Content", md)

    def test_format_markdown_empty(self):
        gen = MagicDocsGenerator()
        self.assertEqual(gen.format_markdown(()), "")

    def test_generate_async_function(self):
        path = self._write_temp('async def afoo(): pass\n')
        try:
            gen = MagicDocsGenerator()
            sections = gen.generate(path)
            titles = [s.title for s in sections]
            self.assertTrue(any("async" in t.lower() for t in titles))
        finally:
            os.unlink(path)

    def test_extract_signatures_method(self):
        gen = MagicDocsGenerator()
        code = "class C:\n    def method(self, x: str) -> None:\n        pass\n"
        sigs = gen.extract_signatures(code)
        self.assertTrue(any("method" in s for s in sigs))

    def test_section_level_3_for_functions(self):
        path = self._write_temp('def f(): pass\n')
        try:
            gen = MagicDocsGenerator()
            sections = gen.generate(path)
            func_sections = [s for s in sections if "f" in s.title]
            self.assertTrue(any(s.level == 3 for s in func_sections))
        finally:
            os.unlink(path)

    def test_section_level_2_for_classes(self):
        path = self._write_temp('class C: pass\n')
        try:
            gen = MagicDocsGenerator()
            sections = gen.generate(path)
            cls_sections = [s for s in sections if "C" in s.title]
            self.assertTrue(any(s.level == 2 for s in cls_sections))
        finally:
            os.unlink(path)

    def test_doc_section_different_not_equal(self):
        a = DocSection("A", "C", 1)
        b = DocSection("B", "C", 1)
        self.assertNotEqual(a, b)


class TestMagicDocsAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.docgen import magic_docs

        self.assertIn("DocSection", magic_docs.__all__)
        self.assertIn("MagicDocsGenerator", magic_docs.__all__)


if __name__ == "__main__":
    unittest.main()
