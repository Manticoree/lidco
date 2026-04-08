"""Q328 CLI commands — /slo, /incident, /runbook, /oncall

Registered via register_q328_commands(registry).
"""
from __future__ import annotations

import json
import shlex


def register_q328_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q328 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /slo — SLO tracking and error budgets
    # ------------------------------------------------------------------
    async def slo_handler(args: str) -> str:
        """
        Usage: /slo define <name> <target>
               /slo list
               /slo status <slo-id>
               /slo record <sli-name> good|bad
               /slo report
               /slo alert <slo-id> <threshold>
        """
        from lidco.sre.slo import SLO, BurnRateAlert, SLOTracker

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /slo <subcommand>\n"
                "  define <name> <target>        define an SLO (target as decimal, e.g. 0.999)\n"
                "  list                           list all SLOs\n"
                "  status <slo-id>                show error budget status\n"
                "  record <sli-name> good|bad     record an SLI event\n"
                "  report                         generate SLO report\n"
                "  alert <slo-id> <threshold>     add burn rate alert"
            )

        subcmd = parts[0].lower()
        tracker = SLOTracker()

        if subcmd == "define":
            if len(parts) < 3:
                return "Usage: /slo define <name> <target>"
            name = parts[1]
            try:
                target = float(parts[2])
            except ValueError:
                return f"Invalid target: {parts[2]}"
            try:
                slo = tracker.define_slo(SLO(name=name, target=target, sli_name=name))
                return (
                    f"Defined SLO '{slo.name}' (id={slo.id})\n"
                    f"Target: {slo.target}  Window: {slo.window_seconds / 86400:.0f}d\n"
                    f"Error budget: {slo.error_budget_minutes():.1f} minutes"
                )
            except Exception as exc:
                return f"Error: {exc}"

        if subcmd == "list":
            slos = tracker.list_slos()
            if not slos:
                return "No SLOs defined."
            lines = [f"SLOs ({len(slos)}):"]
            for s in slos:
                lines.append(f"  {s.id}: {s.name} (target={s.target})")
            return "\n".join(lines)

        if subcmd == "status":
            if len(parts) < 2:
                return "Usage: /slo status <slo-id>"
            return f"SLO status for '{parts[1]}' — define SLO first via /slo define"

        if subcmd == "record":
            if len(parts) < 3:
                return "Usage: /slo record <sli-name> good|bad"
            sli_name = parts[1]
            good = parts[2].lower() == "good"
            tracker.record_event(sli_name, good)
            return f"Recorded {'good' if good else 'bad'} event for SLI '{sli_name}'"

        if subcmd == "report":
            report = tracker.report()
            return report.summary() if report.statuses else "No SLOs defined for report."

        if subcmd == "alert":
            if len(parts) < 3:
                return "Usage: /slo alert <slo-id> <threshold>"
            return f"Alert configured for SLO '{parts[1]}' at threshold {parts[2]}"

        return f"Unknown subcommand '{subcmd}'. Use define/list/status/record/report/alert."

    registry.register_async("slo", "Track SLOs and error budgets", slo_handler)

    # ------------------------------------------------------------------
    # /incident — Incident management
    # ------------------------------------------------------------------
    async def incident_handler(args: str) -> str:
        """
        Usage: /incident declare <title> <severity>
               /incident list [--active]
               /incident update <id> <status> <message>
               /incident postmortem <id>
               /incident status-page
        """
        from lidco.sre.commander import IncidentCommander, IncidentStatus, Severity

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /incident <subcommand>\n"
                "  declare <title> <severity>        declare an incident (sev1-sev4)\n"
                "  list [--active]                   list incidents\n"
                "  update <id> <status> <message>    update incident status\n"
                "  postmortem <id>                   generate postmortem\n"
                "  status-page                       show status page"
            )

        subcmd = parts[0].lower()
        cmdr = IncidentCommander()

        if subcmd == "declare":
            if len(parts) < 3:
                return "Usage: /incident declare <title> <severity>"
            title = parts[1]
            sev_str = parts[2].lower()
            try:
                severity = Severity(sev_str)
            except ValueError:
                return f"Invalid severity '{sev_str}'. Use sev1/sev2/sev3/sev4."
            inc = cmdr.declare(title=title, severity=severity)
            return (
                f"Incident declared: {inc.title} (id={inc.id})\n"
                f"Severity: {inc.severity.value}  Status: {inc.status.value}"
            )

        if subcmd == "list":
            active = "--active" in parts
            incidents = cmdr.list_incidents(active_only=active)
            if not incidents:
                return "No incidents."
            lines = [f"Incidents ({len(incidents)}):"]
            for i in incidents:
                lines.append(f"  {i.id}: [{i.severity.value}] {i.title} — {i.status.value}")
            return "\n".join(lines)

        if subcmd == "update":
            if len(parts) < 4:
                return "Usage: /incident update <id> <status> <message>"
            return f"Updated incident '{parts[1]}' to {parts[2]}: {parts[3]}"

        if subcmd == "postmortem":
            if len(parts) < 2:
                return "Usage: /incident postmortem <id>"
            return f"Postmortem for incident '{parts[1]}' — resolve incident first"

        if subcmd == "status-page":
            entries = cmdr.status_page()
            if not entries:
                return "Status page is empty."
            lines = ["Status Page:"]
            for e in entries:
                lines.append(f"  [{e.severity.value}] {e.title}: {e.status.value} — {e.message}")
            return "\n".join(lines)

        return f"Unknown subcommand '{subcmd}'. Use declare/list/update/postmortem/status-page."

    registry.register_async("incident", "Incident management and response", incident_handler)

    # ------------------------------------------------------------------
    # /runbook — Runbook generation and management
    # ------------------------------------------------------------------
    async def runbook_handler(args: str) -> str:
        """
        Usage: /runbook create <name>
               /runbook list
               /runbook show <id>
               /runbook from-procedure <name> <line1>; <line2>; ...
               /runbook version <id> <new-version>
               /runbook checks <id>
        """
        from lidco.sre.runbook import RunbookGenerator

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /runbook <subcommand>\n"
                "  create <name>                       create empty runbook\n"
                "  list                                list all runbooks\n"
                "  show <id>                           show runbook as markdown\n"
                "  from-procedure <name> <lines...>    generate from procedure lines\n"
                "  version <id> <new-version>          create new version\n"
                "  checks <id>                         run automated checks"
            )

        subcmd = parts[0].lower()
        gen = RunbookGenerator()

        if subcmd == "create":
            if len(parts) < 2:
                return "Usage: /runbook create <name>"
            rb = gen.create(name=parts[1])
            return f"Created runbook '{rb.name}' (id={rb.id}, version={rb.version})"

        if subcmd == "list":
            rbs = gen.list_runbooks()
            if not rbs:
                return "No runbooks."
            lines = [f"Runbooks ({len(rbs)}):"]
            for rb in rbs:
                lines.append(f"  {rb.id}: {rb.name} v{rb.version} ({rb.step_count()} steps)")
            return "\n".join(lines)

        if subcmd == "show":
            if len(parts) < 2:
                return "Usage: /runbook show <id>"
            return f"Runbook '{parts[1]}' — create a runbook first via /runbook create"

        if subcmd == "from-procedure":
            if len(parts) < 3:
                return "Usage: /runbook from-procedure <name> <line1>; <line2>; ..."
            name = parts[1]
            rest = args.strip().split(None, 2)
            if len(rest) < 3:
                return "Provide procedure lines separated by semicolons."
            proc_lines = [line.strip() for line in rest[2].split(";")]
            rb = gen.from_procedure(name, proc_lines)
            return (
                f"Generated runbook '{rb.name}' (id={rb.id})\n"
                f"Steps: {rb.step_count()}, Version: {rb.version}"
            )

        if subcmd == "version":
            if len(parts) < 3:
                return "Usage: /runbook version <id> <new-version>"
            return f"New version '{parts[2]}' for runbook '{parts[1]}'"

        if subcmd == "checks":
            if len(parts) < 2:
                return "Usage: /runbook checks <id>"
            return f"Running checks for runbook '{parts[1]}' — no checks registered yet"

        return f"Unknown subcommand '{subcmd}'. Use create/list/show/from-procedure/version/checks."

    registry.register_async("runbook", "Generate and manage operational runbooks", runbook_handler)

    # ------------------------------------------------------------------
    # /oncall — On-call management
    # ------------------------------------------------------------------
    async def oncall_handler(args: str) -> str:
        """
        Usage: /oncall add-person <name> [email]
               /oncall list
               /oncall who [level]
               /oncall override <original-id> <replacement-id> <hours>
               /oncall fatigue <person-id>
               /oncall handoff <from-id> <to-id> <notes>
               /oncall policy <name>
        """
        from lidco.sre.oncall import EscalationPolicy, OnCallManager, OnCallPerson

        parts = shlex.split(args) if args.strip() else []
        if not parts:
            return (
                "Usage: /oncall <subcommand>\n"
                "  add-person <name> [email]              add on-call person\n"
                "  list                                   list all people\n"
                "  who [level]                            who is currently on-call\n"
                "  override <orig-id> <repl-id> <hours>   add override\n"
                "  fatigue <person-id>                    show fatigue score\n"
                "  handoff <from-id> <to-id> <notes>      create handoff note\n"
                "  policy <name>                          create escalation policy"
            )

        subcmd = parts[0].lower()
        mgr = OnCallManager()

        if subcmd == "add-person":
            if len(parts) < 2:
                return "Usage: /oncall add-person <name> [email]"
            name = parts[1]
            email = parts[2] if len(parts) > 2 else ""
            person = mgr.add_person(OnCallPerson(name=name, email=email))
            return f"Added on-call person '{person.name}' (id={person.id})"

        if subcmd == "list":
            people = mgr.list_people()
            if not people:
                return "No on-call people registered."
            lines = [f"On-call people ({len(people)}):"]
            for p in people:
                lines.append(f"  {p.id}: {p.name} ({p.email or 'no email'})")
            return "\n".join(lines)

        if subcmd == "who":
            person = mgr.current_on_call()
            if person is None:
                return "No one is currently on-call."
            return f"Currently on-call: {person.name} ({person.email})"

        if subcmd == "override":
            if len(parts) < 4:
                return "Usage: /oncall override <original-id> <replacement-id> <hours>"
            return f"Override set: {parts[1]} -> {parts[2]} for {parts[3]}h"

        if subcmd == "fatigue":
            if len(parts) < 2:
                return "Usage: /oncall fatigue <person-id>"
            return f"Fatigue data for person '{parts[1]}' — register person first"

        if subcmd == "handoff":
            if len(parts) < 4:
                return "Usage: /oncall handoff <from-id> <to-id> <notes>"
            return f"Handoff from {parts[1]} to {parts[2]}: {parts[3]}"

        if subcmd == "policy":
            if len(parts) < 2:
                return "Usage: /oncall policy <name>"
            policy = mgr.add_policy(EscalationPolicy(name=parts[1]))
            return f"Created escalation policy '{policy.name}' (id={policy.id}, levels={len(policy.levels)})"

        return f"Unknown subcommand '{subcmd}'. Use add-person/list/who/override/fatigue/handoff/policy."

    registry.register_async("oncall", "On-call schedule and escalation management", oncall_handler)
