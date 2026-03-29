"""Q118 CLI commands: /automation."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q118 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def automation_handler(args: str) -> str:
        from lidco.scheduler.trigger_registry import (
            AutomationTriggerRegistry,
            AutomationTrigger,
            TriggerAlreadyExistsError,
        )
        from lidco.scheduler.automation_runner import AutomationRunner

        # Lazy-init registry and runner
        if "registry" not in _state:
            _state["registry"] = AutomationTriggerRegistry()
        if "runner" not in _state:
            agent_fn = _state.get("agent_fn")
            _state["runner"] = AutomationRunner(
                _state["registry"],  # type: ignore[arg-type]
                agent_fn=agent_fn,  # type: ignore[arg-type]
            )

        reg: AutomationTriggerRegistry = _state["registry"]  # type: ignore[assignment]
        runner: AutomationRunner = _state["runner"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=3)
        sub = parts[0].lower() if parts else ""

        if sub == "list":
            triggers = reg.list_all()
            if not triggers:
                return "No automation triggers registered."
            lines = ["Automation triggers:"]
            for t in triggers:
                status = "enabled" if t.enabled else "disabled"
                lines.append(f"  {t.name} [{t.trigger_type}] ({status})")
            return "\n".join(lines)

        if sub == "add":
            if len(parts) < 4:
                return "Usage: /automation add <type> <name> <template>"
            ttype = parts[1]
            tname = parts[2]
            template = parts[3]
            trigger = AutomationTrigger(
                name=tname,
                trigger_type=ttype,
                config={},
                instructions_template=template,
                output_type="log",
            )
            try:
                reg.register(trigger)
            except TriggerAlreadyExistsError:
                return f"Trigger '{tname}' already exists."
            return f"Registered trigger '{tname}' [{ttype}]."

        if sub == "run":
            if len(parts) < 2:
                return "Usage: /automation run <name> [json_payload]"
            tname = parts[1]
            trigger = reg.get(tname)
            if trigger is None:
                return f"Trigger '{tname}' not found."
            payload = {}
            if len(parts) > 2:
                raw = parts[2]
                if len(parts) > 3:
                    raw = raw + " " + parts[3]
                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return "Invalid JSON payload."
            summary = runner.run(trigger.trigger_type, payload)
            lines = [f"Ran {summary.triggered} trigger(s): {summary.succeeded} ok, {summary.failed} failed."]
            for rec in summary.records:
                status = "ok" if rec.success else f"FAIL: {rec.error}"
                lines.append(f"  [{rec.trigger_name}] {status}")
            return "\n".join(lines)

        if sub == "history":
            records = runner.get_history(limit=5)
            if not records:
                return "No automation history."
            lines = ["Recent automation runs:"]
            for rec in records:
                status = "ok" if rec.success else f"FAIL: {rec.error}"
                lines.append(f"  [{rec.trigger_name}] {status} @ {rec.timestamp}")
            return "\n".join(lines)

        if sub == "enable":
            if len(parts) < 2:
                return "Usage: /automation enable <name>"
            tname = parts[1]
            if reg.get(tname) is None:
                return f"Trigger '{tname}' not found."
            reg.enable(tname)
            return f"Enabled trigger '{tname}'."

        if sub == "disable":
            if len(parts) < 2:
                return "Usage: /automation disable <name>"
            tname = parts[1]
            if reg.get(tname) is None:
                return f"Trigger '{tname}' not found."
            reg.disable(tname)
            return f"Disabled trigger '{tname}'."

        return (
            "Usage: /automation <sub>\n"
            "  list                          -- list triggers\n"
            "  add <type> <name> <template>  -- register trigger\n"
            "  run <name> [json_payload]     -- run trigger\n"
            "  history                       -- show recent runs\n"
            "  enable <name>                 -- enable trigger\n"
            "  disable <name>                -- disable trigger"
        )

    registry.register(SlashCommand("automation", "Automations platform v2", automation_handler))
