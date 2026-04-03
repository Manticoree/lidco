"""API test case generation from endpoints."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.api_intel.extractor import Endpoint


@dataclass(frozen=True)
class TestCase:
    """A generated API test case."""

    name: str
    method: str
    path: str
    expected_status: int
    body: dict | None = None


class APITestGenerator:
    """Generate test cases from API endpoints."""

    def generate(self, endpoints: list[Endpoint]) -> list[TestCase]:
        """Generate all test cases (happy + error) for all endpoints."""
        cases: list[TestCase] = []
        for ep in endpoints:
            cases = [*cases, self.generate_happy_path(ep)]
            for err in self.generate_error_cases(ep):
                cases = [*cases, err]
        return cases

    def generate_happy_path(self, endpoint: Endpoint) -> TestCase:
        """Generate a happy-path test case for an endpoint."""
        name = self._make_name(endpoint, "happy")
        body = None
        if endpoint.method.upper() in ("POST", "PUT", "PATCH"):
            body = self._make_request_body(endpoint)
        return TestCase(
            name=name,
            method=endpoint.method,
            path=endpoint.path,
            expected_status=200,
            body=body,
        )

    def generate_error_cases(self, endpoint: Endpoint) -> list[TestCase]:
        """Generate error test cases for an endpoint."""
        cases: list[TestCase] = []
        # 404 for endpoints with path params
        path_params = [p for p in endpoint.params if p.get("in") == "path"]
        if path_params:
            cases = [*cases, TestCase(
                name=self._make_name(endpoint, "not_found"),
                method=endpoint.method,
                path=endpoint.path,
                expected_status=404,
            )]
        # 400 for POST/PUT/PATCH with missing body
        if endpoint.method.upper() in ("POST", "PUT", "PATCH"):
            cases = [*cases, TestCase(
                name=self._make_name(endpoint, "bad_request"),
                method=endpoint.method,
                path=endpoint.path,
                expected_status=400,
                body={},
            )]
        # 405 method not allowed
        cases = [*cases, TestCase(
            name=self._make_name(endpoint, "method_not_allowed"),
            method="OPTIONS",
            path=endpoint.path,
            expected_status=405,
        )]
        return cases

    @staticmethod
    def _make_name(endpoint: Endpoint, scenario: str) -> str:
        """Generate a test name from endpoint and scenario."""
        path_part = endpoint.path.strip("/").replace("/", "_").replace("{", "").replace("}", "").replace("-", "_")
        if not path_part:
            path_part = "root"
        return f"test_{endpoint.method.lower()}_{path_part}_{scenario}"

    @staticmethod
    def _make_request_body(endpoint: Endpoint) -> dict:
        """Generate a sample request body from endpoint params."""
        body: dict = {}
        for p in endpoint.params:
            if p.get("in") != "path":
                name = p["name"]
                ptype = p.get("type", "string")
                if ptype in ("int", "integer", "number"):
                    body = {**body, name: 1}
                elif ptype in ("bool", "boolean"):
                    body = {**body, name: True}
                else:
                    body = {**body, name: f"test_{name}"}
        return body

    @staticmethod
    def to_python(test_cases: list[TestCase]) -> str:
        """Generate Python test code from test cases."""
        lines = [
            '"""Auto-generated API tests."""',
            "import unittest",
            "",
            "",
            "class TestAPI(unittest.TestCase):",
        ]
        if not test_cases:
            lines.append("    pass")
            return "\n".join(lines) + "\n"

        for tc in test_cases:
            lines.append(f"    def {tc.name}(self):")
            lines.append(f'        """Test {tc.method} {tc.path} -> {tc.expected_status}."""')
            if tc.body is not None:
                lines.append(f"        body = {tc.body!r}")
                lines.append(
                    f"        response = self.client.{tc.method.lower()}("
                    f'"{tc.path}", json=body)'
                )
            else:
                lines.append(
                    f"        response = self.client.{tc.method.lower()}("
                    f'"{tc.path}")'
                )
            lines.append(
                f"        self.assertEqual(response.status_code, {tc.expected_status})"
            )
            lines.append("")

        return "\n".join(lines) + "\n"
