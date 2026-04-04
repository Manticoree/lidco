"""Q293 CLI commands — /linear, /linear-issue, /linear-cycle, /linear-dashboard

Registered via register_q293_commands(registry).
"""
from __future__ import annotations

import shlex
import time

from lidco.cli.commands.registry import SlashCommand


def register_q293_commands(registry) -> None:
    """Register Q293 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /linear [teams | issues <team> | issue <id>]
    # ------------------------------------------------------------------
    async def linear_handler(args: str) -> str:
        from lidco.linear.client import LinearClient

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else "teams"
        client = LinearClient()

        if subcmd == "teams":
            teams = client.list_teams()
            lines = [f"Teams ({len(teams)}):"]
            for t in teams:
                lines.append(f"  [{t.key}] {t.name} (id={t.id})")
            return "\n".join(lines)

        if subcmd == "issues":
            team = parts[1] if len(parts) > 1 else "Engineering"
            issues = client.list_issues(team)
            if not issues:
                return f"No issues for team '{team}'."
            lines = [f"Issues for {team} ({len(issues)}):"]
            for iss in issues:
                lines.append(f"  {iss.id}: [{iss.status}] {iss.title}")
            return "\n".join(lines)

        if subcmd == "issue":
            if len(parts) < 2:
                return "Usage: /linear issue <id>"
            try:
                issue = client.get_issue(parts[1])
                return (
                    f"Issue {issue.id}\n"
                    f"  Title: {issue.title}\n"
                    f"  Status: {issue.status}\n"
                    f"  Team: {issue.team}\n"
                    f"  Priority: {issue.priority}"
                )
            except KeyError:
                return f"Issue not found: {parts[1]}"

        return "Usage: /linear [teams | issues <team> | issue <id>]"

    # ------------------------------------------------------------------
    # /linear-issue [create <title> <team> | status <id> <status> | link <id> <url>]
    # ------------------------------------------------------------------
    async def linear_issue_handler(args: str) -> str:
        from lidco.linear.tracker import IssueTracker

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else ""
        tracker = IssueTracker()

        if subcmd == "create":
            if len(parts) < 3:
                return "Usage: /linear-issue create <title> <team>"
            title = parts[1]
            team = parts[2]
            file = parts[3] if len(parts) > 3 else "unknown"
            issue = tracker.create_from_code(title, file, team=team)
            return f"Created issue {issue.id}: {issue.title} ({issue.team})"

        if subcmd == "status":
            if len(parts) < 3:
                return "Usage: /linear-issue status <id> <status>"
            try:
                issue = tracker.update_status(parts[1], parts[2])
                return f"Updated {issue.id} -> {issue.status}"
            except (KeyError, ValueError) as exc:
                return str(exc)

        if subcmd == "auto-status":
            branch = parts[1] if len(parts) > 1 else "main"
            status = tracker.auto_status(branch)
            return f"Branch '{branch}' -> status: {status}"

        if subcmd == "link":
            if len(parts) < 3:
                return "Usage: /linear-issue link <id> <pr_url>"
            try:
                tracker.link_pr(parts[1], parts[2])
                return f"Linked PR {parts[2]} to {parts[1]}"
            except KeyError as exc:
                return str(exc)

        return "Usage: /linear-issue [create|status|auto-status|link] ..."

    # ------------------------------------------------------------------
    # /linear-cycle [create <name> | scope <id> | estimates <id> | add <cycle> <issue>]
    # ------------------------------------------------------------------
    async def linear_cycle_handler(args: str) -> str:
        from lidco.linear.cycle import CyclePlanner

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else ""
        planner = CyclePlanner()

        if subcmd == "create":
            if len(parts) < 2:
                return "Usage: /linear-cycle create <name>"
            name = parts[1]
            now = time.time()
            cycle = planner.create_cycle(name, now, now + 14 * 86400)
            return f"Created cycle {cycle.id}: {cycle.name}"

        if subcmd == "scope":
            if len(parts) < 2:
                return "Usage: /linear-cycle scope <cycle_id>"
            try:
                scope = planner.scope(parts[1])
                return (
                    f"Cycle: {scope['cycle_name']}\n"
                    f"Total: {scope['total']}\n"
                    f"By status: {scope['by_status']}"
                )
            except KeyError as exc:
                return str(exc)

        if subcmd == "estimates":
            if len(parts) < 2:
                return "Usage: /linear-cycle estimates <cycle_id>"
            try:
                est = planner.estimates(parts[1])
                return (
                    f"Total points: {est['total_points']}\n"
                    f"Avg priority: {est['avg_priority']:.1f}\n"
                    f"Items: {len(est['items'])}"
                )
            except KeyError as exc:
                return str(exc)

        return "Usage: /linear-cycle [create|scope|estimates] ..."

    # ------------------------------------------------------------------
    # /linear-dashboard [velocity <team> | dist <team> | progress <id> | sla <team>]
    # ------------------------------------------------------------------
    async def linear_dashboard_handler(args: str) -> str:
        from lidco.linear.dashboard import LinearDashboard

        parts = shlex.split(args) if args.strip() else []
        subcmd = parts[0] if parts else ""
        dash = LinearDashboard()

        if subcmd == "velocity":
            team = parts[1] if len(parts) > 1 else "Engineering"
            vel = dash.velocity(team)
            if not vel:
                return f"No velocity data for '{team}'."
            lines = [f"Velocity for {team}:"]
            for v in vel:
                lines.append(
                    f"  {v['name']}: {v['completed']}/{v['total']} completed"
                )
            return "\n".join(lines)

        if subcmd == "dist":
            team = parts[1] if len(parts) > 1 else "Engineering"
            dist = dash.distribution(team)
            if not dist:
                return f"No issues for team '{team}'."
            lines = [f"Distribution for {team}:"]
            for status, count in sorted(dist.items()):
                lines.append(f"  {status}: {count}")
            return "\n".join(lines)

        if subcmd == "progress":
            if len(parts) < 2:
                return "Usage: /linear-dashboard progress <cycle_id>"
            try:
                prog = dash.cycle_progress(parts[1])
                return (
                    f"Cycle: {prog['name']}\n"
                    f"Progress: {prog['completed']}/{prog['total']}"
                    f" ({prog['percent']}%)\n"
                    f"Time remaining: {prog['time_remaining_s']:.0f}s"
                )
            except KeyError as exc:
                return str(exc)

        if subcmd == "sla":
            team = parts[1] if len(parts) > 1 else "Engineering"
            sla = dash.sla_tracking(team)
            if not sla:
                return f"No open SLA items for '{team}'."
            lines = [f"SLA for {team} ({len(sla)} open):"]
            for item in sla:
                flag = "OK" if item["within_sla"] else "BREACH"
                lines.append(
                    f"  {item['issue_id']}: P{item['priority']}"
                    f" ({item['elapsed_hours']:.1f}h / {item['sla_hours']:.0f}h)"
                    f" [{flag}]"
                )
            return "\n".join(lines)

        return "Usage: /linear-dashboard [velocity|dist|progress|sla] ..."

    registry.register(SlashCommand("linear", "Linear integration — teams, issues", linear_handler))
    registry.register(SlashCommand("linear-issue", "Linear issue tracker — create, status, link", linear_issue_handler))
    registry.register(SlashCommand("linear-cycle", "Linear cycle planner — create, scope, estimates", linear_cycle_handler))
    registry.register(SlashCommand("linear-dashboard", "Linear dashboard — velocity, distribution, SLA", linear_dashboard_handler))
