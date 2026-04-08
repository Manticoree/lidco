"""API Test Builder — task 1692.

Build API test cases with request builder, assertion builder,
chained requests, and variable interpolation.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Sequence


# ---------------------------------------------------------------------------
# Data structures (frozen where possible)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Assertion:
    """Single assertion on an API response."""

    field: str  # e.g. "status", "body.id", "header.Content-Type"
    operator: str  # eq, ne, gt, lt, gte, lte, contains, matches, exists
    expected: Any = None

    def evaluate(self, actual: Any) -> bool:
        """Return *True* if the assertion passes."""
        ops = {
            "eq": lambda a, e: a == e,
            "ne": lambda a, e: a != e,
            "gt": lambda a, e: a > e,
            "lt": lambda a, e: a < e,
            "gte": lambda a, e: a >= e,
            "lte": lambda a, e: a <= e,
            "contains": lambda a, e: e in a if a is not None else False,
            "matches": lambda a, e: bool(re.search(e, str(a))) if a is not None else False,
            "exists": lambda a, _e: a is not None,
        }
        fn = ops.get(self.operator)
        if fn is None:
            raise ValueError(f"Unknown operator: {self.operator}")
        return fn(actual, self.expected)


@dataclass(frozen=True)
class ApiRequest:
    """Immutable description of a single HTTP request."""

    method: str = "GET"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None
    query_params: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0


@dataclass(frozen=True)
class ApiTestCase:
    """Immutable test case: request + assertions + variable capture."""

    name: str
    request: ApiRequest
    assertions: tuple[Assertion, ...] = ()
    capture: dict[str, str] = field(default_factory=dict)  # var_name -> json path


@dataclass(frozen=True)
class ApiTestSuite:
    """Ordered collection of test cases (possibly chained)."""

    name: str
    cases: tuple[ApiTestCase, ...] = ()
    variables: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Variable interpolation
# ---------------------------------------------------------------------------

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def interpolate(text: str, variables: dict[str, str]) -> str:
    """Replace ``{{var}}`` placeholders in *text*."""

    def _replace(m: re.Match[str]) -> str:
        key = m.group(1)
        return variables.get(key, m.group(0))

    return _VAR_RE.sub(_replace, text)


def interpolate_request(request: ApiRequest, variables: dict[str, str]) -> ApiRequest:
    """Return a new *ApiRequest* with variables resolved."""
    return ApiRequest(
        method=request.method,
        url=interpolate(request.url, variables),
        headers={k: interpolate(v, variables) for k, v in request.headers.items()},
        body=_interpolate_body(request.body, variables),
        query_params={k: interpolate(v, variables) for k, v in request.query_params.items()},
        timeout=request.timeout,
    )


def _interpolate_body(body: Any, variables: dict[str, str]) -> Any:
    if body is None:
        return None
    if isinstance(body, str):
        return interpolate(body, variables)
    if isinstance(body, dict):
        return {k: _interpolate_body(v, variables) for k, v in body.items()}
    if isinstance(body, list):
        return [_interpolate_body(item, variables) for item in body]
    return body


# ---------------------------------------------------------------------------
# Builders (fluent API)
# ---------------------------------------------------------------------------

class RequestBuilder:
    """Fluent builder for *ApiRequest*."""

    def __init__(self) -> None:
        self._method: str = "GET"
        self._url: str = ""
        self._headers: dict[str, str] = {}
        self._body: Any = None
        self._query_params: dict[str, str] = {}
        self._timeout: float = 30.0

    # -- setters (return new builder via copy) --

    def method(self, method: str) -> RequestBuilder:
        b = self._copy()
        b._method = method.upper()
        return b

    def url(self, url: str) -> RequestBuilder:
        b = self._copy()
        b._url = url
        return b

    def header(self, key: str, value: str) -> RequestBuilder:
        b = self._copy()
        b._headers = {**b._headers, key: value}
        return b

    def headers(self, headers: dict[str, str]) -> RequestBuilder:
        b = self._copy()
        b._headers = {**b._headers, **headers}
        return b

    def body(self, body: Any) -> RequestBuilder:
        b = self._copy()
        b._body = body
        return b

    def query(self, key: str, value: str) -> RequestBuilder:
        b = self._copy()
        b._query_params = {**b._query_params, key: value}
        return b

    def timeout(self, seconds: float) -> RequestBuilder:
        b = self._copy()
        b._timeout = seconds
        return b

    def build(self) -> ApiRequest:
        return ApiRequest(
            method=self._method,
            url=self._url,
            headers=dict(self._headers),
            body=copy.deepcopy(self._body),
            query_params=dict(self._query_params),
            timeout=self._timeout,
        )

    # -- internal --

    def _copy(self) -> RequestBuilder:
        b = RequestBuilder()
        b._method = self._method
        b._url = self._url
        b._headers = dict(self._headers)
        b._body = copy.deepcopy(self._body)
        b._query_params = dict(self._query_params)
        b._timeout = self._timeout
        return b


class AssertionBuilder:
    """Collect assertions for a test case."""

    def __init__(self) -> None:
        self._assertions: tuple[Assertion, ...] = ()

    def status_eq(self, code: int) -> AssertionBuilder:
        return self._add(Assertion(field="status", operator="eq", expected=code))

    def body_contains(self, text: str) -> AssertionBuilder:
        return self._add(Assertion(field="body", operator="contains", expected=text))

    def body_field_eq(self, path: str, value: Any) -> AssertionBuilder:
        return self._add(Assertion(field=f"body.{path}", operator="eq", expected=value))

    def header_eq(self, name: str, value: str) -> AssertionBuilder:
        return self._add(Assertion(field=f"header.{name}", operator="eq", expected=value))

    def header_contains(self, name: str, value: str) -> AssertionBuilder:
        return self._add(Assertion(field=f"header.{name}", operator="contains", expected=value))

    def custom(self, field: str, operator: str, expected: Any = None) -> AssertionBuilder:
        return self._add(Assertion(field=field, operator=operator, expected=expected))

    def build(self) -> tuple[Assertion, ...]:
        return self._assertions

    def _add(self, a: Assertion) -> AssertionBuilder:
        b = AssertionBuilder()
        b._assertions = (*self._assertions, a)
        return b


class TestCaseBuilder:
    """Build a single *ApiTestCase*."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._request: ApiRequest = ApiRequest()
        self._assertions: tuple[Assertion, ...] = ()
        self._capture: dict[str, str] = {}

    def request(self, req: ApiRequest) -> TestCaseBuilder:
        b = self._copy()
        b._request = req
        return b

    def assertions(self, assertions: tuple[Assertion, ...] | Sequence[Assertion]) -> TestCaseBuilder:
        b = self._copy()
        b._assertions = tuple(assertions)
        return b

    def capture_var(self, var_name: str, json_path: str) -> TestCaseBuilder:
        b = self._copy()
        b._capture = {**b._capture, var_name: json_path}
        return b

    def build(self) -> ApiTestCase:
        return ApiTestCase(
            name=self._name,
            request=self._request,
            assertions=self._assertions,
            capture=dict(self._capture),
        )

    def _copy(self) -> TestCaseBuilder:
        b = TestCaseBuilder(self._name)
        b._request = self._request
        b._assertions = self._assertions
        b._capture = dict(self._capture)
        return b


class TestSuiteBuilder:
    """Build an *ApiTestSuite*."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._cases: tuple[ApiTestCase, ...] = ()
        self._variables: dict[str, str] = {}

    def add_case(self, case: ApiTestCase) -> TestSuiteBuilder:
        b = self._copy()
        b._cases = (*b._cases, case)
        return b

    def variable(self, key: str, value: str) -> TestSuiteBuilder:
        b = self._copy()
        b._variables = {**b._variables, key: value}
        return b

    def build(self) -> ApiTestSuite:
        return ApiTestSuite(
            name=self._name,
            cases=self._cases,
            variables=dict(self._variables),
        )

    def _copy(self) -> TestSuiteBuilder:
        b = TestSuiteBuilder(self._name)
        b._cases = self._cases
        b._variables = dict(self._variables)
        return b
