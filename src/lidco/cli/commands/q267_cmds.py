"""Q267 CLI commands: /incident-detect, /incident-respond, /forensics, /incident-recover."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:  # noqa: D401
    """Register Q267 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /incident-detect
    # ------------------------------------------------------------------

    async def incident_detect_handler(args: str) -> str:
        from lidco.incident.detector import IncidentDetector

        if "detector" not in _state:
            _state["detector"] = IncidentDetector()

        det: IncidentDetector = _state["detector"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "analyze":
            if not rest:
                return "Usage: /incident-detect analyze <json_events>"
            try:
                events = json.loads(rest)
            except json.JSONDecodeError:
                return "Invalid JSON."
            incidents = det.analyze_events(events)
            if not incidents:
                return "No incidents detected."
            lines = [f"{len(incidents)} incident(s) detected:"]
            for inc in incidents:
                lines.append(f"  [{inc.severity}] {inc.type}: {inc.description}")
            return "\n".join(lines)

        if sub == "list":
            incs = det.incidents()
            if not incs:
                return "No incidents."
            lines = [f"{len(incs)} incident(s):"]
            for inc in incs:
                lines.append(f"  {inc.id} [{inc.severity}] {inc.type}")
            return "\n".join(lines)

        if sub == "severity":
            if not rest:
                return "Usage: /incident-detect severity <level>"
            incs = det.by_severity(rest)
            if not incs:
                return f"No incidents with severity '{rest}'."
            lines = [f"{len(incs)} incident(s):"]
            for inc in incs:
                lines.append(f"  {inc.id} {inc.type}: {inc.description}")
            return "\n".join(lines)

        return (
            "Usage: /incident-detect <subcommand>\n"
            "  analyze <json>   — analyze events for incidents\n"
            "  list             — list all incidents\n"
            "  severity <level> — filter by severity"
        )

    # ------------------------------------------------------------------
    # /incident-respond
    # ------------------------------------------------------------------

    async def incident_respond_handler(args: str) -> str:
        from lidco.incident.detector import IncidentDetector
        from lidco.incident.playbook import PlaybookStep, ResponsePlaybook

        if "playbook" not in _state:
            pb = ResponsePlaybook()
            # Register default playbooks
            pb.register("brute_force", [
                PlaybookStep("block_ip", "block", "firewall"),
                PlaybookStep("notify_admin", "notify", "admin"),
                PlaybookStep("log_event", "log", "siem"),
            ])
            pb.register("data_exfiltration", [
                PlaybookStep("isolate_host", "isolate", "network"),
                PlaybookStep("preserve_logs", "preserve", "evidence"),
                PlaybookStep("notify_security", "notify", "security_team"),
            ])
            _state["playbook"] = pb

        pb_obj: ResponsePlaybook = _state["playbook"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "execute":
            if not rest:
                return "Usage: /incident-respond execute <incident_id>"
            det: IncidentDetector | None = _state.get("detector")  # type: ignore[assignment]
            if det is None:
                return "No detector active. Run /incident-detect analyze first."
            incident = None
            for inc in det.incidents():
                if inc.id == rest:
                    incident = inc
                    break
            if incident is None:
                return f"Incident '{rest}' not found."
            result = pb_obj.execute(incident)
            return (
                f"Executed playbook for {result.incident_id}: "
                f"{result.steps_executed} steps, {result.steps_failed} failed. "
                f"Actions: {', '.join(result.actions_taken)}"
            )

        if sub == "playbooks":
            types = pb_obj.playbook_types()
            if not types:
                return "No playbooks registered."
            return "Playbooks: " + ", ".join(types)

        if sub == "history":
            hist = pb_obj.history()
            if not hist:
                return "No execution history."
            lines = [f"{len(hist)} execution(s):"]
            for r in hist:
                lines.append(f"  {r.incident_id}: {r.steps_executed} steps")
            return "\n".join(lines)

        return (
            "Usage: /incident-respond <subcommand>\n"
            "  execute <id>  — execute playbook for incident\n"
            "  playbooks     — list registered playbooks\n"
            "  history       — show execution history"
        )

    # ------------------------------------------------------------------
    # /forensics
    # ------------------------------------------------------------------

    async def forensics_handler(args: str) -> str:
        from lidco.incident.forensics import ForensicsCollector

        if "forensics" not in _state:
            _state["forensics"] = ForensicsCollector()

        fc: ForensicsCollector = _state["forensics"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "collect":
            tokens = rest.split(maxsplit=2)
            if len(tokens) < 3:
                return "Usage: /forensics collect <incident_id> <type> <content>"
            ev = fc.collect(tokens[0], tokens[1], tokens[2])
            return f"Collected evidence {ev.id} for incident {ev.incident_id}"

        if sub == "timeline":
            if not rest:
                return "Usage: /forensics timeline <incident_id>"
            tl = fc.timeline(rest)
            if not tl:
                return f"No evidence for incident '{rest}'."
            lines = [f"{len(tl)} evidence item(s):"]
            for e in tl:
                lines.append(f"  [{e.type}] {e.content[:60]}")
            return "\n".join(lines)

        if sub == "export":
            if not rest:
                return "Usage: /forensics export <incident_id>"
            return fc.export(rest)

        return (
            "Usage: /forensics <subcommand>\n"
            "  collect <id> <type> <content> — collect evidence\n"
            "  timeline <id>                 — show evidence timeline\n"
            "  export <id>                   — export evidence as JSON"
        )

    # ------------------------------------------------------------------
    # /incident-recover
    # ------------------------------------------------------------------

    async def incident_recover_handler(args: str) -> str:
        from lidco.incident.recovery import RecoveryManager

        if "recovery" not in _state:
            _state["recovery"] = RecoveryManager()

        rm: RecoveryManager = _state["recovery"]  # type: ignore[assignment]
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "plan":
            if not rest:
                return "Usage: /incident-recover plan <incident_id>"
            plan = rm.create_plan(rest)
            return f"Created recovery plan for {plan.incident_id} (status={plan.status})"

        if sub == "action":
            tokens = rest.split(maxsplit=2)
            if len(tokens) < 3:
                return "Usage: /incident-recover action <incident_id> <action> <target>"
            ra = rm.add_action(tokens[0], tokens[1], tokens[2])
            return f"Added action {ra.id}: {ra.action} on {ra.target}"

        if sub == "execute":
            if not rest:
                return "Usage: /incident-recover execute <incident_id>"
            plan = rm.execute_plan(rest)
            return f"Executed plan for {plan.incident_id}: {len(plan.actions)} actions, status={plan.status}"

        if sub == "report":
            if not rest:
                return "Usage: /incident-recover report <incident_id>"
            return rm.generate_report(rest)

        return (
            "Usage: /incident-recover <subcommand>\n"
            "  plan <id>                     — create recovery plan\n"
            "  action <id> <action> <target> — add recovery action\n"
            "  execute <id>                  — execute recovery plan\n"
            "  report <id>                   — generate post-incident report"
        )

    # ------------------------------------------------------------------
    # Register all commands
    # ------------------------------------------------------------------

    registry.register(SlashCommand("incident-detect", "Detect security incidents", incident_detect_handler))
    registry.register(SlashCommand("incident-respond", "Execute incident response playbooks", incident_respond_handler))
    registry.register(SlashCommand("forensics", "Forensics evidence collection", forensics_handler))
    registry.register(SlashCommand("incident-recover", "Incident recovery management", incident_recover_handler))
