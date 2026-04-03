"""Q254 CLI commands: /smell-scan, /smell-fix, /smell-dashboard, /smell-config."""

from __future__ import annotations


def register(registry) -> None:
    """Register Q254 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /smell-scan
    # ------------------------------------------------------------------

    async def smell_scan_handler(args: str) -> str:
        from lidco.smells.catalog import SmellCatalog
        from lidco.smells.scanner import SmellScanner

        catalog = SmellCatalog.with_defaults()
        scanner = SmellScanner(catalog)

        source = args.strip()
        if not source:
            return "Usage: /smell-scan <source code or file content>"

        matches = scanner.scan_text(source, filename="<input>")
        if not matches:
            return "No code smells detected."

        lines = [scanner.summary(matches), ""]
        for m in matches:
            lines.append(f"  [{m.severity}] L{m.line}: {m.message}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /smell-fix
    # ------------------------------------------------------------------

    async def smell_fix_handler(args: str) -> str:
        from lidco.smells.catalog import SmellCatalog
        from lidco.smells.fixer import SmellFixer
        from lidco.smells.scanner import SmellScanner

        catalog = SmellCatalog.with_defaults()
        scanner = SmellScanner(catalog)
        fixer = SmellFixer(catalog)

        source = args.strip()
        if not source:
            return "Usage: /smell-fix <source code>"

        matches = scanner.scan_text(source)
        if not matches:
            return "No code smells to fix."

        results = fixer.batch_fix(matches, source)
        if not results:
            return "No automated fixes available."

        lines = [f"{len(results)} fix(es) applied:"]
        for r in results:
            lines.append(f"  [{r.smell_id}] {r.description}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /smell-dashboard
    # ------------------------------------------------------------------

    async def smell_dashboard_handler(args: str) -> str:
        from lidco.smells.catalog import SmellCatalog
        from lidco.smells.dashboard import SmellDashboard
        from lidco.smells.scanner import SmellScanner

        catalog = SmellCatalog.with_defaults()
        scanner = SmellScanner(catalog)

        source = args.strip()
        if not source:
            return "Usage: /smell-dashboard <source code>"

        matches = scanner.scan_text(source, filename="<input>")
        dashboard = SmellDashboard(matches)
        return dashboard.render()

    # ------------------------------------------------------------------
    # /smell-config
    # ------------------------------------------------------------------

    async def smell_config_handler(args: str) -> str:
        from lidco.smells.catalog import SmellCatalog

        catalog = SmellCatalog.with_defaults()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        if sub == "list":
            smells = catalog.list_all()
            if not smells:
                return "No smells configured."
            lines = [f"{len(smells)} smell(s) configured:"]
            for s in smells:
                lines.append(f"  [{s.severity}] {s.id}: {s.name}")
            return "\n".join(lines)

        if sub == "severity":
            sev = parts[1].strip() if len(parts) > 1 else ""
            if not sev:
                return "Usage: /smell-config severity <critical|high|medium|low>"
            smells = catalog.by_severity(sev)
            if not smells:
                return f"No smells with severity '{sev}'."
            lines = [f"{len(smells)} {sev} smell(s):"]
            for s in smells:
                lines.append(f"  {s.id}: {s.name}")
            return "\n".join(lines)

        return (
            "Usage: /smell-config <subcommand>\n"
            "  list              — list all configured smells\n"
            "  severity <level>  — filter by severity"
        )

    registry.register(SlashCommand("smell-scan", "Scan code for smells", smell_scan_handler))
    registry.register(SlashCommand("smell-fix", "Auto-fix code smells", smell_fix_handler))
    registry.register(SlashCommand("smell-dashboard", "Smell metrics dashboard", smell_dashboard_handler))
    registry.register(SlashCommand("smell-config", "Configure smell detection", smell_config_handler))
