"""Tests for DocstringGenerator, DocStyle, GeneratedDocstring."""
from __future__ import annotations

import unittest

from lidco.doc_intel.docstring_gen import DocStyle, DocstringGenerator, GeneratedDocstring


class TestDocStyleEnum(unittest.TestCase):
    def test_members(self):
        self.assertEqual(DocStyle.GOOGLE.value, "google")
        self.assertEqual(DocStyle.NUMPY.value, "numpy")
        self.assertEqual(DocStyle.SPHINX.value, "sphinx")

    def test_is_str(self):
        self.assertIsInstance(DocStyle.GOOGLE, str)


class TestGeneratedDocstringFrozen(unittest.TestCase):
    def test_creation(self):
        d = GeneratedDocstring(
            function_name="foo",
            docstring="Foo.",
            style=DocStyle.GOOGLE,
        )
        self.assertEqual(d.function_name, "foo")
        self.assertEqual(d.params, ())
        self.assertEqual(d.returns, "")

    def test_frozen(self):
        d = GeneratedDocstring(function_name="f", docstring="D", style=DocStyle.GOOGLE)
        with self.assertRaises(AttributeError):
            d.function_name = "other"  # type: ignore[misc]


class TestDocstringGeneratorGoogle(unittest.TestCase):
    def test_simple_function(self):
        src = "def greet(name: str) -> str:\n    return name"
        gen = DocstringGenerator(style=DocStyle.GOOGLE)
        result = gen.generate(src)
        self.assertEqual(result.function_name, "greet")
        self.assertIn("Args:", result.docstring)
        self.assertIn("name (str)", result.docstring)
        self.assertIn("Returns:", result.docstring)
        self.assertEqual(result.style, DocStyle.GOOGLE)
        self.assertEqual(result.params, (("name", "str"),))
        self.assertEqual(result.returns, "str")

    def test_no_params(self):
        src = "def noop() -> None:\n    pass"
        gen = DocstringGenerator()
        result = gen.generate(src)
        self.assertNotIn("Args:", result.docstring)
        self.assertEqual(result.params, ())

    def test_no_return(self):
        src = "def side(x: int):\n    pass"
        gen = DocstringGenerator()
        result = gen.generate(src)
        self.assertNotIn("Returns:", result.docstring)
        self.assertEqual(result.returns, "")

    def test_no_function_raises(self):
        with self.assertRaises(ValueError):
            DocstringGenerator().generate("x = 1")


class TestDocstringGeneratorNumpy(unittest.TestCase):
    def test_numpy_style(self):
        src = "def add(a: int, b: int) -> int:\n    return a + b"
        gen = DocstringGenerator(style=DocStyle.NUMPY)
        result = gen.generate(src)
        self.assertIn("Parameters", result.docstring)
        self.assertIn("----------", result.docstring)
        self.assertIn("a : int", result.docstring)
        self.assertIn("Returns", result.docstring)
        self.assertIn("-------", result.docstring)


class TestDocstringGeneratorSphinx(unittest.TestCase):
    def test_sphinx_style(self):
        src = "def calc(x: float) -> float:\n    return x"
        gen = DocstringGenerator(style=DocStyle.SPHINX)
        result = gen.generate(src)
        self.assertIn(":param x:", result.docstring)
        self.assertIn(":type x: float", result.docstring)
        self.assertIn(":rtype: float", result.docstring)


class TestSetStyleAndFormatParam(unittest.TestCase):
    def test_set_style(self):
        gen = DocstringGenerator(style=DocStyle.GOOGLE)
        gen.set_style(DocStyle.NUMPY)
        src = "def f(a: int) -> int:\n    return a"
        result = gen.generate(src)
        self.assertEqual(result.style, DocStyle.NUMPY)

    def test_format_param_google(self):
        gen = DocstringGenerator(style=DocStyle.GOOGLE)
        line = gen.format_param("x", "int", "The x coord.")
        self.assertIn("x (int): The x coord.", line)

    def test_format_param_sphinx(self):
        gen = DocstringGenerator(style=DocStyle.SPHINX)
        line = gen.format_param("x", "int")
        self.assertIn(":param x:", line)
        self.assertIn(":type x: int", line)


class TestGenerateForClass(unittest.TestCase):
    def test_class_methods(self):
        src = (
            "class Calc:\n"
            "    def add(self, a: int, b: int) -> int:\n"
            "        return a + b\n"
            "    def sub(self, a: int, b: int) -> int:\n"
            "        return a - b\n"
        )
        gen = DocstringGenerator()
        results = gen.generate_for_class(src)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].function_name, "add")
        self.assertEqual(results[1].function_name, "sub")
        # self is excluded from params
        for r in results:
            names = [p[0] for p in r.params]
            self.assertNotIn("self", names)

    def test_no_class_raises(self):
        with self.assertRaises(ValueError):
            DocstringGenerator().generate_for_class("x = 1")


if __name__ == "__main__":
    unittest.main()
