"""Tests for scope_analyzer — Q125."""
from __future__ import annotations
import unittest
from lidco.analysis.scope_analyzer import Scope, ScopeAnalyzer


class TestScope(unittest.TestCase):
    def test_creation(self):
        s = Scope(name="mymod", kind="module", parent=None)
        self.assertEqual(s.name, "mymod")
        self.assertEqual(s.kind, "module")
        self.assertIsNone(s.parent)
        self.assertEqual(s.symbols, [])
        self.assertEqual(s.line, 0)


class TestScopeAnalyzer(unittest.TestCase):
    def setUp(self):
        self.sa = ScopeAnalyzer()

    def test_empty_source(self):
        scopes = self.sa.analyze("")
        self.assertEqual(len(scopes), 1)
        self.assertEqual(scopes[0].kind, "module")

    def test_module_scope_always_first(self):
        scopes = self.sa.analyze("x = 1", module_name="mymod")
        self.assertEqual(scopes[0].kind, "module")
        self.assertEqual(scopes[0].name, "mymod")

    def test_function_creates_scope(self):
        src = "def foo(): pass"
        scopes = self.sa.analyze(src)
        kinds = [s.kind for s in scopes]
        self.assertIn("function", kinds)

    def test_class_creates_scope(self):
        src = "class Bar: pass"
        scopes = self.sa.analyze(src)
        kinds = [s.kind for s in scopes]
        self.assertIn("class", kinds)

    def test_module_symbols_contain_function(self):
        src = "def foo(): pass"
        scopes = self.sa.analyze(src, module_name="<module>")
        mod = scopes[0]
        self.assertIn("foo", mod.symbols)

    def test_module_symbols_contain_class(self):
        src = "class Foo: pass"
        scopes = self.sa.analyze(src, module_name="<module>")
        mod = scopes[0]
        self.assertIn("Foo", mod.symbols)

    def test_module_symbols_contain_variable(self):
        src = "x = 42"
        scopes = self.sa.analyze(src, module_name="<module>")
        mod = scopes[0]
        self.assertIn("x", mod.symbols)

    def test_syntax_error_returns_empty(self):
        scopes = self.sa.analyze("def foo(")
        self.assertEqual(scopes, [])

    def test_find_scope_found(self):
        src = "def foo(): pass"
        scopes = self.sa.analyze(src, module_name="<module>")
        fn_scope = self.sa.find_scope("foo", scopes)
        self.assertIsNotNone(fn_scope)
        self.assertEqual(fn_scope.kind, "function")

    def test_find_scope_not_found(self):
        scopes = self.sa.analyze("x = 1")
        self.assertIsNone(self.sa.find_scope("nonexistent", scopes))

    def test_children_of_module(self):
        src = "def foo(): pass\nclass Bar: pass"
        scopes = self.sa.analyze(src, module_name="<module>")
        children = self.sa.children("<module>", scopes)
        # foo and Bar are children of module
        child_names = [c.name for c in children]
        self.assertIn("foo", child_names)
        self.assertIn("Bar", child_names)

    def test_class_scope_line(self):
        src = "\n\nclass Foo: pass"
        scopes = self.sa.analyze(src)
        cls_scope = self.sa.find_scope("Foo", scopes)
        self.assertIsNotNone(cls_scope)
        self.assertGreater(cls_scope.line, 0)

    def test_function_scope_parent(self):
        src = "def bar(): pass"
        scopes = self.sa.analyze(src, module_name="<module>")
        fn = self.sa.find_scope("bar", scopes)
        self.assertIsNotNone(fn)
        self.assertEqual(fn.parent, "<module>")

    def test_class_scope_parent(self):
        src = "class Baz: pass"
        scopes = self.sa.analyze(src, module_name="<module>")
        cls = self.sa.find_scope("Baz", scopes)
        self.assertIsNotNone(cls)
        self.assertEqual(cls.parent, "<module>")

    def test_no_children_for_unknown(self):
        scopes = self.sa.analyze("x = 1")
        self.assertEqual(self.sa.children("nobody", scopes), [])

    def test_multiple_functions(self):
        src = "def a(): pass\ndef b(): pass"
        scopes = self.sa.analyze(src)
        fn_names = [s.name for s in scopes if s.kind == "function"]
        self.assertIn("a", fn_names)
        self.assertIn("b", fn_names)

    def test_function_with_args_in_symbols(self):
        src = "def f(a, b): pass"
        scopes = self.sa.analyze(src)
        fn = self.sa.find_scope("f", scopes)
        self.assertIsNotNone(fn)
        self.assertIn("a", fn.symbols)
        self.assertIn("b", fn.symbols)

    def test_class_methods_in_symbols(self):
        src = "class Foo:\n    def method(self): pass"
        scopes = self.sa.analyze(src)
        cls = self.sa.find_scope("Foo", scopes)
        self.assertIsNotNone(cls)
        self.assertIn("method", cls.symbols)


if __name__ == "__main__":
    unittest.main()
