"""Tests for MockGeneratorV2 (Q253)."""
from __future__ import annotations

import unittest

from lidco.testgen.mock_gen import MockGeneratorV2, MockSpec


class TestMockSpec(unittest.TestCase):
    def test_frozen(self):
        spec = MockSpec(name="Foo")
        with self.assertRaises(AttributeError):
            spec.name = "Bar"  # type: ignore[misc]

    def test_defaults(self):
        spec = MockSpec(name="Foo")
        self.assertEqual(spec.methods, [])
        self.assertEqual(spec.return_values, {})

    def test_with_methods(self):
        spec = MockSpec(name="Svc", methods=[{"name": "run", "params": []}])
        self.assertEqual(len(spec.methods), 1)


class TestGenerate(unittest.TestCase):
    def setUp(self):
        self.gen = MockGeneratorV2()

    def test_empty_mock(self):
        spec = MockSpec(name="Empty")
        code = self.gen.generate(spec)
        self.assertIn("class MockEmpty", code)
        self.assertIn("pass", code)

    def test_with_methods(self):
        spec = MockSpec(
            name="Calculator",
            methods=[
                {"name": "add", "params": ["a", "b"]},
                {"name": "reset", "params": []},
            ],
        )
        code = self.gen.generate(spec)
        self.assertIn("class MockCalculator", code)
        self.assertIn("def add(self, a, b)", code)
        self.assertIn("def reset(self)", code)
        self.assertIn("_calls", code)

    def test_async_method(self):
        spec = MockSpec(
            name="Client",
            methods=[{"name": "fetch", "params": ["url"], "is_async": True}],
        )
        code = self.gen.generate(spec)
        self.assertIn("async def fetch", code)

    def test_return_values(self):
        spec = MockSpec(
            name="Svc",
            methods=[{"name": "get", "params": []}],
            return_values={"get": 42},
        )
        code = self.gen.generate(spec)
        self.assertIn("42", code)

    def test_records_calls(self):
        spec = MockSpec(
            name="Db",
            methods=[{"name": "query", "params": ["sql"]}],
        )
        code = self.gen.generate(spec)
        self.assertIn("_calls", code)
        self.assertIn("'query'", code)


class TestFromInterface(unittest.TestCase):
    def setUp(self):
        self.gen = MockGeneratorV2()

    def test_basic(self):
        source = (
            "class Repo:\n"
            "    def find(self, id):\n"
            "        pass\n"
            "    def save(self, item):\n"
            "        pass\n"
        )
        spec = self.gen.from_interface(source, "Repo")
        self.assertEqual(spec.name, "Repo")
        names = [m["name"] for m in spec.methods]
        self.assertIn("find", names)
        self.assertIn("save", names)

    def test_skips_private(self):
        source = "class X:\n    def _priv(self):\n        pass\n    def pub(self):\n        pass\n"
        spec = self.gen.from_interface(source, "X")
        names = [m["name"] for m in spec.methods]
        self.assertNotIn("_priv", names)
        self.assertIn("pub", names)

    def test_async_detected(self):
        source = "class S:\n    async def fetch(self, url):\n        pass\n"
        spec = self.gen.from_interface(source, "S")
        self.assertTrue(spec.methods[0]["is_async"])

    def test_class_not_found(self):
        spec = self.gen.from_interface("class A:\n    pass\n", "Missing")
        self.assertEqual(spec.name, "Missing")
        self.assertEqual(spec.methods, [])

    def test_bad_syntax(self):
        spec = self.gen.from_interface("def (broken", "X")
        self.assertEqual(spec.methods, [])

    def test_params_extracted(self):
        source = "class R:\n    def find(self, id, name):\n        pass\n"
        spec = self.gen.from_interface(source, "R")
        self.assertEqual(spec.methods[0]["params"], ["id", "name"])


class TestGenerateSpy(unittest.TestCase):
    def setUp(self):
        self.gen = MockGeneratorV2()

    def test_empty_spy(self):
        spec = MockSpec(name="Empty")
        code = self.gen.generate_spy(spec)
        self.assertIn("class SpyEmpty", code)
        self.assertIn("pass", code)

    def test_spy_with_methods(self):
        spec = MockSpec(
            name="Logger",
            methods=[{"name": "log", "params": ["msg"]}],
        )
        code = self.gen.generate_spy(spec)
        self.assertIn("class SpyLogger", code)
        self.assertIn("call_log", code)
        self.assertIn("def log(self, msg)", code)

    def test_spy_records_args(self):
        spec = MockSpec(
            name="Svc",
            methods=[{"name": "do", "params": ["x", "y"]}],
        )
        code = self.gen.generate_spy(spec)
        self.assertIn("call_log", code)
        self.assertIn("'method'", code)

    def test_spy_async(self):
        spec = MockSpec(
            name="Cl",
            methods=[{"name": "fetch", "params": [], "is_async": True}],
        )
        code = self.gen.generate_spy(spec)
        self.assertIn("async def fetch", code)


if __name__ == "__main__":
    unittest.main()
