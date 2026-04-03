"""Tests for APITestGenerator (Q256)."""
from __future__ import annotations

import unittest

from lidco.api_intel.extractor import Endpoint
from lidco.api_intel.test_gen import APITestGenerator, TestCase


class TestTestCase(unittest.TestCase):
    def test_frozen(self):
        tc = TestCase(name="t", method="GET", path="/x", expected_status=200)
        with self.assertRaises(AttributeError):
            tc.name = "y"  # type: ignore[misc]

    def test_defaults(self):
        tc = TestCase(name="t", method="GET", path="/x", expected_status=200)
        self.assertIsNone(tc.body)


class TestGenerateHappyPath(unittest.TestCase):
    def setUp(self):
        self.gen = APITestGenerator()

    def test_get_happy(self):
        ep = Endpoint(method="GET", path="/items")
        tc = self.gen.generate_happy_path(ep)
        self.assertIn("happy", tc.name)
        self.assertEqual(tc.method, "GET")
        self.assertEqual(tc.expected_status, 200)
        self.assertIsNone(tc.body)

    def test_post_happy_has_body(self):
        ep = Endpoint(method="POST", path="/items", params=({"name": "title", "type": "string", "in": "query"},))
        tc = self.gen.generate_happy_path(ep)
        self.assertIsNotNone(tc.body)
        self.assertIn("title", tc.body)

    def test_put_happy_has_body(self):
        ep = Endpoint(method="PUT", path="/items/{id}", params=({"name": "id", "in": "path"},))
        tc = self.gen.generate_happy_path(ep)
        self.assertIsNotNone(tc.body)

    def test_delete_no_body(self):
        ep = Endpoint(method="DELETE", path="/items/{id}")
        tc = self.gen.generate_happy_path(ep)
        self.assertIsNone(tc.body)


class TestGenerateErrorCases(unittest.TestCase):
    def setUp(self):
        self.gen = APITestGenerator()

    def test_path_param_generates_404(self):
        ep = Endpoint(method="GET", path="/items/{id}", params=({"name": "id", "in": "path"},))
        errors = self.gen.generate_error_cases(ep)
        statuses = [tc.expected_status for tc in errors]
        self.assertIn(404, statuses)

    def test_post_generates_400(self):
        ep = Endpoint(method="POST", path="/items")
        errors = self.gen.generate_error_cases(ep)
        statuses = [tc.expected_status for tc in errors]
        self.assertIn(400, statuses)

    def test_always_generates_405(self):
        ep = Endpoint(method="GET", path="/items")
        errors = self.gen.generate_error_cases(ep)
        statuses = [tc.expected_status for tc in errors]
        self.assertIn(405, statuses)

    def test_get_no_path_params_no_404(self):
        ep = Endpoint(method="GET", path="/items")
        errors = self.gen.generate_error_cases(ep)
        statuses = [tc.expected_status for tc in errors]
        self.assertNotIn(404, statuses)


class TestGenerate(unittest.TestCase):
    def setUp(self):
        self.gen = APITestGenerator()

    def test_generates_all(self):
        eps = [
            Endpoint(method="GET", path="/items"),
            Endpoint(method="POST", path="/items"),
        ]
        cases = self.gen.generate(eps)
        # Each has happy + error cases
        self.assertTrue(len(cases) >= 4)

    def test_empty(self):
        self.assertEqual(self.gen.generate([]), [])


class TestToPython(unittest.TestCase):
    def test_empty(self):
        code = APITestGenerator.to_python([])
        self.assertIn("class TestAPI", code)
        self.assertIn("pass", code)

    def test_with_cases(self):
        cases = [
            TestCase(name="test_get_items_happy", method="GET", path="/items", expected_status=200),
            TestCase(name="test_post_items_happy", method="POST", path="/items", expected_status=200, body={"title": "x"}),
        ]
        code = APITestGenerator.to_python(cases)
        self.assertIn("def test_get_items_happy", code)
        self.assertIn("def test_post_items_happy", code)
        self.assertIn("assertEqual", code)
        self.assertIn("200", code)

    def test_body_included_for_post(self):
        cases = [
            TestCase(name="test_post", method="POST", path="/x", expected_status=200, body={"a": 1}),
        ]
        code = APITestGenerator.to_python(cases)
        self.assertIn("json=body", code)

    def test_no_body_for_get(self):
        cases = [
            TestCase(name="test_get", method="GET", path="/x", expected_status=200),
        ]
        code = APITestGenerator.to_python(cases)
        self.assertNotIn("json=body", code)

    def test_integer_param_body(self):
        gen = APITestGenerator()
        ep = Endpoint(method="POST", path="/items", params=({"name": "count", "type": "int", "in": "query"},))
        tc = gen.generate_happy_path(ep)
        self.assertEqual(tc.body["count"], 1)

    def test_boolean_param_body(self):
        gen = APITestGenerator()
        ep = Endpoint(method="POST", path="/items", params=({"name": "active", "type": "bool", "in": "query"},))
        tc = gen.generate_happy_path(ep)
        self.assertTrue(tc.body["active"])


if __name__ == "__main__":
    unittest.main()
