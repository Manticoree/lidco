"""API Test Runner — task 1693.

Execute API tests sequentially or in parallel, with environment
variables, auth handling, and retry support.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lidco.apitest.builder import (
    ApiRequest,
    ApiTestCase,
    ApiTestSuite,
    Assertion,
    interpolate_request,
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssertionResult:
    """Outcome of a single assertion."""

    assertion: Assertion
    passed: bool
    actual: Any = None
    error: str = ""


@dataclass(frozen=True)
class TestCaseResult:
    """Outcome of a single test case execution."""

    name: str
    passed: bool
    status_code: int = 0
    response_body: Any = None
    response_headers: dict[str, str] = field(default_factory=dict)
    assertion_results: tuple[AssertionResult, ...] = ()
    duration_ms: float = 0.0
    error: str = ""
    captured: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SuiteResult:
    """Outcome of a full test suite run."""

    name: str
    passed: bool
    total: int
    passed_count: int
    failed_count: int
    results: tuple[TestCaseResult, ...] = ()
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration."""

    auth_type: str = "none"  # none | bearer | basic | header
    token: str = ""
    username: str = ""
    password: str = ""
    header_name: str = "Authorization"
    header_value: str = ""

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        """Return new headers dict with auth applied."""
        if self.auth_type == "bearer":
            return {**headers, "Authorization": f"Bearer {self.token}"}
        if self.auth_type == "basic":
            import base64

            cred = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {**headers, "Authorization": f"Basic {cred}"}
        if self.auth_type == "header":
            return {**headers, self.header_name: self.header_value}
        return dict(headers)


# ---------------------------------------------------------------------------
# Response field extraction
# ---------------------------------------------------------------------------

def _resolve_field(
    field_path: str,
    status_code: int,
    body: Any,
    headers: dict[str, str],
) -> Any:
    """Resolve a dotted *field_path* against the response."""
    if field_path == "status":
        return status_code
    if field_path == "body":
        return body if isinstance(body, str) else json.dumps(body) if body is not None else None
    if field_path.startswith("body."):
        return _resolve_json_path(field_path[5:], body)
    if field_path.startswith("header."):
        hdr_name = field_path[7:]
        # Case-insensitive header lookup
        for k, v in headers.items():
            if k.lower() == hdr_name.lower():
                return v
        return None
    return None


def _resolve_json_path(path: str, obj: Any) -> Any:
    """Simple dot-notation resolver over dicts / lists."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

@dataclass
class RunnerConfig:
    """Configuration for the test runner."""

    parallel: bool = False
    max_workers: int = 4
    auth: AuthConfig = field(default_factory=AuthConfig)
    env: dict[str, str] = field(default_factory=dict)
    retries: int = 0
    retry_delay: float = 0.5
    base_url: str = ""


class ApiTestRunner:
    """Execute *ApiTestSuite* instances."""

    def __init__(self, config: RunnerConfig | None = None) -> None:
        self._config = config or RunnerConfig()

    @property
    def config(self) -> RunnerConfig:
        return self._config

    # -- public API ---------------------------------------------------------

    def run_suite(self, suite: ApiTestSuite) -> SuiteResult:
        """Run all cases in *suite* and return aggregated result."""
        variables: dict[str, str] = {
            **self._config.env,
            **suite.variables,
        }
        start = time.monotonic()
        if self._config.parallel:
            results = self._run_parallel(suite, variables)
        else:
            results = self._run_sequential(suite, variables)
        elapsed = (time.monotonic() - start) * 1000

        passed_count = sum(1 for r in results if r.passed)
        return SuiteResult(
            name=suite.name,
            passed=passed_count == len(results),
            total=len(results),
            passed_count=passed_count,
            failed_count=len(results) - passed_count,
            results=tuple(results),
            duration_ms=round(elapsed, 2),
        )

    def run_case(self, case: ApiTestCase, variables: dict[str, str] | None = None) -> TestCaseResult:
        """Run a single test case."""
        variables = dict(variables or {})
        return self._execute_case(case, variables)

    # -- internal -----------------------------------------------------------

    def _run_sequential(
        self, suite: ApiTestSuite, variables: dict[str, str]
    ) -> list[TestCaseResult]:
        results: list[TestCaseResult] = []
        vars_mut = dict(variables)
        for case in suite.cases:
            result = self._execute_case(case, vars_mut)
            # Merge captured variables for chaining
            vars_mut = {**vars_mut, **result.captured}
            results.append(result)
        return results

    def _run_parallel(
        self, suite: ApiTestSuite, variables: dict[str, str]
    ) -> list[TestCaseResult]:
        results: list[TestCaseResult] = [None] * len(suite.cases)  # type: ignore[list-item]
        with ThreadPoolExecutor(max_workers=self._config.max_workers) as pool:
            future_to_idx = {
                pool.submit(self._execute_case, case, dict(variables)): idx
                for idx, case in enumerate(suite.cases)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()
        return results

    def _execute_case(
        self, case: ApiTestCase, variables: dict[str, str]
    ) -> TestCaseResult:
        req = interpolate_request(case.request, variables)
        # Prepend base_url if URL is relative
        url = req.url
        if self._config.base_url and not url.startswith(("http://", "https://")):
            url = self._config.base_url.rstrip("/") + "/" + url.lstrip("/")

        headers = self._config.auth.apply(req.headers)

        attempts = max(1, self._config.retries + 1)
        last_error = ""
        for attempt in range(attempts):
            try:
                result = self._do_request(url, req.method, headers, req.body, req.query_params, req.timeout)
                # Evaluate assertions
                assertion_results = self._evaluate_assertions(
                    case.assertions, result["status"], result["body"], result["headers"]
                )
                all_passed = all(ar.passed for ar in assertion_results)

                # Capture variables
                captured: dict[str, str] = {}
                for var_name, json_path in case.capture.items():
                    val = _resolve_json_path(json_path, result["body"])
                    if val is not None:
                        captured[var_name] = str(val)

                return TestCaseResult(
                    name=case.name,
                    passed=all_passed,
                    status_code=result["status"],
                    response_body=result["body"],
                    response_headers=result["headers"],
                    assertion_results=tuple(assertion_results),
                    duration_ms=result["duration_ms"],
                    captured=captured,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt < attempts - 1:
                    time.sleep(self._config.retry_delay)

        return TestCaseResult(
            name=case.name,
            passed=False,
            error=last_error,
        )

    def _do_request(
        self,
        url: str,
        method: str,
        headers: dict[str, str],
        body: Any,
        query_params: dict[str, str],
        timeout: float,
    ) -> dict[str, Any]:
        """Perform HTTP request via stdlib urllib."""
        if query_params:
            from urllib.parse import urlencode

            qs = urlencode(query_params)
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{qs}"

        data: bytes | None = None
        if body is not None:
            if isinstance(body, str):
                data = body.encode("utf-8")
            else:
                data = json.dumps(body).encode("utf-8")
                headers = {**headers, "Content-Type": "application/json"}

        req = Request(url, data=data, headers=headers, method=method)
        start = time.monotonic()
        try:
            with urlopen(req, timeout=timeout) as resp:
                elapsed = (time.monotonic() - start) * 1000
                raw = resp.read().decode("utf-8", errors="replace")
                resp_headers = {k: v for k, v in resp.getheaders()}
                status = resp.status
        except HTTPError as exc:
            elapsed = (time.monotonic() - start) * 1000
            raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            resp_headers = {k: v for k, v in exc.headers.items()} if exc.headers else {}
            status = exc.code

        # Attempt JSON parse
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            parsed = raw

        return {
            "status": status,
            "body": parsed,
            "headers": resp_headers,
            "duration_ms": round(elapsed, 2),
        }

    def _evaluate_assertions(
        self,
        assertions: tuple[Assertion, ...],
        status: int,
        body: Any,
        headers: dict[str, str],
    ) -> list[AssertionResult]:
        results: list[AssertionResult] = []
        for assertion in assertions:
            actual = _resolve_field(assertion.field, status, body, headers)
            try:
                passed = assertion.evaluate(actual)
            except Exception as exc:  # noqa: BLE001
                results.append(AssertionResult(
                    assertion=assertion, passed=False, actual=actual, error=str(exc),
                ))
                continue
            results.append(AssertionResult(assertion=assertion, passed=passed, actual=actual))
        return results
