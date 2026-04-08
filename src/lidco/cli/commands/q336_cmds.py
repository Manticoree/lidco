"""Q336 CLI commands — /dig-history, /decode-legacy, /migration-advice, /find-dead-features

Registered via register_q336_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q336_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q336 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /dig-history — Dig through project history
    # ------------------------------------------------------------------
    async def dig_history_handler(args: str) -> str:
        """
        Usage: /dig-history timeline <target>
               /dig-history decisions
               /dig-history intent <target>
               /dig-history hotfiles [n]
        """
        from lidco.archaeology.digger import CommitInfo, HistoryDigger

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /dig-history <subcommand>\n"
                "  timeline <target>   show evolution timeline for a file/keyword\n"
                "  decisions           find design decisions in history\n"
                "  intent <target>     recover original design intent\n"
                "  hotfiles [n]        show most-frequently-changed files"
            )

        subcmd = parts[0].lower()
        digger = HistoryDigger()

        if subcmd == "timeline":
            if len(parts) < 2:
                return "Usage: /dig-history timeline <target>"
            target = parts[1]
            tl = digger.timeline_for(target)
            return tl.summary()

        if subcmd == "decisions":
            decisions = digger.find_decisions()
            if not decisions:
                return "No design decisions detected (no commits loaded)."
            lines = [f"Design decisions ({len(decisions)}):"]
            for d in decisions:
                tag = "[HIGH]" if d.is_high_confidence() else "[LOW]"
                lines.append(f"  {tag} {d.summary} ({d.category})")
            return "\n".join(lines)

        if subcmd == "intent":
            if len(parts) < 2:
                return "Usage: /dig-history intent <target>"
            return digger.original_intent(parts[1])

        if subcmd == "hotfiles":
            n = int(parts[1]) if len(parts) > 1 else 10
            hot = digger.hot_files(top_n=n)
            if not hot:
                return "No file change data available."
            lines = [f"Hot files (top {n}):"]
            for path, count in hot:
                lines.append(f"  {path}: {count} changes")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use timeline/decisions/intent/hotfiles."

    registry.register_async("dig-history", "Dig through project history for design intent", dig_history_handler)

    # ------------------------------------------------------------------
    # /decode-legacy — Decode legacy code patterns
    # ------------------------------------------------------------------
    async def decode_legacy_handler(args: str) -> str:
        """
        Usage: /decode-legacy <source-text>
               /decode-legacy explain <pattern-name>
        """
        from lidco.archaeology.decoder import LegacyDecoder

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /decode-legacy <subcommand>\n"
                "  <source-text>          decode a source snippet\n"
                "  explain <pattern>      explain a known pattern name"
            )

        subcmd = parts[0].lower()
        decoder = LegacyDecoder()

        if subcmd == "explain":
            if len(parts) < 2:
                return "Usage: /decode-legacy explain <pattern-name>"
            return decoder.explain_pattern(parts[1])

        # Default: treat entire args as source text
        result = decoder.decode(args.strip(), name="<cli-input>")
        return result.summary()

    registry.register_async("decode-legacy", "Decode legacy code and explain cryptic patterns", decode_legacy_handler)

    # ------------------------------------------------------------------
    # /migration-advice — Advise on legacy migration
    # ------------------------------------------------------------------
    async def migration_advice_handler(args: str) -> str:
        """
        Usage: /migration-advice assess
               /migration-advice plan [name]
        """
        from lidco.archaeology.migration import MigrationAdvisor

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /migration-advice <subcommand>\n"
                "  assess           assess migration risks for loaded files\n"
                "  plan [name]      generate a migration plan"
            )

        subcmd = parts[0].lower()
        advisor = MigrationAdvisor()

        if subcmd == "assess":
            risks = advisor.assess_risks()
            if not risks:
                return "No migration risks detected (no files loaded)."
            lines = [f"Migration risks ({len(risks)}):"]
            for r in risks:
                tag = "[BLOCKING]" if r.is_blocking() else "[OK]"
                lines.append(f"  {tag} {r.description} — {r.mitigation}")
            return "\n".join(lines)

        if subcmd == "plan":
            name = parts[1] if len(parts) > 1 else "migration"
            plan = advisor.plan(name=name)
            return plan.summary()

        return f"Unknown subcommand '{subcmd}'. Use assess/plan."

    registry.register_async("migration-advice", "Advise on legacy code migration", migration_advice_handler)

    # ------------------------------------------------------------------
    # /find-dead-features — Find dead features and unused code
    # ------------------------------------------------------------------
    async def find_dead_features_handler(args: str) -> str:
        """
        Usage: /find-dead-features scan
               /find-dead-features summary
        """
        from lidco.archaeology.dead_finder import DeadFeatureFinder

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /find-dead-features <subcommand>\n"
                "  scan              scan loaded files for dead features\n"
                "  summary           show summary of dead feature report"
            )

        subcmd = parts[0].lower()
        finder = DeadFeatureFinder()

        if subcmd in ("scan", "summary"):
            report = finder.scan()
            return report.summary()

        return f"Unknown subcommand '{subcmd}'. Use scan/summary."

    registry.register_async("find-dead-features", "Find dead features and unused code paths", find_dead_features_handler)
