"""
Q93 CLI commands:
  /playbook  list|show <name>|run <name> [key=val ...]
  /test-impact [--run] [--since <ref>]
  /ai-blame <file> [<start>-<end>]
  /pr-desc [--base <branch>] [--format github|markdown]
"""

from __future__ import annotations

import asyncio
import shlex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_q93_commands(registry: "CommandRegistry") -> None:

    # ------------------------------------------------------------------ #
    # /playbook
    # ------------------------------------------------------------------ #
    async def playbook_handler(args: str) -> str:
        from lidco.playbooks.engine import PlaybookEngine

        parts = shlex.split(args) if args.strip() else []
        subcommand = parts[0] if parts else "list"
        engine = PlaybookEngine()

        if subcommand == "list":
            books = engine.list()
            if not books:
                return "No playbooks found. Create .lidco/playbooks/*.yaml files."
            lines = [f"  {b.name:20s}  {b.description}" for b in books]
            return "Available playbooks:\n" + "\n".join(lines)

        if subcommand == "show" and len(parts) >= 2:
            try:
                book = engine.load(parts[1])
            except KeyError as exc:
                return str(exc)
            lines = [f"Playbook: {book.name}", f"Description: {book.description}", "Steps:"]
            for i, step in enumerate(book.steps, 1):
                if step.type == "run":
                    lines.append(f"  {i}. run: {step.command}")
                elif step.type == "prompt":
                    lines.append(f"  {i}. prompt: {step.message[:60]}")
                elif step.type == "tool":
                    lines.append(f"  {i}. tool: {step.command}")
                elif step.type == "condition":
                    lines.append(f"  {i}. condition: if {step.condition}")
            return "\n".join(lines)

        if subcommand == "run" and len(parts) >= 2:
            name = parts[1]
            # Parse key=val pairs
            variables: dict[str, str] = {}
            for token in parts[2:]:
                if "=" in token:
                    k, _, v = token.partition("=")
                    variables[k.strip()] = v.strip()

            try:
                result = engine.execute(name, variables)
            except KeyError as exc:
                return str(exc)
            except Exception as exc:
                return f"Playbook execution error: {exc}"

            status = "✓ succeeded" if result.success else "✗ failed"
            header = (
                f"Playbook '{result.name}': {status} "
                f"({result.steps_completed}/{result.steps_total} steps)"
            )
            if result.output:
                return f"{header}\n\n{result.output[:2000]}"
            return header

        return (
            "Usage:\n"
            "  /playbook list\n"
            "  /playbook show <name>\n"
            "  /playbook run <name> [key=val ...]"
        )

    registry.register_async("playbook", "Devin-style reusable workflow scripts", playbook_handler)

    # ------------------------------------------------------------------ #
    # /test-impact
    # ------------------------------------------------------------------ #
    async def test_impact_handler(args: str) -> str:
        from lidco.testing.impact_analyzer import ChangeSet, TestImpactAnalyzer

        parts = shlex.split(args) if args.strip() else []
        run_tests = "--run" in parts
        since_ref: str | None = None
        changed_files: list[str] = []

        i = 0
        while i < len(parts):
            if parts[i] == "--since" and i + 1 < len(parts):
                since_ref = parts[i + 1]
                i += 2
            elif parts[i] == "--run":
                i += 1
            elif not parts[i].startswith("--"):
                changed_files.append(parts[i])
                i += 1
            else:
                i += 1

        analyzer = TestImpactAnalyzer()

        if since_ref:
            result = analyzer.analyze_since(since_ref)
        elif changed_files:
            result = analyzer.analyze(ChangeSet(files=changed_files))
        else:
            result = analyzer.analyze_since("HEAD~1")

        lines = [
            f"Changed files: {len(result.changed_files)}",
            f"Affected tests: {len(result.affected_tests)}",
            f"Skipped tests:  {len(result.skipped_tests)}",
            f"Coverage estimate: {result.coverage_estimate:.0%} of tests need to run",
            "",
            f"Minimal command:\n  {result.get_minimal_test_command()}",
        ]

        if result.affected_tests:
            lines += ["", "Affected test files:"]
            for t in result.affected_tests[:20]:
                lines.append(f"  {t}")
            if len(result.affected_tests) > 20:
                lines.append(f"  … and {len(result.affected_tests) - 20} more")

        if run_tests and result.affected_tests:
            import subprocess
            cmd = result.get_minimal_test_command()
            lines.append(f"\nRunning: {cmd}")
            try:
                proc = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=120
                )
                output = (proc.stdout + proc.stderr)[:2000]
                lines.append(output)
            except Exception as exc:
                lines.append(f"Error running tests: {exc}")

        return "\n".join(lines)

    registry.register_async(
        "test-impact",
        "Show which tests are affected by recent changes (Nx/Turborepo parity)",
        test_impact_handler,
    )

    # ------------------------------------------------------------------ #
    # /ai-blame
    # ------------------------------------------------------------------ #
    async def ai_blame_handler(args: str) -> str:
        from lidco.git.ai_blame import AIBlameAnalyzer

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return "Usage: /ai-blame <file> [<start>-<end>]"

        filepath = parts[0]
        line_range: tuple[int, int] | None = None

        if len(parts) >= 2:
            range_str = parts[1]
            if "-" in range_str:
                lo, _, hi = range_str.partition("-")
                try:
                    line_range = (int(lo), int(hi))
                except ValueError:
                    pass

        analyzer = AIBlameAnalyzer()

        if line_range:
            entries = analyzer.analyze_file(filepath, line_range)
        else:
            entries = analyzer.analyze_file(filepath)

        if not entries:
            return f"No blame data found for {filepath}."

        lines: list[str] = [f"AI Blame: {filepath}", ""]
        for entry in entries[:15]:
            range_str = (
                f"L{entry.line_start}"
                if entry.line_start == entry.line_end
                else f"L{entry.line_start}–{entry.line_end}"
            )
            lines.append(
                f"  {range_str:12s}  {entry.commit[:8]}  "
                f"{entry.author} — {entry.message}"
            )
            if entry.ai_explanation:
                lines.append(f"              ↳ {entry.ai_explanation}")

        if len(entries) > 15:
            lines.append(f"  … and {len(entries) - 15} more entries")

        return "\n".join(lines)

    registry.register_async(
        "ai-blame",
        "LLM-enhanced git blame (CodeSee parity)",
        ai_blame_handler,
    )

    # ------------------------------------------------------------------ #
    # /pr-desc
    # ------------------------------------------------------------------ #
    async def pr_desc_handler(args: str) -> str:
        from lidco.git.pr_description import PRDescriptionGenerator

        parts = shlex.split(args) if args.strip() else []
        base_branch = "main"
        fmt = "markdown"

        i = 0
        while i < len(parts):
            if parts[i] == "--base" and i + 1 < len(parts):
                base_branch = parts[i + 1]
                i += 2
            elif parts[i] == "--format" and i + 1 < len(parts):
                fmt = parts[i + 1]
                i += 2
            else:
                i += 1

        generator = PRDescriptionGenerator()
        try:
            desc = generator.generate(base_branch=base_branch)
        except Exception as exc:
            return f"Error generating PR description: {exc}"

        if fmt == "github":
            return generator.format_github(desc)
        return generator.format_markdown(desc)

    registry.register_async(
        "pr-desc",
        "Auto-generate PR description from git diff + commits (GitHub Copilot parity)",
        pr_desc_handler,
    )
