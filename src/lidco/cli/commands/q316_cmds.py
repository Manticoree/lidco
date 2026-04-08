"""
Q316 CLI commands — /api-test, /api-run, /api-mock, /api-report

Registered via register_q316_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q316_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q316 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /api-test — Build and show an API test case
    # ------------------------------------------------------------------
    async def api_test_handler(args: str) -> str:
        """
        Usage: /api-test <method> <url> [--header K:V] [--body JSON]
                         [--assert-status CODE] [--assert-body-contains TEXT]
                         [--name NAME]
        """
        from lidco.apitest.builder import (
            AssertionBuilder,
            RequestBuilder,
            TestCaseBuilder,
        )

        parts = shlex.split(args) if args.strip() else []
        if len(parts) < 2:
            return "Usage: /api-test <method> <url> [--header K:V] [--body JSON] [--assert-status CODE] [--name NAME]"

        method = parts[0].upper()
        url = parts[1]
        headers: dict[str, str] = {}
        body: str | None = None
        assert_status: int | None = None
        assert_body_contains: str | None = None
        name = "test"

        i = 2
        while i < len(parts):
            if parts[i] == "--header" and i + 1 < len(parts):
                k, _, v = parts[i + 1].partition(":")
                headers[k.strip()] = v.strip()
                i += 2
            elif parts[i] == "--body" and i + 1 < len(parts):
                body = parts[i + 1]
                i += 2
            elif parts[i] == "--assert-status" and i + 1 < len(parts):
                try:
                    assert_status = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--assert-body-contains" and i + 1 < len(parts):
                assert_body_contains = parts[i + 1]
                i += 2
            elif parts[i] == "--name" and i + 1 < len(parts):
                name = parts[i + 1]
                i += 2
            else:
                i += 1

        rb = RequestBuilder().method(method).url(url)
        for k, v in headers.items():
            rb = rb.header(k, v)
        if body is not None:
            rb = rb.body(body)

        ab = AssertionBuilder()
        if assert_status is not None:
            ab = ab.status_eq(assert_status)
        if assert_body_contains is not None:
            ab = ab.body_contains(assert_body_contains)

        case = (
            TestCaseBuilder(name)
            .request(rb.build())
            .assertions(ab.build())
            .build()
        )

        lines = [
            f"Test case '{case.name}':",
            f"  {case.request.method} {case.request.url}",
        ]
        if case.request.headers:
            lines.append(f"  Headers: {case.request.headers}")
        if case.request.body:
            lines.append(f"  Body: {case.request.body}")
        if case.assertions:
            lines.append(f"  Assertions: {len(case.assertions)}")
            for a in case.assertions:
                lines.append(f"    {a.field} {a.operator} {a.expected!r}")
        return "\n".join(lines)

    registry.register_async(
        "api-test",
        "Build and display an API test case",
        api_test_handler,
    )

    # ------------------------------------------------------------------
    # /api-run — Run an API test
    # ------------------------------------------------------------------
    async def api_run_handler(args: str) -> str:
        """
        Usage: /api-run <method> <url> [--assert-status CODE] [--retries N]
                        [--auth-bearer TOKEN] [--name NAME]
        """
        from lidco.apitest.builder import (
            AssertionBuilder,
            RequestBuilder,
            TestCaseBuilder,
            TestSuiteBuilder,
        )
        from lidco.apitest.runner import ApiTestRunner, AuthConfig, RunnerConfig

        parts = shlex.split(args) if args.strip() else []
        if len(parts) < 2:
            return "Usage: /api-run <method> <url> [--assert-status CODE] [--retries N] [--auth-bearer TOKEN]"

        method = parts[0].upper()
        url = parts[1]
        assert_status: int | None = None
        retries = 0
        token = ""
        name = "run"

        i = 2
        while i < len(parts):
            if parts[i] == "--assert-status" and i + 1 < len(parts):
                try:
                    assert_status = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--retries" and i + 1 < len(parts):
                try:
                    retries = int(parts[i + 1])
                except ValueError:
                    pass
                i += 2
            elif parts[i] == "--auth-bearer" and i + 1 < len(parts):
                token = parts[i + 1]
                i += 2
            elif parts[i] == "--name" and i + 1 < len(parts):
                name = parts[i + 1]
                i += 2
            else:
                i += 1

        req = RequestBuilder().method(method).url(url).build()
        ab = AssertionBuilder()
        if assert_status is not None:
            ab = ab.status_eq(assert_status)
        case = TestCaseBuilder(name).request(req).assertions(ab.build()).build()
        suite = TestSuiteBuilder("cli-run").add_case(case).build()

        auth = AuthConfig(auth_type="bearer", token=token) if token else AuthConfig()
        config = RunnerConfig(retries=retries, auth=auth)
        runner = ApiTestRunner(config)

        try:
            result = runner.run_suite(suite)
        except Exception as exc:  # noqa: BLE001
            return f"Error running test: {exc}"

        cr = result.results[0] if result.results else None
        if cr is None:
            return "No results."

        status = "PASS" if cr.passed else "FAIL"
        lines = [
            f"[{status}] {cr.name}: HTTP {cr.status_code} ({cr.duration_ms}ms)",
        ]
        if cr.error:
            lines.append(f"  Error: {cr.error}")
        for ar in cr.assertion_results:
            ar_status = "ok" if ar.passed else "FAIL"
            lines.append(f"  [{ar_status}] {ar.assertion.field} {ar.assertion.operator} {ar.assertion.expected!r} (got {ar.actual!r})")
        return "\n".join(lines)

    registry.register_async(
        "api-run",
        "Run an API test against a live endpoint",
        api_run_handler,
    )

    # ------------------------------------------------------------------
    # /api-mock — Start/stop a mock API server
    # ------------------------------------------------------------------
    async def api_mock_handler(args: str) -> str:
        """
        Usage: /api-mock start [--port PORT]
               /api-mock stop
               /api-mock add <method> <path> [--status CODE] [--body JSON]
               /api-mock list
        """
        from lidco.apitest.mock_server import MockApiServer, MockResponse

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /api-mock start [--port PORT]\n"
                "       /api-mock stop\n"
                "       /api-mock add <method> <path> [--status CODE] [--body JSON]\n"
                "       /api-mock list"
            )

        # Use a module-level dict for server state
        if not hasattr(api_mock_handler, "_server"):
            api_mock_handler._server = None  # type: ignore[attr-defined]
            api_mock_handler._routes_info: list[str] = []  # type: ignore[attr-defined]

        subcmd = parts[0]

        if subcmd == "start":
            port = 0
            j = 1
            while j < len(parts):
                if parts[j] == "--port" and j + 1 < len(parts):
                    try:
                        port = int(parts[j + 1])
                    except ValueError:
                        pass
                    j += 2
                else:
                    j += 1
            if api_mock_handler._server is not None:  # type: ignore[attr-defined]
                return "Mock server already running."
            server = MockApiServer(port=port, recording=True)
            server.start()
            api_mock_handler._server = server  # type: ignore[attr-defined]
            return f"Mock server started at {server.base_url}"

        if subcmd == "stop":
            server = api_mock_handler._server  # type: ignore[attr-defined]
            if server is None:
                return "No mock server running."
            server.stop()
            api_mock_handler._server = None  # type: ignore[attr-defined]
            api_mock_handler._routes_info = []  # type: ignore[attr-defined]
            return "Mock server stopped."

        if subcmd == "add":
            server = api_mock_handler._server  # type: ignore[attr-defined]
            if server is None:
                return "No mock server running. Use: /api-mock start"
            if len(parts) < 3:
                return "Usage: /api-mock add <method> <path> [--status CODE] [--body JSON]"
            route_method = parts[1].upper()
            route_path = parts[2]
            status = 200
            body: str | None = None
            j = 3
            while j < len(parts):
                if parts[j] == "--status" and j + 1 < len(parts):
                    try:
                        status = int(parts[j + 1])
                    except ValueError:
                        pass
                    j += 2
                elif parts[j] == "--body" and j + 1 < len(parts):
                    body = parts[j + 1]
                    j += 2
                else:
                    j += 1

            import json as _json

            parsed_body: Any = body
            if body is not None:
                try:
                    parsed_body = _json.loads(body)
                except (ValueError, _json.JSONDecodeError):
                    parsed_body = body

            server.route(route_method, route_path, status=status, body=parsed_body)
            desc = f"{route_method} {route_path} -> {status}"
            api_mock_handler._routes_info = [*api_mock_handler._routes_info, desc]  # type: ignore[attr-defined]
            return f"Route added: {desc}"

        if subcmd == "list":
            routes = api_mock_handler._routes_info  # type: ignore[attr-defined]
            if not routes:
                return "No routes registered."
            return "Routes:\n" + "\n".join(f"  {r}" for r in routes)

        return "Unknown sub-command. Use: start, stop, add, list."

    registry.register_async(
        "api-mock",
        "Manage a mock API server",
        api_mock_handler,
    )

    # ------------------------------------------------------------------
    # /api-report — Generate a report from last run
    # ------------------------------------------------------------------
    async def api_report_handler(args: str) -> str:
        """
        Usage: /api-report [--format text|json]

        Runs a demo test and shows the report.
        """
        from lidco.apitest.report import ApiTestReporter
        from lidco.apitest.runner import SuiteResult, TestCaseResult

        parts = shlex.split(args) if args.strip() else []
        fmt = "text"
        i = 0
        while i < len(parts):
            if parts[i] == "--format" and i + 1 < len(parts):
                fmt = parts[i + 1]
                i += 2
            else:
                i += 1

        # If there's a stored result from /api-run we would use it.
        # For now, return usage guidance.
        if not hasattr(api_report_handler, "_last_result"):
            return (
                "No test results available. Run /api-run first, "
                "or use the ApiTestReporter programmatically."
            )

        result: SuiteResult = api_report_handler._last_result  # type: ignore[attr-defined]
        reporter = ApiTestReporter()
        report = reporter.build_report(result)
        if fmt == "json":
            return reporter.format_json(report)
        return reporter.format_text(report)

    registry.register_async(
        "api-report",
        "Generate an API test report",
        api_report_handler,
    )
