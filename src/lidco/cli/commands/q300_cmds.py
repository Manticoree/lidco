"""
Q300 CLI commands — /pr-description, /pr-reviewer, /pr-checklist, /pr-status

Registered via register_q300_commands(registry).
"""
from __future__ import annotations

import shlex


def register_q300_commands(registry) -> None:
    """Register Q300 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /pr-description — Generate PR description from diff
    # ------------------------------------------------------------------
    async def pr_description_handler(args: str) -> str:
        """
        Usage: /pr-description <diff-text>
               /pr-description --file <path>
        """
        from lidco.pr.description import PRDescriptionGenerator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /pr-description <diff-text>\n"
                "       /pr-description --file <path>\n"
                "Generate a PR description from a unified diff."
            )

        gen = PRDescriptionGenerator()

        if parts[0] == "--file" and len(parts) >= 2:
            from pathlib import Path
            try:
                diff = Path(parts[1]).read_text(encoding="utf-8")
            except FileNotFoundError:
                return f"Error: file not found: {parts[1]}"
        else:
            diff = " ".join(parts)

        body = gen.generate([], diff)
        return body

    registry.register_async("pr-description", "Generate PR description from diff", pr_description_handler)

    # ------------------------------------------------------------------
    # /pr-reviewer — Suggest reviewers for files
    # ------------------------------------------------------------------
    _reviewer_state: dict[str, object] = {}

    async def pr_reviewer_handler(args: str) -> str:
        """
        Usage: /pr-reviewer suggest <file1> [file2 ...]
               /pr-reviewer add-owner <pattern> <user>
               /pr-reviewer add-codeowner <pattern> <team>
               /pr-reviewer activity <user>
        """
        from lidco.pr.reviewer import PRReviewerMatcher

        if "matcher" not in _reviewer_state:
            _reviewer_state["matcher"] = PRReviewerMatcher()

        matcher: PRReviewerMatcher = _reviewer_state["matcher"]  # type: ignore[assignment]

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /pr-reviewer <subcommand>\n"
                "  suggest <file1> [file2 ...]    suggest reviewers\n"
                "  add-owner <pattern> <user>     register file owner\n"
                "  add-codeowner <pattern> <team> register codeowner\n"
                "  activity <user>                show review activity count"
            )

        subcmd = parts[0].lower()

        if subcmd == "suggest":
            if len(parts) < 2:
                return "Error: at least one file required."
            reviewers = matcher.suggest(parts[1:])
            if not reviewers:
                return "No reviewers matched for the given files."
            lines = [f"  {r.user} — {r.reason} (score: {r.score})" for r in reviewers]
            return "Suggested reviewers:\n" + "\n".join(lines)

        if subcmd == "add-owner":
            if len(parts) < 3:
                return "Error: Usage: /pr-reviewer add-owner <pattern> <user>"
            matcher.add_owner(parts[1], parts[2])
            return f"Owner added: {parts[2]} for pattern '{parts[1]}'"

        if subcmd == "add-codeowner":
            if len(parts) < 3:
                return "Error: Usage: /pr-reviewer add-codeowner <pattern> <team>"
            matcher.add_codeowner(parts[1], parts[2])
            return f"Codeowner added: {parts[2]} for pattern '{parts[1]}'"

        if subcmd == "activity":
            if len(parts) < 2:
                return "Error: user required."
            count = matcher.recent_activity(parts[1])
            return f"Review activity for {parts[1]}: {count} event(s)"

        return f"Unknown subcommand '{subcmd}'. Use suggest/add-owner/add-codeowner/activity."

    registry.register_async("pr-reviewer", "Suggest PR reviewers based on file ownership", pr_reviewer_handler)

    # ------------------------------------------------------------------
    # /pr-checklist — Generate PR checklist
    # ------------------------------------------------------------------
    async def pr_checklist_handler(args: str) -> str:
        """
        Usage: /pr-checklist generate <type>       (feature|bugfix|refactor)
               /pr-checklist security <diff-text>
               /pr-checklist deploy <diff-text>
        """
        from lidco.pr.checklist import PRChecklistGenerator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /pr-checklist <subcommand>\n"
                "  generate <type>       generate checklist (feature/bugfix/refactor)\n"
                "  security <diff-text>  show security checks for diff\n"
                "  deploy <diff-text>    show deployment notes for diff"
            )

        subcmd = parts[0].lower()
        gen = PRChecklistGenerator()

        if subcmd == "generate":
            pr_type = parts[1] if len(parts) >= 2 else "feature"
            checklist = gen.generate(pr_type)
            return checklist.as_markdown()

        if subcmd == "security":
            diff = " ".join(parts[1:]) if len(parts) > 1 else ""
            checks = gen.security_checks(diff)
            if not checks:
                return "No security concerns detected."
            return "Security checks:\n" + "\n".join(f"  - {c}" for c in checks)

        if subcmd == "deploy":
            diff = " ".join(parts[1:]) if len(parts) > 1 else ""
            notes = gen.deployment_notes(diff)
            if not notes:
                return "No deployment notes."
            return "Deployment notes:\n" + "\n".join(f"  - {n}" for n in notes)

        return f"Unknown subcommand '{subcmd}'. Use generate/security/deploy."

    registry.register_async("pr-checklist", "Generate PR checklists", pr_checklist_handler)

    # ------------------------------------------------------------------
    # /pr-status — Track PR readiness
    # ------------------------------------------------------------------
    _status_state: dict[str, object] = {}

    async def pr_status_handler(args: str) -> str:
        """
        Usage: /pr-status track <pr-id>
               /pr-status ci <pr-id> <passed|failed|running|pending>
               /pr-status review <pr-id> <reviewer> <approve|reject>
               /pr-status check <pr-id>
               /pr-status list
        """
        from lidco.pr.status import PRStatusTracker

        if "tracker" not in _status_state:
            _status_state["tracker"] = PRStatusTracker()

        tracker: PRStatusTracker = _status_state["tracker"]  # type: ignore[assignment]

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /pr-status <subcommand>\n"
                "  track <pr-id>                           start tracking\n"
                "  ci <pr-id> <status>                     update CI status\n"
                "  review <pr-id> <reviewer> approve|reject  record review\n"
                "  check <pr-id>                           check readiness\n"
                "  list                                    list tracked PRs"
            )

        subcmd = parts[0].lower()

        if subcmd == "track":
            if len(parts) < 2:
                return "Error: PR ID required."
            pr = tracker.track(parts[1])
            return f"Tracking PR {pr.pr_id} — CI: {pr.ci_status.value}, approvals: {pr.approval_count}/{pr.required_approvals}"

        if subcmd == "ci":
            if len(parts) < 3:
                return "Error: Usage: /pr-status ci <pr-id> <status>"
            try:
                pr = tracker.update_ci(parts[1], parts[2])
            except ValueError as exc:
                return f"Error: {exc}"
            return f"PR {pr.pr_id} CI updated: {pr.ci_status.value}"

        if subcmd == "review":
            if len(parts) < 4:
                return "Error: Usage: /pr-status review <pr-id> <reviewer> approve|reject"
            approved = parts[3].lower() == "approve"
            pr = tracker.update_review(parts[1], parts[2], approved)
            status_word = "approved" if approved else "rejected"
            return f"PR {pr.pr_id}: {parts[2]} {status_word}. Approvals: {pr.approval_count}/{pr.required_approvals}"

        if subcmd == "check":
            if len(parts) < 2:
                return "Error: PR ID required."
            ready = tracker.is_ready(parts[1])
            merge = tracker.auto_merge_eligible(parts[1])
            pr = tracker.track(parts[1])
            lines = [
                f"PR {pr.pr_id}:",
                f"  CI: {pr.ci_status.value}",
                f"  Approvals: {pr.approval_count}/{pr.required_approvals}",
                f"  Ready to merge: {'yes' if ready else 'no'}",
                f"  Auto-merge eligible: {'yes' if merge else 'no'}",
            ]
            return "\n".join(lines)

        if subcmd == "list":
            ids = tracker.list_tracked()
            if not ids:
                return "No PRs being tracked."
            return "Tracked PRs:\n" + "\n".join(f"  {pid}" for pid in ids)

        return f"Unknown subcommand '{subcmd}'. Use track/ci/review/check/list."

    registry.register_async("pr-status", "Track PR readiness and merge eligibility", pr_status_handler)
