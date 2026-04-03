"""Q256 CLI commands: /api-extract, /api-diff, /api-mock, /api-test."""
from __future__ import annotations


def register(registry) -> None:  # noqa: ANN001
    """Register Q256 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /api-extract
    # ------------------------------------------------------------------

    async def api_extract_handler(args: str) -> str:
        from lidco.api_intel.extractor import APIExtractor

        extractor = APIExtractor()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "source":
            if not rest:
                return "Usage: /api-extract source <python source code>"
            endpoints = extractor.extract_from_source(rest)
            return extractor.summary(endpoints)

        if sub == "openapi":
            if not rest:
                return "Usage: /api-extract openapi <python source code>"
            endpoints = extractor.extract_from_source(rest)
            import json
            return json.dumps(extractor.to_openapi(endpoints), indent=2)

        if sub == "graphql":
            if not rest:
                return "Usage: /api-extract graphql <python source code>"
            endpoints = extractor.extract_from_source(rest)
            return extractor.to_graphql_schema(endpoints)

        return (
            "Usage: /api-extract <subcommand>\n"
            "  source <code>  — extract endpoints from source\n"
            "  openapi <code> — generate OpenAPI spec\n"
            "  graphql <code> — generate GraphQL schema"
        )

    # ------------------------------------------------------------------
    # /api-diff
    # ------------------------------------------------------------------

    async def api_diff_handler(args: str) -> str:
        from lidco.api_intel.diff import APIDiff
        from lidco.api_intel.extractor import APIExtractor

        differ = APIDiff()
        extractor = APIExtractor()
        parts = args.strip().split("|||")

        if len(parts) < 2:
            return (
                "Usage: /api-diff <old source> ||| <new source>\n"
                "  Separate old and new source with |||"
            )

        old_eps = extractor.extract_from_source(parts[0].strip())
        new_eps = extractor.extract_from_source(parts[1].strip())
        entries = differ.diff(old_eps, new_eps)

        if not entries:
            return "No API changes detected."

        breaking = differ.breaking_changes(entries)
        compat = "COMPATIBLE" if not breaking else "BREAKING CHANGES DETECTED"
        return f"[{compat}]\n{differ.summary(entries)}"

    # ------------------------------------------------------------------
    # /api-mock
    # ------------------------------------------------------------------

    async def api_mock_handler(args: str) -> str:
        from lidco.api_intel.extractor import APIExtractor
        from lidco.api_intel.mock_server import APIMockServer

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        server = APIMockServer()

        if sub == "generate":
            if not rest:
                return "Usage: /api-mock generate <python source code>"
            extractor = APIExtractor()
            endpoints = extractor.extract_from_source(rest)
            server.generate_from_endpoints(endpoints)
            routes = server.list_routes()
            if not routes:
                return "No routes generated."
            lines = [f"Generated {len(routes)} mock route(s):"]
            for r in routes:
                lines.append(f"  {r['method']} {r['path']} -> {r['status']}")
            return "\n".join(lines)

        if sub == "test":
            if not rest:
                return "Usage: /api-mock test <method> <path>"
            tparts = rest.split(maxsplit=1)
            if len(tparts) < 2:
                return "Usage: /api-mock test <method> <path>"
            resp = server.get_response(tparts[0], tparts[1])
            if resp is None:
                return f"No mock route for {tparts[0].upper()} {tparts[1]}"
            return f"Status: {resp.status}, Body: {resp.body}"

        return (
            "Usage: /api-mock <subcommand>\n"
            "  generate <code> — generate mock routes from source\n"
            "  test <method> <path> — test a mock route"
        )

    # ------------------------------------------------------------------
    # /api-test
    # ------------------------------------------------------------------

    async def api_test_handler(args: str) -> str:
        from lidco.api_intel.extractor import APIExtractor
        from lidco.api_intel.test_gen import APITestGenerator

        extractor = APIExtractor()
        gen = APITestGenerator()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "generate":
            if not rest:
                return "Usage: /api-test generate <python source code>"
            endpoints = extractor.extract_from_source(rest)
            cases = gen.generate(endpoints)
            if not cases:
                return "No test cases generated."
            lines = [f"Generated {len(cases)} test case(s):"]
            for tc in cases:
                lines.append(f"  {tc.name}: {tc.method} {tc.path} -> {tc.expected_status}")
            return "\n".join(lines)

        if sub == "python":
            if not rest:
                return "Usage: /api-test python <python source code>"
            endpoints = extractor.extract_from_source(rest)
            cases = gen.generate(endpoints)
            return gen.to_python(cases)

        return (
            "Usage: /api-test <subcommand>\n"
            "  generate <code> — generate test cases from source\n"
            "  python <code>   — generate Python test code"
        )

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------
    registry.register(SlashCommand("api-extract", "Extract API endpoints from source", api_extract_handler))
    registry.register(SlashCommand("api-diff", "Diff two API versions", api_diff_handler))
    registry.register(SlashCommand("api-mock", "Generate mock API server", api_mock_handler))
    registry.register(SlashCommand("api-test", "Generate API test cases", api_test_handler))
