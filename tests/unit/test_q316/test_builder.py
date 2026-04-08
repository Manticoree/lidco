"""Tests for lidco.apitest.builder — task 1692."""

from __future__ import annotations

import unittest

from lidco.apitest.builder import (
    ApiRequest,
    ApiTestCase,
    ApiTestSuite,
    Assertion,
    AssertionBuilder,
    RequestBuilder,
    TestCaseBuilder,
    TestSuiteBuilder,
    interpolate,
    interpolate_request,
)


class TestAssertion(unittest.TestCase):
    """Test Assertion.evaluate with all operators."""

    def test_eq(self) -> None:
        a = Assertion(field="status", operator="eq", expected=200)
        self.assertTrue(a.evaluate(200))
        self.assertFalse(a.evaluate(404))

    def test_ne(self) -> None:
        a = Assertion(field="status", operator="ne", expected=200)
        self.assertTrue(a.evaluate(404))
        self.assertFalse(a.evaluate(200))

    def test_gt(self) -> None:
        a = Assertion(field="status", operator="gt", expected=100)
        self.assertTrue(a.evaluate(200))
        self.assertFalse(a.evaluate(50))

    def test_lt(self) -> None:
        a = Assertion(field="status", operator="lt", expected=300)
        self.assertTrue(a.evaluate(200))
        self.assertFalse(a.evaluate(400))

    def test_gte(self) -> None:
        a = Assertion(field="status", operator="gte", expected=200)
        self.assertTrue(a.evaluate(200))
        self.assertTrue(a.evaluate(201))
        self.assertFalse(a.evaluate(199))

    def test_lte(self) -> None:
        a = Assertion(field="status", operator="lte", expected=200)
        self.assertTrue(a.evaluate(200))
        self.assertTrue(a.evaluate(199))
        self.assertFalse(a.evaluate(201))

    def test_contains(self) -> None:
        a = Assertion(field="body", operator="contains", expected="hello")
        self.assertTrue(a.evaluate("hello world"))
        self.assertFalse(a.evaluate("goodbye"))
        self.assertFalse(a.evaluate(None))

    def test_matches(self) -> None:
        a = Assertion(field="body", operator="matches", expected=r"\d{3}")
        self.assertTrue(a.evaluate("code 200"))
        self.assertFalse(a.evaluate("none"))
        self.assertFalse(a.evaluate(None))

    def test_exists(self) -> None:
        a = Assertion(field="body", operator="exists")
        self.assertTrue(a.evaluate("something"))
        self.assertFalse(a.evaluate(None))

    def test_unknown_operator_raises(self) -> None:
        a = Assertion(field="x", operator="bogus")
        with self.assertRaises(ValueError):
            a.evaluate(42)


class TestInterpolate(unittest.TestCase):
    """Test variable interpolation."""

    def test_basic(self) -> None:
        self.assertEqual(
            interpolate("https://api.com/{{id}}", {"id": "123"}),
            "https://api.com/123",
        )

    def test_multiple(self) -> None:
        self.assertEqual(
            interpolate("{{host}}/{{path}}", {"host": "h", "path": "p"}),
            "h/p",
        )

    def test_missing_var_untouched(self) -> None:
        self.assertEqual(
            interpolate("{{missing}}", {}),
            "{{missing}}",
        )

    def test_spaces_in_braces(self) -> None:
        self.assertEqual(
            interpolate("{{ id }}", {"id": "42"}),
            "42",
        )


class TestInterpolateRequest(unittest.TestCase):
    """Test interpolate_request on ApiRequest fields."""

    def test_interpolates_url_and_headers(self) -> None:
        req = ApiRequest(
            method="GET",
            url="https://{{host}}/api",
            headers={"Authorization": "Bearer {{token}}"},
            query_params={"q": "{{query}}"},
        )
        result = interpolate_request(req, {"host": "example.com", "token": "abc", "query": "test"})
        self.assertEqual(result.url, "https://example.com/api")
        self.assertEqual(result.headers["Authorization"], "Bearer abc")
        self.assertEqual(result.query_params["q"], "test")

    def test_interpolates_dict_body(self) -> None:
        req = ApiRequest(body={"name": "{{name}}"})
        result = interpolate_request(req, {"name": "Alice"})
        self.assertEqual(result.body, {"name": "Alice"})

    def test_interpolates_list_body(self) -> None:
        req = ApiRequest(body=["{{a}}", "{{b}}"])
        result = interpolate_request(req, {"a": "1", "b": "2"})
        self.assertEqual(result.body, ["1", "2"])

    def test_none_body(self) -> None:
        req = ApiRequest(body=None)
        result = interpolate_request(req, {"x": "y"})
        self.assertIsNone(result.body)


class TestRequestBuilder(unittest.TestCase):
    """Test fluent RequestBuilder."""

    def test_build_defaults(self) -> None:
        req = RequestBuilder().build()
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.url, "")
        self.assertEqual(req.timeout, 30.0)

    def test_fluent_chain(self) -> None:
        req = (
            RequestBuilder()
            .method("POST")
            .url("https://api.com")
            .header("X-Custom", "val")
            .body({"key": "value"})
            .query("page", "1")
            .timeout(10.0)
            .build()
        )
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.url, "https://api.com")
        self.assertEqual(req.headers["X-Custom"], "val")
        self.assertEqual(req.body, {"key": "value"})
        self.assertEqual(req.query_params["page"], "1")
        self.assertEqual(req.timeout, 10.0)

    def test_immutability(self) -> None:
        b1 = RequestBuilder().url("a")
        b2 = b1.url("b")
        self.assertEqual(b1.build().url, "a")
        self.assertEqual(b2.build().url, "b")

    def test_headers_merge(self) -> None:
        req = (
            RequestBuilder()
            .header("A", "1")
            .headers({"B": "2", "C": "3"})
            .build()
        )
        self.assertEqual(req.headers, {"A": "1", "B": "2", "C": "3"})


class TestAssertionBuilder(unittest.TestCase):
    """Test AssertionBuilder."""

    def test_empty(self) -> None:
        self.assertEqual(AssertionBuilder().build(), ())

    def test_chain(self) -> None:
        assertions = (
            AssertionBuilder()
            .status_eq(200)
            .body_contains("ok")
            .body_field_eq("id", 1)
            .header_eq("Content-Type", "application/json")
            .header_contains("Content-Type", "json")
            .custom("status", "gte", 200)
            .build()
        )
        self.assertEqual(len(assertions), 6)
        self.assertEqual(assertions[0].field, "status")
        self.assertEqual(assertions[1].field, "body")
        self.assertEqual(assertions[2].field, "body.id")
        self.assertEqual(assertions[3].field, "header.Content-Type")

    def test_immutability(self) -> None:
        b1 = AssertionBuilder().status_eq(200)
        b2 = b1.body_contains("x")
        self.assertEqual(len(b1.build()), 1)
        self.assertEqual(len(b2.build()), 2)


class TestTestCaseBuilder(unittest.TestCase):
    """Test TestCaseBuilder."""

    def test_build(self) -> None:
        req = RequestBuilder().method("GET").url("/test").build()
        case = (
            TestCaseBuilder("my-test")
            .request(req)
            .assertions(AssertionBuilder().status_eq(200).build())
            .capture_var("user_id", "data.id")
            .build()
        )
        self.assertEqual(case.name, "my-test")
        self.assertEqual(case.request.url, "/test")
        self.assertEqual(len(case.assertions), 1)
        self.assertEqual(case.capture["user_id"], "data.id")

    def test_immutability(self) -> None:
        b1 = TestCaseBuilder("t").capture_var("a", "x")
        b2 = b1.capture_var("b", "y")
        self.assertNotIn("b", b1.build().capture)
        self.assertIn("b", b2.build().capture)


class TestTestSuiteBuilder(unittest.TestCase):
    """Test TestSuiteBuilder."""

    def test_build_empty(self) -> None:
        suite = TestSuiteBuilder("s").build()
        self.assertEqual(suite.name, "s")
        self.assertEqual(suite.cases, ())

    def test_add_cases_and_variables(self) -> None:
        case = TestCaseBuilder("c1").build()
        suite = (
            TestSuiteBuilder("suite")
            .add_case(case)
            .variable("host", "localhost")
            .build()
        )
        self.assertEqual(len(suite.cases), 1)
        self.assertEqual(suite.variables["host"], "localhost")

    def test_immutability(self) -> None:
        c1 = TestCaseBuilder("c1").build()
        c2 = TestCaseBuilder("c2").build()
        b1 = TestSuiteBuilder("s").add_case(c1)
        b2 = b1.add_case(c2)
        self.assertEqual(len(b1.build().cases), 1)
        self.assertEqual(len(b2.build().cases), 2)


if __name__ == "__main__":
    unittest.main()
