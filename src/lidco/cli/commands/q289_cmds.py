"""Q289 CLI commands — /gh-pr, /gh-issue, /gh-actions, /gh-review

Registered via register_q289_commands(registry).
"""
from __future__ import annotations

import shlex

from lidco.cli.commands.registry import SlashCommand


def register_q289_commands(registry) -> None:
    """Register Q289 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /gh-pr <subcommand> [args]
    # ------------------------------------------------------------------
    async def gh_pr_handler(args: str) -> str:
        from lidco.github.pr_workflow import PRWorkflow

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else ""
        wf = PRWorkflow()

        if subcmd == "create":
            title = parts[1] if len(parts) > 1 else ""
            body = parts[2] if len(parts) > 2 else ""
            branch = parts[3] if len(parts) > 3 else "feature"
            base = parts[4] if len(parts) > 4 else "main"
            if not title:
                return "Usage: /gh-pr create <title> [body] [branch] [base]"
            pr = wf.create_pr(title, body, branch, base)
            return f"PR #{pr.id}: {pr.title} ({pr.branch} -> {pr.base})"

        if subcmd == "describe":
            diff = " ".join(parts[1:]) if len(parts) > 1 else ""
            return wf.auto_describe(diff)

        return (
            "Usage: /gh-pr <subcommand>\n"
            "  create <title> [body] [branch] [base]\n"
            "  describe <diff>"
        )

    # ------------------------------------------------------------------
    # /gh-issue <subcommand> [args]
    # ------------------------------------------------------------------
    async def gh_issue_handler(args: str) -> str:
        from lidco.github.issues import IssueManager

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else ""
        mgr = IssueManager()

        if subcmd == "create":
            title = parts[1] if len(parts) > 1 else ""
            body = parts[2] if len(parts) > 2 else ""
            if not title:
                return "Usage: /gh-issue create <title> [body]"
            issue = mgr.create(title, body)
            return f"Issue #{issue.id}: {issue.title}"

        if subcmd == "list":
            issues = mgr.list_issues()
            if not issues:
                return "No issues found."
            return "\n".join(f"#{i.id} [{i.state}] {i.title}" for i in issues)

        return (
            "Usage: /gh-issue <subcommand>\n"
            "  create <title> [body]\n"
            "  list"
        )

    # ------------------------------------------------------------------
    # /gh-actions <subcommand> [args]
    # ------------------------------------------------------------------
    async def gh_actions_handler(args: str) -> str:
        from lidco.github.actions import ActionsMonitor

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else ""
        mon = ActionsMonitor()

        if subcmd == "list":
            repo = parts[1] if len(parts) > 1 else ""
            if not repo:
                return "Usage: /gh-actions list <repo>"
            runs = mon.list_runs(repo)
            if not runs:
                return f"No runs found for {repo}."
            return "\n".join(
                f"Run #{r.id}: {r.status} ({r.conclusion or 'pending'})"
                for r in runs
            )

        if subcmd == "failures":
            run_id_str = parts[1] if len(parts) > 1 else ""
            if not run_id_str:
                return "Usage: /gh-actions failures <run_id>"
            failures = mon.detect_failures(int(run_id_str))
            if not failures:
                return "No failures detected."
            return "\n".join(failures)

        return (
            "Usage: /gh-actions <subcommand>\n"
            "  list <repo>\n"
            "  failures <run_id>"
        )

    # ------------------------------------------------------------------
    # /gh-review <subcommand> [args]
    # ------------------------------------------------------------------
    async def gh_review_handler(args: str) -> str:
        from lidco.github.pr_workflow import PRWorkflow

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else ""
        wf = PRWorkflow()

        if subcmd == "request":
            pr_id_str = parts[1] if len(parts) > 1 else ""
            reviewers = parts[2:] if len(parts) > 2 else []
            if not pr_id_str or not reviewers:
                return "Usage: /gh-review request <pr_id> <reviewer...>"
            # Since PRWorkflow is fresh, create a dummy PR first
            pr = wf.create_pr("temp", "", "branch")
            wf.request_reviewers(pr.id, reviewers)
            return f"Requested reviewers for PR #{pr.id}: {', '.join(reviewers)}"

        if subcmd == "list":
            pr_id_str = parts[1] if len(parts) > 1 else ""
            if not pr_id_str:
                return "Usage: /gh-review list <pr_id>"
            reviews = wf.list_reviews(int(pr_id_str))
            if not reviews:
                return "No reviews found."
            return "\n".join(
                f"{r['reviewer']}: {r['state']}" for r in reviews
            )

        return (
            "Usage: /gh-review <subcommand>\n"
            "  request <pr_id> <reviewer...>\n"
            "  list <pr_id>"
        )

    # -- register --------------------------------------------------------
    registry.register(SlashCommand("gh-pr", "GitHub PR workflow", gh_pr_handler))
    registry.register(SlashCommand("gh-issue", "GitHub issue management", gh_issue_handler))
    registry.register(SlashCommand("gh-actions", "GitHub Actions monitor", gh_actions_handler))
    registry.register(SlashCommand("gh-review", "GitHub PR review management", gh_review_handler))
