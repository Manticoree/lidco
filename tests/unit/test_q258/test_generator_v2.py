"""Tests for DocGeneratorV2 (Q258)."""
from __future__ import annotations

import unittest

from lidco.docgen.generator_v2 import DocGeneratorV2, DocSection


class TestDocSection(unittest.TestCase):
    def test_dataclass_fields(self):
        s = DocSection(title="Intro", content="Hello", source_file="mod.py")
        self.assertEqual(s.title, "Intro")
        self.assertEqual(s.content, "Hello")
        self.assertEqual(s.source_file, "mod.py")

    def test_frozen(self):
        s = DocSection(title="X", content="Y")
        with self.assertRaises(AttributeError):
            s.title = "Z"  # type: ignore[misc]

    def test_default_source_file(self):
        s = DocSection(title="X", content="Y")
        self.assertEqual(s.source_file, "")


class TestGenerateModule(unittest.TestCase):
    def setUp(self):
        self.gen = DocGeneratorV2()

    def test_basic_module(self):
        src = '"""Module doc."""\ndef foo():\n    """Foo doc."""\n    pass\n'
        md = self.gen.generate_module(src, "mymod")
        self.assertIn("# Module `mymod`", md)
        self.assertIn("Module doc.", md)
        self.assertIn("foo", md)

    def test_module_with_class(self):
        src = 'class Bar:\n    """Bar class."""\n    pass\n'
        md = self.gen.generate_module(src, "m")
        self.assertIn("Bar", md)
        self.assertIn("Bar class.", md)

    def test_empty_module(self):
        md = self.gen.generate_module("", "empty")
        self.assertIn("# Module `empty`", md)

    def test_syntax_error(self):
        with self.assertRaises(ValueError):
            self.gen.generate_module("def (broken", "bad")


class TestGenerateFunction(unittest.TestCase):
    def setUp(self):
        self.gen = DocGeneratorV2()

    def test_basic_function(self):
        src = 'def add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b\n'
        md = self.gen.generate_function(src, "add")
        self.assertIn("add", md)
        self.assertIn("int", md)
        self.assertIn("Add two numbers.", md)
        self.assertIn("**Parameters:**", md)
        self.assertIn("`a`", md)
        self.assertIn("**Returns:**", md)

    def test_function_not_found(self):
        md = self.gen.generate_function("def foo(): pass\n", "bar")
        self.assertIn("not found", md)

    def test_no_annotations(self):
        src = "def greet(name):\n    pass\n"
        md = self.gen.generate_function(src, "greet")
        self.assertIn("greet", md)
        self.assertIn("`name`", md)
        self.assertNotIn("**Returns:**", md)

    def test_no_params(self):
        src = 'def noop() -> None:\n    """Nothing."""\n    pass\n'
        md = self.gen.generate_function(src, "noop")
        self.assertNotIn("**Parameters:**", md)

    def test_async_function(self):
        src = 'async def fetch(url: str) -> str:\n    """Fetch URL."""\n    return ""\n'
        md = self.gen.generate_function(src, "fetch")
        self.assertIn("fetch", md)
        self.assertIn("url", md)


class TestGenerateClass(unittest.TestCase):
    def setUp(self):
        self.gen = DocGeneratorV2()

    def test_basic_class(self):
        src = (
            'class Dog:\n'
            '    """A dog."""\n'
            '    def bark(self):\n'
            '        """Woof."""\n'
            '        pass\n'
        )
        md = self.gen.generate_class(src, "Dog")
        self.assertIn("Dog", md)
        self.assertIn("A dog.", md)
        self.assertIn("bark", md)

    def test_class_with_bases(self):
        src = 'class Cat(Animal):\n    """A cat."""\n    pass\n'
        md = self.gen.generate_class(src, "Cat")
        self.assertIn("Animal", md)

    def test_class_not_found(self):
        md = self.gen.generate_class("class Foo: pass\n", "Bar")
        self.assertIn("not found", md)


class TestAddExamples(unittest.TestCase):
    def setUp(self):
        self.gen = DocGeneratorV2()

    def test_add_examples(self):
        doc = "Some function doc."
        result = self.gen.add_examples(doc, ["print('hello')", "x = 1 + 2"])
        self.assertIn("**Examples:**", result)
        self.assertIn("```python", result)
        self.assertIn("print('hello')", result)
        self.assertIn("x = 1 + 2", result)

    def test_empty_examples(self):
        doc = "Doc."
        result = self.gen.add_examples(doc, [])
        self.assertEqual(result, doc)


class TestToMarkdown(unittest.TestCase):
    def setUp(self):
        self.gen = DocGeneratorV2()

    def test_single_section(self):
        sections = [DocSection(title="Intro", content="Welcome.")]
        md = self.gen.to_markdown(sections)
        self.assertIn("## Intro", md)
        self.assertIn("Welcome.", md)

    def test_multiple_sections(self):
        sections = [
            DocSection(title="A", content="First."),
            DocSection(title="B", content="Second.", source_file="b.py"),
        ]
        md = self.gen.to_markdown(sections)
        self.assertIn("## A", md)
        self.assertIn("## B", md)
        self.assertIn("*Source: b.py*", md)

    def test_empty_sections(self):
        md = self.gen.to_markdown([])
        self.assertEqual(md.strip(), "")


if __name__ == "__main__":
    unittest.main()
