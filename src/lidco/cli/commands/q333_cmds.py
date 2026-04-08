"""Q333 CLI commands — /adr, /gen-adr, /search-adr, /validate-adr

Registered via register_q333_commands(registry).
"""

from __future__ import annotations

import json
import shlex


def register_q333_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q333 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /adr — Manage Architecture Decision Records
    # ------------------------------------------------------------------
    async def adr_handler(args: str) -> str:
        """
        Usage: /adr list [status]
               /adr show <number>
               /adr create <title> [--context ...] [--decision ...] [--tags ...]
               /adr accept <number>
               /adr deprecate <number>
               /adr supersede <old> <new>
               /adr remove <number>
               /adr templates
               /adr export <number>
        """
        from lidco.adr.manager import ADRManager, ADRStatus

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /adr <subcommand>\n"
                "  list [status]                    list ADRs (optionally by status)\n"
                "  show <number>                    show ADR details\n"
                "  create <title>                   create a new ADR\n"
                "  accept <number>                  accept an ADR\n"
                "  deprecate <number>               deprecate an ADR\n"
                "  supersede <old> <new>            supersede an ADR\n"
                "  remove <number>                  remove an ADR\n"
                "  templates                        list templates\n"
                "  export <number>                  export ADR as markdown"
            )

        subcmd = parts[0].lower()
        mgr = ADRManager()

        if subcmd == "list":
            status_filter = parts[1] if len(parts) > 1 else None
            if status_filter:
                try:
                    status = ADRStatus(status_filter.lower())
                    adrs = mgr.list_by_status(status)
                except ValueError:
                    return f"Unknown status '{status_filter}'. Use: proposed/accepted/deprecated/superseded."
            else:
                adrs = mgr.list_all()
            if not adrs:
                return "No ADRs found."
            lines = [f"ADRs ({len(adrs)}):"]
            for a in adrs:
                lines.append(f"  ADR-{a.number:04d}: {a.title} [{a.status.value}]")
            return "\n".join(lines)

        if subcmd == "show":
            if len(parts) < 2:
                return "Usage: /adr show <number>"
            try:
                num = int(parts[1])
            except ValueError:
                return "ADR number must be an integer."
            adr = mgr.get(num)
            if adr is None:
                return f"ADR-{num:04d} not found."
            return adr.to_markdown()

        if subcmd == "create":
            if len(parts) < 2:
                return "Usage: /adr create <title>"
            title = parts[1]
            context = ""
            decision = ""
            tags: list[str] = []
            # Parse optional flags
            i = 2
            while i < len(parts):
                if parts[i] == "--context" and i + 1 < len(parts):
                    context = parts[i + 1]
                    i += 2
                elif parts[i] == "--decision" and i + 1 < len(parts):
                    decision = parts[i + 1]
                    i += 2
                elif parts[i] == "--tags" and i + 1 < len(parts):
                    tags = [t.strip() for t in parts[i + 1].split(",")]
                    i += 2
                else:
                    i += 1
            adr = mgr.create(title=title, context=context, decision=decision, tags=tags)
            return (
                f"Created ADR-{adr.number:04d}: {adr.title}\n"
                f"Status: {adr.status.value}\n"
                f"Date: {adr.date}"
            )

        if subcmd == "accept":
            if len(parts) < 2:
                return "Usage: /adr accept <number>"
            try:
                num = int(parts[1])
                adr = mgr.update_status(num, ADRStatus.ACCEPTED)
                return f"ADR-{num:04d} accepted."
            except (ValueError, KeyError) as exc:
                return f"Error: {exc}"

        if subcmd == "deprecate":
            if len(parts) < 2:
                return "Usage: /adr deprecate <number>"
            try:
                num = int(parts[1])
                adr = mgr.update_status(num, ADRStatus.DEPRECATED)
                return f"ADR-{num:04d} deprecated."
            except (ValueError, KeyError) as exc:
                return f"Error: {exc}"

        if subcmd == "supersede":
            if len(parts) < 3:
                return "Usage: /adr supersede <old-number> <new-number>"
            try:
                old_num = int(parts[1])
                new_num = int(parts[2])
                mgr.supersede(old_num, new_num)
                return f"ADR-{old_num:04d} superseded by ADR-{new_num:04d}."
            except (ValueError, KeyError) as exc:
                return f"Error: {exc}"

        if subcmd == "remove":
            if len(parts) < 2:
                return "Usage: /adr remove <number>"
            try:
                num = int(parts[1])
                mgr.remove(num)
                return f"Removed ADR-{num:04d}."
            except (ValueError, KeyError) as exc:
                return f"Error: {exc}"

        if subcmd == "templates":
            names = mgr.list_templates()
            return f"Templates: {', '.join(names)}"

        if subcmd == "export":
            if len(parts) < 2:
                return "Usage: /adr export <number>"
            try:
                num = int(parts[1])
                md = mgr.export_markdown(num)
                return md
            except (ValueError, KeyError) as exc:
                return f"Error: {exc}"

        return f"Unknown subcommand '{subcmd}'. Use list/show/create/accept/deprecate/supersede/remove/templates/export."

    registry.register_async("adr", "Manage Architecture Decision Records", adr_handler)

    # ------------------------------------------------------------------
    # /gen-adr — Generate ADRs from discussions
    # ------------------------------------------------------------------
    async def gen_adr_handler(args: str) -> str:
        """
        Usage: /gen-adr from-text <text> [--title <title>] [--author <name>]
               /gen-adr from-json <json-array>
        """
        from lidco.adr.generator import ADRGenerator, DiscussionEntry

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /gen-adr <subcommand>\n"
                "  from-text <text>                generate from free text\n"
                "  from-json <json-array>          generate from discussion JSON"
            )

        subcmd = parts[0].lower()
        gen = ADRGenerator()

        if subcmd == "from-text":
            if len(parts) < 2:
                return "Usage: /gen-adr from-text <text> [--title <t>] [--author <a>]"
            text = parts[1]
            title = ""
            author = ""
            i = 2
            while i < len(parts):
                if parts[i] == "--title" and i + 1 < len(parts):
                    title = parts[i + 1]
                    i += 2
                elif parts[i] == "--author" and i + 1 < len(parts):
                    author = parts[i + 1]
                    i += 2
                else:
                    i += 1
            try:
                result = gen.generate_from_text(text, title=title, author=author)
                return (
                    f"Generated ADR-{result.adr.number:04d}: {result.adr.title}\n"
                    f"Confidence: {result.confidence:.0%}\n"
                    f"Context: {result.extracted_context[:80] or '(none)'}...\n"
                    f"Decision: {result.extracted_decision[:80] or '(none)'}...\n"
                    f"Consequences: {result.extracted_consequences[:80] or '(none)'}..."
                )
            except ValueError as exc:
                return f"Error: {exc}"

        if subcmd == "from-json":
            raw = args.strip()[len("from-json"):].strip()
            if not raw:
                return "Usage: /gen-adr from-json <json-array>"
            try:
                data = json.loads(raw)
                entries = [
                    DiscussionEntry(
                        author=d.get("author", ""),
                        content=d.get("content", ""),
                        timestamp=d.get("timestamp", ""),
                        role=d.get("role", ""),
                    )
                    for d in data
                ]
                result = gen.generate_from_discussion(entries)
                return (
                    f"Generated ADR-{result.adr.number:04d}: {result.adr.title}\n"
                    f"Confidence: {result.confidence:.0%}\n"
                    f"Source entries: {result.source_entries}"
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                return f"Error: {exc}"

        return f"Unknown subcommand '{subcmd}'. Use from-text/from-json."

    registry.register_async("gen-adr", "Generate ADRs from discussions", gen_adr_handler)

    # ------------------------------------------------------------------
    # /search-adr — Search ADRs
    # ------------------------------------------------------------------
    async def search_adr_handler(args: str) -> str:
        """
        Usage: /search-adr <query>
               /search-adr --status <status>
               /search-adr --tag <tag>
               /search-adr --date <start> <end>
               /search-adr --trace
        """
        from lidco.adr.manager import ADRManager, ADRStatus
        from lidco.adr.search import ADRSearch

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /search-adr <query|option>\n"
                "  <query>                         full-text search\n"
                "  --status <status>               filter by status\n"
                "  --tag <tag>                     filter by tag\n"
                "  --date <start> <end>            filter by date range\n"
                "  --trace                         traceability report"
            )

        mgr = ADRManager()
        search = ADRSearch(mgr)

        if parts[0] == "--status":
            if len(parts) < 2:
                return "Usage: /search-adr --status <status>"
            try:
                status = ADRStatus(parts[1].lower())
                results = search.search_by_status(status)
            except ValueError:
                return f"Unknown status '{parts[1]}'. Use: proposed/accepted/deprecated/superseded."
            if not results:
                return "No ADRs found."
            lines = [f"ADRs with status '{parts[1]}' ({len(results)}):"]
            for r in results:
                lines.append(f"  ADR-{r.adr.number:04d}: {r.adr.title}")
            return "\n".join(lines)

        if parts[0] == "--tag":
            if len(parts) < 2:
                return "Usage: /search-adr --tag <tag>"
            results = search.search_by_tag(parts[1])
            if not results:
                return "No ADRs found."
            lines = [f"ADRs tagged '{parts[1]}' ({len(results)}):"]
            for r in results:
                lines.append(f"  ADR-{r.adr.number:04d}: {r.adr.title}")
            return "\n".join(lines)

        if parts[0] == "--date":
            if len(parts) < 3:
                return "Usage: /search-adr --date <start-YYYY-MM-DD> <end-YYYY-MM-DD>"
            results = search.search_by_date_range(parts[1], parts[2])
            if not results:
                return "No ADRs found in date range."
            lines = [f"ADRs in range ({len(results)}):"]
            for r in results:
                lines.append(f"  ADR-{r.adr.number:04d}: {r.adr.title} ({r.adr.date})")
            return "\n".join(lines)

        if parts[0] == "--trace":
            reports = search.traceability_report()
            if not reports:
                return "No ADRs to trace."
            lines = ["Traceability Report:"]
            for tr in reports:
                ref_status = "referenced" if tr.referenced_in_code else "NOT referenced"
                lines.append(f"  ADR-{tr.adr_number:04d}: {tr.title} [{tr.status}] — {ref_status}")
            return "\n".join(lines)

        # Default: full-text search
        query = " ".join(parts)
        results = search.full_text_search(query)
        if not results:
            return f"No ADRs matching '{query}'."
        lines = [f"Search results for '{query}' ({len(results)}):"]
        for r in results:
            lines.append(f"  ADR-{r.adr.number:04d}: {r.adr.title} (score={r.score})")
        return "\n".join(lines)

    registry.register_async("search-adr", "Search Architecture Decision Records", search_adr_handler)

    # ------------------------------------------------------------------
    # /validate-adr — Validate ADR compliance
    # ------------------------------------------------------------------
    async def validate_adr_handler(args: str) -> str:
        """
        Usage: /validate-adr
               /validate-adr <number>
               /validate-adr overdue
        """
        from lidco.adr.manager import ADRManager
        from lidco.adr.validator import ADRValidator

        parts = shlex.split(args) if args.strip() else []

        mgr = ADRManager()
        validator = ADRValidator(mgr)

        if not parts:
            report = validator.validate()
            if not report.issues:
                return f"All {report.adrs_checked} ADRs passed validation."
            lines = [
                f"Validation: {report.adrs_checked} ADRs, {report.rules_applied} rules",
                f"  Errors: {report.error_count}, Warnings: {report.warning_count}, Info: {report.info_count}",
            ]
            for issue in report.issues:
                lines.append(f"  [{issue.severity}] ADR-{issue.adr_number:04d}: {issue.message}")
            return "\n".join(lines)

        if parts[0].lower() == "overdue":
            overdue = validator.get_overdue_reviews()
            if not overdue:
                return "No overdue reviews."
            lines = [f"Overdue reviews ({len(overdue)}):"]
            for s in overdue:
                lines.append(f"  ADR-{s.adr_number:04d}: last reviewed {s.last_reviewed or 'never'}")
            return "\n".join(lines)

        # Single ADR validation
        try:
            num = int(parts[0])
            report = validator.validate_single(num)
            if not report.issues:
                return f"ADR-{num:04d} passed validation."
            lines = [f"Validation for ADR-{num:04d}:"]
            for issue in report.issues:
                lines.append(f"  [{issue.severity}] {issue.message}")
            return "\n".join(lines)
        except ValueError:
            return "Usage: /validate-adr [number|overdue]"
        except KeyError as exc:
            return f"Error: {exc}"

    registry.register_async("validate-adr", "Validate ADR compliance", validate_adr_handler)
