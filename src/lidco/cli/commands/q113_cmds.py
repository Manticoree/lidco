"""Q113 CLI commands: /bugbot /session-tags /lint-hook."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q113 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /bugbot                                                              #
    # ------------------------------------------------------------------ #

    async def bugbot_handler(args: str) -> str:
        from lidco.review.bugbot_pr_trigger import BugBotPRTrigger, PREvent, BugBotFinding, BugSeverity
        from lidco.review.bugbot_fix_agent import BugBotFixAgent
        from lidco.review.bugbot_pr_poster import BugBotPRPoster

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "check":
            if not rest:
                return "Usage: /bugbot check <diff_text>"
            trigger = BugBotPRTrigger()
            event = PREvent(pr_number=0, repo="local", diff=rest)
            findings = trigger.process_pr_event(event)
            if not findings:
                return "No issues found in diff."
            lines = [f"Found {len(findings)} issue(s):"]
            for f in findings:
                lines.append(f"  [{f.severity.value.upper()}] {f.file}:{f.line} — {f.message} ({f.rule_id})")
            return "\n".join(lines)

        if sub == "fix":
            if not rest:
                return "Usage: /bugbot fix <finding_json>"
            try:
                data = json.loads(rest)
            except json.JSONDecodeError as e:
                return f"Invalid JSON: {e}"
            try:
                sev = BugSeverity(data.get("severity", "low"))
            except ValueError:
                sev = BugSeverity.LOW
            finding = BugBotFinding(
                file=data.get("file", "unknown"),
                line=data.get("line", 0),
                severity=sev,
                message=data.get("message", ""),
                rule_id=data.get("rule_id", "unknown"),
                suggested_fix=data.get("suggested_fix"),
            )
            agent = BugBotFixAgent()
            proposal = agent.generate_fix(finding, data.get("source", ""))
            lines = [
                f"Fix proposal for {finding.file}:{finding.line}:",
                f"  Rule: {finding.rule_id}",
                f"  Confidence: {proposal.confidence:.0%}",
                f"  Rationale: {proposal.rationale}",
            ]
            if proposal.patch:
                lines.append(f"  Patch: {proposal.patch}")
            return "\n".join(lines)

        if sub == "post":
            dry_run = "--dry-run" in rest
            poster = BugBotPRPoster()
            # In CLI context, we just report that posting requires proposals
            if "bugbot_proposals" not in _state:
                return "No proposals to post. Run /bugbot check first."
            proposals = _state["bugbot_proposals"]
            result = poster.post(proposals, pr_number=0, dry_run=dry_run)  # type: ignore[arg-type]
            mode = " (dry-run)" if dry_run else ""
            return f"Posted{mode}: {result.posted}, Skipped: {result.skipped}, Errors: {len(result.errors)}"

        return (
            "Usage: /bugbot <sub>\n"
            "  check <diff_text>     — scan diff for bugs\n"
            "  fix <finding_json>    — generate fix for finding\n"
            "  post [--dry-run]      — post findings to PR"
        )

    # ------------------------------------------------------------------ #
    # /session-tags                                                        #
    # ------------------------------------------------------------------ #

    async def session_tags_handler(args: str) -> str:
        from lidco.memory.session_tags import SessionTagStore

        def _get_store() -> SessionTagStore:
            if "session_tag_store" not in _state:
                _state["session_tag_store"] = SessionTagStore()
            return _state["session_tag_store"]  # type: ignore[return-value]

        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "tag":
            if len(parts) < 3:
                return "Usage: /session-tags tag <session_id> <tag1,tag2>"
            session_id = parts[1]
            tags = [t.strip() for t in parts[2].split(",") if t.strip()]
            store = _get_store()
            store.tag(session_id, tags)
            return f"Tagged session '{session_id}' with: {', '.join(tags)}"

        if sub == "search":
            query = parts[1] if len(parts) > 1 else ""
            if not query:
                return "Usage: /session-tags search <query>"
            store = _get_store()
            results = store.search(query)
            if not results:
                return f"No sessions found matching '{query}'."
            lines = [f"Found {len(results)} session(s):"]
            for r in results:
                lines.append(f"  {r.session_id}: [{', '.join(r.tags)}]")
            return "\n".join(lines)

        if sub == "list":
            store = _get_store()
            all_tags = store.list_all()
            if not all_tags:
                return "No tagged sessions."
            lines = [f"{len(all_tags)} tagged session(s):"]
            for t in all_tags:
                lines.append(f"  {t.session_id}: [{', '.join(t.tags)}]")
            return "\n".join(lines)

        return (
            "Usage: /session-tags <sub>\n"
            "  tag <session_id> <tag1,tag2>  — tag a session\n"
            "  search <query>               — search by tag\n"
            "  list                         — list all tagged sessions"
        )

    # ------------------------------------------------------------------ #
    # /lint-hook                                                           #
    # ------------------------------------------------------------------ #

    async def lint_hook_handler(args: str) -> str:
        from lidco.editing.post_edit_lint import PostEditLintHook

        def _get_hook() -> PostEditLintHook:
            if "lint_hook" not in _state:
                _state["lint_hook"] = PostEditLintHook()
            return _state["lint_hook"]  # type: ignore[return-value]

        sub = args.strip().lower()

        if sub == "enable":
            hook = _get_hook()
            hook.enable()
            return "Post-edit lint hook enabled."

        if sub == "disable":
            hook = _get_hook()
            hook.disable()
            return "Post-edit lint hook disabled."

        if sub == "status":
            hook = _get_hook()
            status = "enabled" if hook.enabled else "disabled"
            return f"Post-edit lint hook is {status}."

        return (
            "Usage: /lint-hook <sub>\n"
            "  enable   — enable post-edit lint hook\n"
            "  disable  — disable post-edit lint hook\n"
            "  status   — show hook status"
        )

    registry.register(SlashCommand("bugbot", "BugBot PR autofix pipeline", bugbot_handler))
    registry.register(SlashCommand("session-tags", "Session tagging", session_tags_handler))
    registry.register(SlashCommand("lint-hook", "Post-edit lint hook", lint_hook_handler))
