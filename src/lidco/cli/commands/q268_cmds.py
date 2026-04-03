"""Q268 CLI commands: /dlp-scan, /content-filter, /watermark, /dlp-policy."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q268 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /dlp-scan
    # ------------------------------------------------------------------

    async def dlp_scan_handler(args: str) -> str:
        from lidco.dlp.scanner import DLPScanner

        content = args.strip()
        if not content:
            return "Usage: /dlp-scan <content>"
        scanner = DLPScanner()
        result = scanner.scan(content)
        if not result.findings:
            return "No sensitive data found."
        lines = [f"Findings ({len(result.findings)}):"]
        for f in result.findings:
            lines.append(f"  [{f.severity}] {f.type}: {f.match}")
        lines.append(f"Blocked: {result.blocked}")
        lines.append(f"Recommendation: {result.recommendation}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /content-filter
    # ------------------------------------------------------------------

    async def content_filter_handler(args: str) -> str:
        from lidco.dlp.filter import ContentFilter, FilterRule

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        cf = ContentFilter()

        if sub == "add":
            tokens = rest.split()
            if len(tokens) < 3:
                return "Usage: /content-filter add <name> <pattern> <action>"
            rule = FilterRule(name=tokens[0], pattern=tokens[1], action=tokens[2])
            cf.add_rule(rule)
            return f"Added rule '{tokens[0]}'."

        if sub == "remove":
            name = rest.strip()
            if not name:
                return "Usage: /content-filter remove <name>"
            removed = cf.remove_rule(name)
            return f"Removed '{name}'." if removed else f"Rule '{name}' not found."

        if sub == "filter":
            if not rest:
                return "Usage: /content-filter filter <content>"
            filtered, result = cf.filter(rest)
            return f"Filtered ({result.original_length}->{result.filtered_length}): {filtered}"

        if sub == "list":
            rules = cf.rules()
            if not rules:
                return "No rules configured."
            lines = [f"  {r.name}: {r.pattern} ({r.action})" for r in rules]
            return "Rules:\n" + "\n".join(lines)

        return (
            "Usage: /content-filter <subcommand>\n"
            "  add <name> <pattern> <action>\n"
            "  remove <name>\n"
            "  filter <content>\n"
            "  list"
        )

    # ------------------------------------------------------------------
    # /watermark
    # ------------------------------------------------------------------

    async def watermark_handler(args: str) -> str:
        from lidco.dlp.watermark import WatermarkEngine

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        engine = WatermarkEngine()

        if sub == "embed":
            if not rest:
                return "Usage: /watermark embed <code>"
            code, wm = engine.embed(rest)
            return f"Watermarked (id={wm.id}, sig={wm.signature}). Length: {len(code)}"

        if sub == "detect":
            if not rest:
                return "Usage: /watermark detect <code>"
            wm = engine.detect(rest)
            if wm is None:
                return "No watermark detected."
            return f"Watermark: id={wm.id}, source={wm.source}, sig={wm.signature}"

        if sub == "strip":
            if not rest:
                return "Usage: /watermark strip <code>"
            stripped = engine.strip(rest)
            return f"Stripped. Length: {len(stripped)}"

        return (
            "Usage: /watermark <subcommand>\n"
            "  embed <code>\n"
            "  detect <code>\n"
            "  strip <code>"
        )

    # ------------------------------------------------------------------
    # /dlp-policy
    # ------------------------------------------------------------------

    async def dlp_policy_handler(args: str) -> str:
        from lidco.dlp.policy import DLPPolicyManager, DLPPolicy

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        mgr = DLPPolicyManager()

        if sub == "add":
            name = rest.strip()
            if not name:
                return "Usage: /dlp-policy add <name>"
            mgr.add_policy(DLPPolicy(name=name))
            return f"Added policy '{name}'."

        if sub == "remove":
            name = rest.strip()
            if not name:
                return "Usage: /dlp-policy remove <name>"
            removed = mgr.remove_policy(name)
            return f"Removed '{name}'." if removed else f"Policy '{name}' not found."

        if sub == "enable":
            name = rest.strip()
            if not name:
                return "Usage: /dlp-policy enable <name>"
            ok = mgr.enable(name)
            return f"Enabled '{name}'." if ok else f"Policy '{name}' not found."

        if sub == "disable":
            name = rest.strip()
            if not name:
                return "Usage: /dlp-policy disable <name>"
            ok = mgr.disable(name)
            return f"Disabled '{name}'." if ok else f"Policy '{name}' not found."

        if sub == "eval":
            if not rest:
                return "Usage: /dlp-policy eval <content>"
            evals = mgr.evaluate(rest)
            if not evals:
                return "No policies to evaluate."
            lines = [f"  {e.policy_name}: matched={e.matched}, severity={e.severity}" for e in evals]
            return "Evaluations:\n" + "\n".join(lines)

        if sub == "list":
            pols = mgr.policies()
            if not pols:
                return "No policies."
            lines = [f"  {p.name} (severity={p.severity}, enabled={p.enabled})" for p in pols]
            return "Policies:\n" + "\n".join(lines)

        return (
            "Usage: /dlp-policy <subcommand>\n"
            "  add <name>\n"
            "  remove <name>\n"
            "  enable <name>\n"
            "  disable <name>\n"
            "  eval <content>\n"
            "  list"
        )

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------
    registry.register(SlashCommand("dlp-scan", "Scan content for sensitive data", dlp_scan_handler))
    registry.register(SlashCommand("content-filter", "Filter content with allow/deny/redact rules", content_filter_handler))
    registry.register(SlashCommand("watermark", "Embed/detect/strip invisible watermarks", watermark_handler))
    registry.register(SlashCommand("dlp-policy", "Manage DLP policies", dlp_policy_handler))
