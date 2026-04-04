"""Q291 CLI commands — /jira, /jira-sync, /jira-sprint, /jira-report

Registered via register_q291_commands(registry).
"""
from __future__ import annotations

import shlex

# Module-level shared state so commands share a single client/planner
_state: dict = {}


def _ensure_state() -> dict:
    """Lazily initialise shared Jira state."""
    if "client" not in _state:
        from lidco.jira.client import JiraClient
        from lidco.jira.sync import IssueSync
        from lidco.jira.sprint import SprintPlanner
        from lidco.jira.reporter import JiraReporter

        client = JiraClient()
        client.add_project("PROJ", "Default Project")
        planner = SprintPlanner(client)
        _state["client"] = client
        _state["sync"] = IssueSync(client)
        _state["planner"] = planner
        _state["reporter"] = JiraReporter(planner)
    return _state


def register_q291_commands(registry) -> None:
    """Register Q291 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /jira [create <summary> | get <key> | search <jql> | projects | delete <key>]
    # ------------------------------------------------------------------
    async def jira_handler(args: str) -> str:
        state = _ensure_state()
        client = state["client"]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "projects"

        if subcmd == "create":
            summary = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not summary:
                return "Usage: /jira create <summary>"
            issue = client.create_issue(summary=summary)
            return f"Created {issue.key}: {issue.summary}"

        if subcmd == "get":
            if len(parts) < 2:
                return "Usage: /jira get <key>"
            try:
                issue = client.get_issue(parts[1])
                return (
                    f"{issue.key}: {issue.summary}\n"
                    f"Status: {issue.status} | Type: {issue.issue_type} | Priority: {issue.priority}"
                )
            except KeyError:
                return f"Issue {parts[1]} not found."

        if subcmd == "search":
            jql = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not jql:
                return "Usage: /jira search <jql>"
            results = client.search_jql(jql)
            if not results:
                return "No issues found."
            lines = [f"Found {len(results)} issue(s):"]
            for iss in results:
                lines.append(f"  {iss.key}: {iss.summary} [{iss.status}]")
            return "\n".join(lines)

        if subcmd == "delete":
            if len(parts) < 2:
                return "Usage: /jira delete <key>"
            try:
                client.delete_issue(parts[1])
                return f"Deleted {parts[1]}"
            except KeyError:
                return f"Issue {parts[1]} not found."

        if subcmd == "projects":
            projects = client.list_projects()
            if not projects:
                return "No projects."
            lines = [f"{len(projects)} project(s):"]
            for p in projects:
                lines.append(f"  {p.key}: {p.name}")
            return "\n".join(lines)

        return (
            "Usage: /jira <subcommand>\n"
            "  create <summary>  create issue\n"
            "  get <key>         get issue details\n"
            "  search <jql>      search issues\n"
            "  delete <key>      delete issue\n"
            "  projects          list projects"
        )

    # ------------------------------------------------------------------
    # /jira-sync [push <title> | pull | status <key> <status> | link-pr <key> <url> | pending | failed]
    # ------------------------------------------------------------------
    async def jira_sync_handler(args: str) -> str:
        state = _ensure_state()
        sync = state["sync"]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "pending"

        if subcmd == "push":
            title = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not title:
                return "Usage: /jira-sync push <title>"
            from lidco.jira.sync import TodoItem
            issues = sync.sync_from_todo([TodoItem(title=title)])
            if issues:
                return f"Synced to Jira: {issues[0].key}: {issues[0].summary}"
            return "Sync failed."

        if subcmd == "pull":
            jql = " ".join(parts[1:]) if len(parts) > 1 else ""
            todos = sync.sync_from_jira(jql)
            if not todos:
                return "No issues to pull."
            lines = [f"Pulled {len(todos)} item(s):"]
            for t in todos:
                status = "done" if t.done else "todo"
                lines.append(f"  [{status}] {t.issue_key}: {t.title}")
            return "\n".join(lines)

        if subcmd == "status":
            if len(parts) < 3:
                return "Usage: /jira-sync status <key> <status>"
            try:
                issue = sync.update_status(parts[1], parts[2])
                return f"Updated {issue.key} -> {issue.status}"
            except KeyError:
                return f"Issue {parts[1]} not found."

        if subcmd == "link-pr":
            if len(parts) < 3:
                return "Usage: /jira-sync link-pr <key> <pr_url>"
            try:
                sync.link_pr(parts[1], parts[2])
                return f"Linked PR {parts[2]} to {parts[1]}"
            except KeyError:
                return f"Issue {parts[1]} not found."

        if subcmd == "pending":
            pending = sync.pending_syncs()
            if not pending:
                return "No pending syncs."
            lines = [f"{len(pending)} pending sync(s):"]
            for r in pending:
                lines.append(f"  {r.issue_key}: {r.detail}")
            return "\n".join(lines)

        if subcmd == "failed":
            failed = sync.failed_syncs()
            if not failed:
                return "No failed syncs."
            lines = [f"{len(failed)} failed sync(s):"]
            for r in failed:
                lines.append(f"  {r.issue_key}: {r.detail}")
            return "\n".join(lines)

        return (
            "Usage: /jira-sync <subcommand>\n"
            "  push <title>              sync TODO to Jira\n"
            "  pull [jql]                pull issues as TODOs\n"
            "  status <key> <status>     update issue status\n"
            "  link-pr <key> <pr_url>    link PR to issue\n"
            "  pending                   show pending syncs\n"
            "  failed                    show failed syncs"
        )

    # ------------------------------------------------------------------
    # /jira-sprint [create <name> | start <id> | close <id> | add <id> <key> |
    #               estimate <key> <pts> | capacity <id> | list | issues <id>]
    # ------------------------------------------------------------------
    async def jira_sprint_handler(args: str) -> str:
        state = _ensure_state()
        planner = state["planner"]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "list"

        if subcmd == "create":
            name = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not name:
                return "Usage: /jira-sprint create <name>"
            sprint = planner.create_sprint(name)
            return f"Created sprint {sprint.id}: {sprint.name}"

        if subcmd == "start":
            if len(parts) < 2:
                return "Usage: /jira-sprint start <sprint_id>"
            try:
                sprint = planner.start_sprint(parts[1])
                return f"Started sprint {sprint.id}"
            except KeyError:
                return f"Sprint {parts[1]} not found."

        if subcmd == "close":
            if len(parts) < 2:
                return "Usage: /jira-sprint close <sprint_id>"
            try:
                sprint = planner.close_sprint(parts[1])
                return f"Closed sprint {sprint.id}"
            except KeyError:
                return f"Sprint {parts[1]} not found."

        if subcmd == "add":
            if len(parts) < 3:
                return "Usage: /jira-sprint add <sprint_id> <issue_key>"
            try:
                planner.add_issue(parts[1], parts[2])
                return f"Added {parts[2]} to {parts[1]}"
            except KeyError as e:
                return str(e)

        if subcmd == "estimate":
            if len(parts) < 3:
                return "Usage: /jira-sprint estimate <issue_key> <points>"
            try:
                pts = int(parts[2])
            except ValueError:
                return "Points must be an integer."
            try:
                result = planner.estimate(parts[1], pts)
                return f"Estimated {result['issue_key']} at {result['points']} points"
            except KeyError as e:
                return str(e)

        if subcmd == "capacity":
            if len(parts) < 2:
                return "Usage: /jira-sprint capacity <sprint_id>"
            try:
                cap = planner.capacity(parts[1])
                return (
                    f"Sprint {cap['sprint_name']}:\n"
                    f"  Capacity: {cap['capacity_points']} pts\n"
                    f"  Estimated: {cap['total_estimated']} pts\n"
                    f"  Remaining: {cap['remaining']} pts\n"
                    f"  Issues: {cap['issue_count']} ({cap['unestimated_count']} unestimated)"
                )
            except KeyError:
                return f"Sprint {parts[1]} not found."

        if subcmd == "issues":
            if len(parts) < 2:
                return "Usage: /jira-sprint issues <sprint_id>"
            try:
                issues = planner.sprint_issues(parts[1])
                if not issues:
                    return "No issues in sprint."
                lines = [f"{len(issues)} issue(s):"]
                for iss in issues:
                    lines.append(f"  {iss.key}: {iss.summary} [{iss.status}]")
                return "\n".join(lines)
            except KeyError:
                return f"Sprint {parts[1]} not found."

        if subcmd == "list":
            sprints = planner.list_sprints()
            if not sprints:
                return "No sprints."
            lines = [f"{len(sprints)} sprint(s):"]
            for s in sprints:
                lines.append(f"  {s.id}: {s.name} [{s.status}]")
            return "\n".join(lines)

        return (
            "Usage: /jira-sprint <subcommand>\n"
            "  create <name>                 create sprint\n"
            "  start <sprint_id>             start sprint\n"
            "  close <sprint_id>             close sprint\n"
            "  add <sprint_id> <issue_key>   add issue to sprint\n"
            "  estimate <key> <points>       set story points\n"
            "  capacity <sprint_id>          show capacity\n"
            "  issues <sprint_id>            list sprint issues\n"
            "  list                          list all sprints"
        )

    # ------------------------------------------------------------------
    # /jira-report [velocity | burndown <sprint_id> | prediction <sprint_id> | summary]
    # ------------------------------------------------------------------
    async def jira_report_handler(args: str) -> str:
        state = _ensure_state()
        reporter = state["reporter"]
        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "summary"

        if subcmd == "velocity":
            vel = reporter.velocity()
            if not vel:
                return "No closed sprints for velocity."
            lines = ["Velocity:"]
            for v in vel:
                lines.append(f"  {v.sprint_name}: {v.completed}/{v.committed} pts")
            return "\n".join(lines)

        if subcmd == "burndown":
            if len(parts) < 2:
                return "Usage: /jira-report burndown <sprint_id>"
            try:
                data = reporter.burndown(parts[1])
                lines = ["Burndown:"]
                for d in data:
                    lines.append(
                        f"  Day {d['day']}: {d['remaining_points']} remaining, "
                        f"{d['completed_points']} completed"
                    )
                return "\n".join(lines)
            except KeyError:
                return f"Sprint {parts[1]} not found."

        if subcmd == "prediction":
            if len(parts) < 2:
                return "Usage: /jira-report prediction <sprint_id>"
            try:
                pred = reporter.completion_prediction(parts[1])
                return (
                    f"Prediction for {pred['sprint_id']}:\n"
                    f"  Total: {pred['total_points']} pts\n"
                    f"  Completed: {pred['completed_points']} pts\n"
                    f"  Remaining: {pred['remaining_points']} pts\n"
                    f"  Avg velocity: {pred['avg_velocity']}\n"
                    f"  Est. days remaining: {pred['estimated_days_remaining']}\n"
                    f"  On track: {pred['on_track']}"
                )
            except KeyError:
                return f"Sprint {parts[1]} not found."

        if subcmd == "summary":
            s = reporter.summary()
            return (
                f"Jira Summary:\n"
                f"  Sprints: {s['total_sprints']} "
                f"(closed: {s['closed_sprints']}, active: {s['active_sprints']}, "
                f"future: {s['future_sprints']})\n"
                f"  Committed: {s['total_committed']} pts\n"
                f"  Completed: {s['total_completed']} pts\n"
                f"  Avg velocity: {s['average_velocity']}"
            )

        return (
            "Usage: /jira-report <subcommand>\n"
            "  velocity                 sprint velocity\n"
            "  burndown <sprint_id>     burndown chart\n"
            "  prediction <sprint_id>   completion prediction\n"
            "  summary                  overall summary"
        )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    from lidco.cli.commands import SlashCommand

    registry.register(SlashCommand("jira", "Jira issue management", jira_handler))
    registry.register(SlashCommand("jira-sync", "Bi-directional Jira sync", jira_sync_handler))
    registry.register(SlashCommand("jira-sprint", "Sprint planning", jira_sprint_handler))
    registry.register(SlashCommand("jira-report", "Sprint reports and analytics", jira_report_handler))
