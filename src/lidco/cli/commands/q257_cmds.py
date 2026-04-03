"""Q257 CLI commands: /infer-types, /annotate-types, /type-check, /migrate-types."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q257 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /infer-types
    # ------------------------------------------------------------------

    async def infer_types_handler(args: str) -> str:
        from lidco.types.inferrer import TypeInferrer

        source = args.strip()
        if not source:
            return "Usage: /infer-types <python source>"

        inferrer = TypeInferrer()
        results = inferrer.infer_all(source)
        if not results:
            return "No types could be inferred."
        lines = [f"Inferred {len(results)} type(s):"]
        for r in results:
            lines.append(f"  {r.name}: {r.type} (confidence={r.confidence:.2f}, source={r.source})")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /annotate-types
    # ------------------------------------------------------------------

    async def annotate_types_handler(args: str) -> str:
        from lidco.types.annotator_v2 import TypeAnnotatorV2
        from lidco.types.inferrer import TypeInferrer

        source = args.strip()
        if not source:
            return "Usage: /annotate-types <python source>"

        inferrer = TypeInferrer()
        inferred = inferrer.infer_all(source)
        annotator = TypeAnnotatorV2()
        annotated = annotator.annotate_all(source, inferred)

        if annotated == source:
            return "No annotations to add."

        diff_lines = annotator.diff(source, annotated)
        if not diff_lines:
            return "No annotations to add."
        return "".join(diff_lines)

    # ------------------------------------------------------------------
    # /type-check
    # ------------------------------------------------------------------

    async def type_check_handler(args: str) -> str:
        from lidco.types.checker import TypeCheckerIntegration

        output = args.strip()
        if not output:
            return "Usage: /type-check <mypy or pyright output>"

        checker = TypeCheckerIntegration()
        # Try mypy first, fall back to pyright.
        errors = checker.parse_mypy_output(output)
        if not errors:
            errors = checker.parse_pyright_output(output)
        if not errors:
            return "No type errors parsed from input."

        lines = [checker.summary(errors)]
        for e in errors:
            fix = checker.suggest_fix(e)
            entry = f"  {e.file}:{e.line} [{e.severity}] {e.message}"
            if e.code:
                entry += f" ({e.code})"
            if fix:
                entry += f"\n    Fix: {fix}"
            lines.append(entry)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /migrate-types
    # ------------------------------------------------------------------

    async def migrate_types_handler(args: str) -> str:
        from lidco.types.migration import TypeMigration

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        migration = TypeMigration.with_defaults()

        if sub == "apply":
            if not rest:
                return "Usage: /migrate-types apply <source>"
            result = migration.apply(rest)
            if result == rest:
                return "No migrations needed."
            return result

        if sub == "preview":
            if not rest:
                return "Usage: /migrate-types preview <source>"
            changes = migration.preview(rest)
            if not changes:
                return "No migrations would apply."
            lines = [f"{len(changes)} rule(s) would apply:"]
            for c in changes:
                lines.append(f"  - {c['description']}")
            return "\n".join(lines)

        if sub == "rules":
            rules = migration.list_rules()
            lines = [f"{len(rules)} migration rule(s):"]
            for r in rules:
                lines.append(f"  - {r.description}")
            return "\n".join(lines)

        return (
            "Usage: /migrate-types <subcommand>\n"
            "  apply <source>   — apply migration rules\n"
            "  preview <source> — preview changes\n"
            "  rules            — list all rules"
        )

    registry.register(SlashCommand("infer-types", "Infer types from Python source", infer_types_handler))
    registry.register(SlashCommand("annotate-types", "Annotate Python source with types", annotate_types_handler))
    registry.register(SlashCommand("type-check", "Parse mypy/pyright output", type_check_handler))
    registry.register(SlashCommand("migrate-types", "Migrate type annotations to modern syntax", migrate_types_handler))
