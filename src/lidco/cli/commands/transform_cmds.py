# src/lidco/cli/commands/transform_cmds.py
"""CLI commands for code transformation and generation (Q82)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_transform_commands(registry: "CommandRegistry") -> None:
    """Register /rename, /multi-edit, /testgen, /health commands."""

    async def rename_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: /rename <old_name> <new_name> [--dry-run]"
        old_name = parts[0]
        rest = parts[1].split()
        dry_run = "--dry-run" in rest
        new_parts = [p for p in rest if p != "--dry-run"]
        if not new_parts:
            return "Usage: /rename <old_name> <new_name> [--dry-run]"
        new_name = new_parts[0]

        try:
            from lidco.refactor.symbol_rename import SymbolRenamer
            renamer = SymbolRenamer(".")
            result = renamer.rename(old_name, new_name, dry_run=dry_run)
            lines = [
                f"{'[dry-run] ' if dry_run else ''}Renamed `{old_name}` → `{new_name}`",
                f"Files changed: {result.files_changed}, occurrences: {result.occurrences}",
            ]
            if result.preview:
                lines.append("Changed files:")
                lines.extend(result.preview[:10])
            if result.errors:
                lines.append("Errors:")
                lines.extend(f"  {e}" for e in result.errors[:5])
            return "\n".join(lines)
        except Exception as e:
            return f"/rename failed: {e}"

    async def multi_edit_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        spec_path = args.strip()
        if not spec_path:
            return "Usage: /multi-edit <spec.yaml>"

        try:
            import yaml  # type: ignore[import]
            from lidco.editing.multi_edit import MultiEditTransaction
            from pathlib import Path
            spec = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8"))
            tx = MultiEditTransaction()
            for step in spec.get("edits", []):
                tx.add_edit(
                    step["path"],
                    step["old"],
                    step["new"],
                    replace_all=step.get("replace_all", False),
                )
            errors = tx.validate()
            if errors:
                return "Validation errors:\n" + "\n".join(f"  {e}" for e in errors)
            result = tx.apply()
            if not result.success:
                tx.rollback()
                return f"Transaction failed (rolled back):\n" + "\n".join(f"  {e}" for e in result.errors)
            return f"Applied {result.applied} edit(s) across {tx.step_count} step(s)."
        except Exception as e:
            return f"/multi-edit failed: {e}"

    async def testgen_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        parts = args.strip().split()
        if not parts:
            return "Usage: /testgen <source_path> [--write]"
        source_path = parts[0]
        write = "--write" in parts

        try:
            from lidco.scaffold.test_gen import TestGenerator
            from pathlib import Path
            gen = TestGenerator()
            result = gen.generate_for_module(source_path)
            if result.error:
                return f"/testgen error: {result.error}"
            if write:
                p = Path(source_path)
                out = p.parent / f"test_{p.stem}.py"
                gen.write_test_file(result.test_code, str(out))
                return f"Tests written to {out}\nFunctions covered: {', '.join(result.functions_covered)}"
            return f"Generated tests for: {', '.join(result.functions_covered)}\n\n{result.test_code}"
        except Exception as e:
            return f"/testgen failed: {e}"

    async def health_handler(args: str = "", arg: str = "", **_) -> str:
        args = args or arg
        try:
            from lidco.analytics.health_dashboard import ProjectHealthDashboard
            dash = ProjectHealthDashboard(".")
            report = dash.collect()
            return report.format_table()
        except Exception as e:
            return f"/health failed: {e}"

    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("rename", "Rename a symbol across the codebase", rename_handler))
    registry.register(SlashCommand("multi-edit", "Apply atomic multi-file edits from a YAML spec", multi_edit_handler))
    registry.register(SlashCommand("testgen", "Generate test stubs for a Python module", testgen_handler))
    registry.register(SlashCommand("health", "Show project health dashboard", health_handler))
