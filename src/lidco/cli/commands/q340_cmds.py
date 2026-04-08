"""
Q340 CLI commands — /cmd-dedup, /cmd-deps, /async-validate, /cmd-coverage

Registered via register_q340_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q340_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q340 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /cmd-dedup — Detect duplicate slash command registrations
    # ------------------------------------------------------------------
    async def cmd_dedup_handler(args: str) -> str:
        """
        Usage: /cmd-dedup <json-array-of-commands>
               /cmd-dedup --help
        """
        from lidco.stability.cmd_dedup import CommandDedupValidator

        parts = shlex.split(args) if args.strip() else []
        if not parts or parts[0] in ("--help", "-h"):
            return (
                "Usage: /cmd-dedup <json-array>\n"
                "\n"
                "Each element: {\"name\": str, \"description\": str, \"line\": int}\n"
                "\n"
                "Detects duplicate registrations and shadow chains."
            )

        import json

        raw = args.strip()
        try:
            commands = json.loads(raw)
        except json.JSONDecodeError as exc:
            return f"Error parsing JSON: {exc}"

        if not isinstance(commands, list):
            return "Error: expected a JSON array of command objects."

        validator = CommandDedupValidator()
        duplicates = validator.find_duplicates(commands)
        shadows = validator.analyze_shadows(commands)
        chain = validator.track_override_chain(commands)
        fixes = validator.suggest_fixes(duplicates)

        lines: list[str] = [
            f"Slash Command Dedup Report ({len(commands)} registrations analysed)",
            "=" * 60,
        ]

        if duplicates:
            lines.append(f"\nDuplicates found: {len(duplicates)}")
            for dup in duplicates:
                lines.append(
                    f"  '{dup['name']}' — registered {len(dup['registrations'])} times "
                    f"(lines {dup['registrations']}), winner: line {dup['winner']}"
                )
        else:
            lines.append("\nNo duplicate registrations detected.")

        if shadows:
            lines.append(f"\nShadowed commands: {len(shadows)}")
            for s in shadows:
                lines.append(
                    f"  '{s['shadowed_name']}': original line {s['original_line']} "
                    f"shadowed at line {s['shadow_line']}"
                )
        else:
            lines.append("No shadow conflicts detected.")

        lines.append(f"\nOverride chains: {len(chain)} unique command names tracked.")

        if fixes:
            lines.append("\nSuggested fixes:")
            for fix in fixes:
                lines.append(f"  - {fix}")

        return "\n".join(lines)

    registry.register_async(
        "cmd-dedup",
        "Detect duplicate and shadowed slash command registrations",
        cmd_dedup_handler,
    )

    # ------------------------------------------------------------------
    # /cmd-deps — Check handler source for missing imports/dependencies
    # ------------------------------------------------------------------
    async def cmd_deps_handler(args: str) -> str:
        """
        Usage: /cmd-deps <source-code>
               /cmd-deps --help
        """
        from lidco.stability.cmd_deps import CommandDependencyChecker

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /cmd-deps <source-code>\n"
                "\n"
                "Pass Python source code (as a string) to check for\n"
                "missing imports, unavailable dependencies, and incorrect\n"
                "try/except import fallbacks."
            )

        source = args  # treat entire args as source code
        checker = CommandDependencyChecker()

        dep_findings = checker.check_dependencies(source)
        missing_imports = checker.detect_missing_imports(source)
        fallbacks = checker.validate_fallbacks(source)

        report = checker.generate_report(dep_findings)

        lines: list[str] = [report, ""]

        if fallbacks:
            lines.append(f"Import fallback analysis ({len(fallbacks)} found):")
            for fb in fallbacks:
                status = "OK" if fb["fallback_correct"] else (
                    "MISSING FALLBACK" if not fb["has_fallback"] else "FALLBACK INCORRECT"
                )
                lines.append(
                    f"  Line {fb['line']}: {fb['module']} — {status}"
                )
        else:
            lines.append("No try/except import fallbacks detected.")

        return "\n".join(lines)

    registry.register_async(
        "cmd-deps",
        "Check command handler source for missing imports/dependencies",
        cmd_deps_handler,
    )

    # ------------------------------------------------------------------
    # /async-validate — Validate async handlers for common anti-patterns
    # ------------------------------------------------------------------
    async def async_validate_handler(args: str) -> str:
        """
        Usage: /async-validate <source-code>
               /async-validate --help
        """
        from lidco.stability.async_validator import AsyncHandlerValidator

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /async-validate <source-code>\n"
                "\n"
                "Scans Python async handler source code for:\n"
                "  - Blocking calls (time.sleep, open, requests, subprocess)\n"
                "  - Missing await on coroutines\n"
                "  - Async operations without timeout guards"
            )

        source = args
        validator = AsyncHandlerValidator()

        blocking = validator.find_blocking_calls(source)
        await_issues = validator.check_await_chains(source)
        timeout_issues = [
            f for f in validator.check_timeout_guards(source)
            if not f.get("has_timeout", True)
        ]

        lines: list[str] = [
            "Async Handler Validation Report",
            "=" * 40,
        ]

        if blocking:
            lines.append(f"\nBlocking calls detected ({len(blocking)}):")
            for b in blocking:
                lines.append(
                    f"  Line {b['line']}: '{b['call']}' — "
                    f"use {b['async_alternative']} instead"
                )
        else:
            lines.append("\nNo blocking calls detected.")

        if await_issues:
            lines.append(f"\nMissing await ({len(await_issues)}):")
            for aw in await_issues:
                lines.append(f"  Line {aw['line']}: {aw['issue']}")
        else:
            lines.append("No missing await issues detected.")

        if timeout_issues:
            lines.append(f"\nMissing timeout guards ({len(timeout_issues)}):")
            for t in timeout_issues:
                lines.append(
                    f"  Line {t['line']}: '{t['operation']}' — {t['suggestion']}"
                )
        else:
            lines.append("No missing timeout guards detected.")

        total_issues = len(blocking) + len(await_issues) + len(timeout_issues)
        lines.append(f"\nTotal issues: {total_issues}")
        return "\n".join(lines)

    registry.register_async(
        "async-validate",
        "Validate async handlers for blocking calls, missing awaits, and timeout guards",
        async_validate_handler,
    )

    # ------------------------------------------------------------------
    # /cmd-coverage — Track slash command test coverage
    # ------------------------------------------------------------------
    async def cmd_coverage_handler(args: str) -> str:
        """
        Usage: /cmd-coverage <json-object>
               /cmd-coverage --help

        JSON object format:
          {
            "commands": ["cmd-dedup", "cmd-deps", ...],
            "test_files": {"test_foo.py": "<file content>", ...}
          }
        """
        from lidco.stability.cmd_coverage import CommandCoverageTracker

        if not args.strip() or args.strip() in ("--help", "-h"):
            return (
                "Usage: /cmd-coverage <json-object>\n"
                "\n"
                "JSON fields:\n"
                '  "commands"   — list of command name strings\n'
                '  "test_files" — dict mapping filename -> file content\n'
                "\n"
                "Reports coverage %, untested commands, and generates stubs."
            )

        import json

        try:
            data = json.loads(args.strip())
        except json.JSONDecodeError as exc:
            return f"Error parsing JSON: {exc}"

        if not isinstance(data, dict):
            return "Error: expected a JSON object with 'commands' and 'test_files' keys."

        commands: list[str] = data.get("commands", [])
        test_files: dict[str, str] = data.get("test_files", {})

        if not isinstance(commands, list):
            return "Error: 'commands' must be a list of strings."
        if not isinstance(test_files, dict):
            return "Error: 'test_files' must be a dict mapping filename -> content."

        tracker = CommandCoverageTracker()
        mapping = tracker.map_commands_to_tests(commands, test_files)
        untested = tracker.find_untested(commands, test_files)
        pct = tracker.coverage_percentage(commands, test_files)

        lines: list[str] = [
            "Command Coverage Report",
            "=" * 40,
            f"Commands: {len(commands)}",
            f"Test files: {len(test_files)}",
            f"Coverage: {pct:.1f}%",
        ]

        if untested:
            lines.append(f"\nUntested commands ({len(untested)}):")
            for cmd in untested:
                lines.append(f"  - /{cmd}")
            lines.append("\nGenerated test stubs:")
            lines.append("-" * 40)
            stubs = tracker.generate_test_stubs(untested)
            lines.append(stubs)
        else:
            lines.append("\nAll commands have test coverage.")

        lines.append("\nCoverage map:")
        for cmd, files in mapping.items():
            status = "TESTED" if files else "UNTESTED"
            file_list = ", ".join(files) if files else "none"
            lines.append(f"  [{status}] /{cmd} — {file_list}")

        return "\n".join(lines)

    registry.register_async(
        "cmd-coverage",
        "Track slash command test coverage and generate test stubs",
        cmd_coverage_handler,
    )
