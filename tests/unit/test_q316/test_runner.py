"""Tests for lidco.apitest.runner — task 1693."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from lidco.apitest.builder import (
    ApiRequest,
    ApiTestCase,
    ApiTestSuite,
    Assertion,
)
from lidco.apitest.runner import (
    ApiTestRunner,
    AssertionResult,
    AuthConfig,
    RunnerConfig,
    SuiteResult,
    TestCaseResult,
    _resolve_field,
    _resolve_json_path,
)


class TestResolveJsonPath(unittest.TestCase):
    """Test _resolve_json_path helper."""

    def test_simple_key(self) -> None:
        self.assertEqual(_resolve_json_path("id", {"id": 42}), 42)

    def test_nested(self) -> None:
        self.assertEqual(_resolve_json_path("a.b.c", {"a": {"b": {"c": 1}}}), 1)

    def test_list_index(self) -> None:
        self.assertEqual(_resolve_json_path("items.0", {"items": [10, 20]}), 10)

    def test_missing_returns_none(self) -> None:
        self.assertIsNone(_resolve_json_path("x.y", {"x": {}}))

    def test_none_obj(self) -> None:
        self.assertIsNone(_resolve_json_path("x", None))


class TestResolveField(unittest.TestCase):
    """Test _resolve_field helper."""

    def test_status(self) -> None:
        self.assertEqual(_resolve_field("status", 200, None, {}), 200)

    def test_body_string(self) -> None:
        self.assertEqual(_resolve_field("body", 200, "hello", {}), "hello")

    def test_body_dict(self) -> None:
        result = _resolve_field("body", 200, {"k": "v"}, {})
        self.assertIn("k", result)

    def test_body_none(self) -> None:
        self.assertIsNone(_resolve_field("body", 200, None, {}))

    def test_body_dot_path(self) -> None:
        self.assertEqual(_resolve_field("body.data.id", 200, {"data": {"id": 7}}, {}), 7)

    def test_header(self) -> None:
        self.assertEqual(
            _resolve_field("header.Content-Type", 200, None, {"Content-Type": "text/html"}),
            "text/html",
        )

    def test_header_case_insensitive(self) -> None:
        self.assertEqual(
            _resolve_field("header.content-type", 200, None, {"Content-Type": "text/html"}),
            "text/html",
        )

    def test_unknown_field(self) -> None:
        self.assertIsNone(_resolve_field("unknown", 200, None, {}))


class TestAuthConfig(unittest.TestCase):
    """Test AuthConfig.apply."""

    def test_none(self) -> None:
        auth = AuthConfig(auth_type="none")
        self.assertEqual(auth.apply({"X": "1"}), {"X": "1"})

    def test_bearer(self) -> None:
        auth = AuthConfig(auth_type="bearer", token="tok123")
        headers = auth.apply({})
        self.assertEqual(headers["Authorization"], "Bearer tok123")

    def test_basic(self) -> None:
        import base64
        auth = AuthConfig(auth_type="basic", username="user", password="pass")
        headers = auth.apply({})
        expected = base64.b64encode(b"user:pass").decode()
        self.assertEqual(headers["Authorization"], f"Basic {expected}")

    def test_header(self) -> None:
        auth = AuthConfig(auth_type="header", header_name="X-API-Key", header_value="secret")
        headers = auth.apply({})
        self.assertEqual(headers["X-API-Key"], "secret")


class TestRunnerConfig(unittest.TestCase):
    """Test RunnerConfig defaults."""

    def test_defaults(self) -> None:
        cfg = RunnerConfig()
        self.assertFalse(cfg.parallel)
        self.assertEqual(cfg.max_workers, 4)
        self.assertEqual(cfg.retries, 0)
        self.assertEqual(cfg.base_url, "")


class TestApiTestRunner(unittest.TestCase):
    """Test ApiTestRunner with mocked HTTP."""

    def _make_mock_response(
        self,
        status: int = 200,
        body: str = '{"ok":true}',
        headers: dict[str, str] | None = None,
    ) -> MagicMock:
        resp = MagicMock()
        resp.status = status
        resp.read.return_value = body.encode("utf-8")
        resp.getheaders.return_value = list((headers or {"Content-Type": "application/json"}).items())
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    @patch("lidco.apitest.runner.urlopen")
    def test_run_suite_pass(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._make_mock_response(200, '{"id":1}')

        case = ApiTestCase(
            name="get-user",
            request=ApiRequest(method="GET", url="http://localhost/user"),
            assertions=(Assertion(field="status", operator="eq", expected=200),),
        )
        suite = ApiTestSuite(name="test-suite", cases=(case,))
        runner = ApiTestRunner()
        result = runner.run_suite(suite)

        self.assertTrue(result.passed)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.passed_count, 1)
        self.assertEqual(result.failed_count, 0)

    @patch("lidco.apitest.runner.urlopen")
    def test_run_suite_fail(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._make_mock_response(500)

        case = ApiTestCase(
            name="fail-case",
            request=ApiRequest(method="GET", url="http://localhost/err"),
            assertions=(Assertion(field="status", operator="eq", expected=200),),
        )
        suite = ApiTestSuite(name="fail-suite", cases=(case,))
        runner = ApiTestRunner()
        result = runner.run_suite(suite)

        self.assertFalse(result.passed)
        self.assertEqual(result.failed_count, 1)

    @patch("lidco.apitest.runner.urlopen")
    def test_variable_capture(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._make_mock_response(200, '{"data":{"token":"abc"}}')

        case = ApiTestCase(
            name="login",
            request=ApiRequest(method="POST", url="http://localhost/login"),
            capture={"auth_token": "data.token"},
        )
        suite = ApiTestSuite(name="cap-suite", cases=(case,))
        runner = ApiTestRunner()
        result = runner.run_suite(suite)

        self.assertEqual(result.results[0].captured.get("auth_token"), "abc")

    @patch("lidco.apitest.runner.urlopen")
    def test_base_url_prepend(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._make_mock_response(200)

        case = ApiTestCase(
            name="rel",
            request=ApiRequest(method="GET", url="/api/test"),
        )
        suite = ApiTestSuite(name="s", cases=(case,))
        runner = ApiTestRunner(RunnerConfig(base_url="http://base.com"))
        runner.run_suite(suite)

        call_args = mock_urlopen.call_args
        req_obj = call_args[0][0]
        self.assertTrue(req_obj.full_url.startswith("http://base.com/api/test"))

    @patch("lidco.apitest.runner.urlopen")
    def test_parallel_execution(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._make_mock_response(200)

        cases = tuple(
            ApiTestCase(name=f"c{i}", request=ApiRequest(method="GET", url="http://localhost/"))
            for i in range(3)
        )
        suite = ApiTestSuite(name="par", cases=cases)
        runner = ApiTestRunner(RunnerConfig(parallel=True, max_workers=2))
        result = runner.run_suite(suite)

        self.assertEqual(result.total, 3)
        self.assertTrue(result.passed)

    @patch("lidco.apitest.runner.urlopen")
    def test_retry_on_failure(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = [
            Exception("conn error"),
            self._make_mock_response(200),
        ]

        case = ApiTestCase(
            name="retry-test",
            request=ApiRequest(method="GET", url="http://localhost/retry"),
            assertions=(Assertion(field="status", operator="eq", expected=200),),
        )
        suite = ApiTestSuite(name="r", cases=(case,))
        runner = ApiTestRunner(RunnerConfig(retries=1, retry_delay=0.0))
        result = runner.run_suite(suite)

        self.assertTrue(result.passed)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("lidco.apitest.runner.urlopen")
    def test_retry_exhausted(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = Exception("always fail")

        case = ApiTestCase(
            name="exhaust",
            request=ApiRequest(method="GET", url="http://localhost/x"),
        )
        suite = ApiTestSuite(name="e", cases=(case,))
        runner = ApiTestRunner(RunnerConfig(retries=1, retry_delay=0.0))
        result = runner.run_suite(suite)

        self.assertFalse(result.passed)
        self.assertIn("always fail", result.results[0].error)

    @patch("lidco.apitest.runner.urlopen")
    def test_run_case_standalone(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._make_mock_response(201)

        case = ApiTestCase(
            name="single",
            request=ApiRequest(method="POST", url="http://localhost/create"),
            assertions=(Assertion(field="status", operator="eq", expected=201),),
        )
        runner = ApiTestRunner()
        result = runner.run_case(case)

        self.assertTrue(result.passed)
        self.assertEqual(result.status_code, 201)

    @patch("lidco.apitest.runner.urlopen")
    def test_query_params(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._make_mock_response(200)

        case = ApiTestCase(
            name="qs",
            request=ApiRequest(method="GET", url="http://localhost/search", query_params={"q": "hello"}),
        )
        runner = ApiTestRunner()
        runner.run_case(case)

        call_args = mock_urlopen.call_args
        req_obj = call_args[0][0]
        self.assertIn("q=hello", req_obj.full_url)

    @patch("lidco.apitest.runner.urlopen")
    def test_env_variables_merged(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = self._make_mock_response(200)

        case = ApiTestCase(
            name="env",
            request=ApiRequest(method="GET", url="http://{{host}}/api"),
        )
        suite = ApiTestSuite(name="e", cases=(case,), variables={"host": "override.com"})
        runner = ApiTestRunner(RunnerConfig(env={"host": "env.com"}))
        result = runner.run_suite(suite)

        # Suite variables override env
        call_args = mock_urlopen.call_args
        req_obj = call_args[0][0]
        self.assertIn("override.com", req_obj.full_url)


class TestAssertionResult(unittest.TestCase):
    """Test AssertionResult frozen dataclass."""

    def test_creation(self) -> None:
        ar = AssertionResult(
            assertion=Assertion(field="status", operator="eq", expected=200),
            passed=True,
            actual=200,
        )
        self.assertTrue(ar.passed)
        self.assertEqual(ar.actual, 200)


if __name__ == "__main__":
    unittest.main()
