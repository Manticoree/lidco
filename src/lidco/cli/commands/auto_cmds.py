"""Slash commands for the Automation Engine (/auto)."""
from __future__ import annotations

from typing import Any

_engine: Any = None


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        try:
            from lidco.scheduler.automation_engine import AutomationEngine
            _engine = AutomationEngine()
            _engine.load_rules()
        except Exception:
            _engine = None
    return _engine


# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------

async def auto_list_handler(args: str = "") -> str:
    """/auto list — show all automation rules."""
    engine = _get_engine()
    if engine is None:
        return "Automation engine unavailable."
    rules = engine.rules
    if not rules:
        return "No automation rules loaded. Create .lidco/automations.yaml."
    lines = [f"Automation rules ({len(rules)}):"]
    for r in rules:
        status = "enabled" if r.enabled else "disabled"
        lines.append(f"  [{status}] {r.name} ({r.trigger_type}) → {r.output_type}")
    return "\n".join(lines)


async def auto_run_handler(args: str = "") -> str:
    """/auto run <name> — trigger a specific rule immediately."""
    name = args.strip()
    if not name:
        return "Usage: /auto run <rule_name>"
    engine = _get_engine()
    if engine is None:
        return "Automation engine unavailable."
    rule = next((r for r in engine.rules if r.name == name), None)
    if rule is None:
        return f"Rule '{name}' not found."
    result = engine.run_rule(rule, {"type": rule.trigger_type})
    status = "✓" if result.success else f"✗ {result.error}"
    return f"Rule '{name}': {status}\nOutput: {result.output[:200]}"


async def auto_tick_handler(args: str = "") -> str:
    """/auto tick — trigger a scheduler tick (runs all due cron rules)."""
    engine = _get_engine()
    if engine is None:
        return "Automation engine unavailable."
    try:
        results = engine.tick()
        if not results:
            return "Tick complete. No cron rules ran."
        lines = [f"Tick ran {len(results)} rule(s):"]
        for r in results:
            status = "✓" if r.success else f"✗ {r.error}"
            lines.append(f"  {r.rule_name}: {status}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Tick failed: {exc}"


async def auto_enable_handler(args: str = "") -> str:
    """/auto enable <name> — enable a rule."""
    name = args.strip()
    if not name:
        return "Usage: /auto enable <rule_name>"
    engine = _get_engine()
    if engine is None:
        return "Automation engine unavailable."
    rule = next((r for r in engine.rules if r.name == name), None)
    if rule is None:
        return f"Rule '{name}' not found."
    rule.enabled = True
    return f"Rule '{name}' enabled."


async def auto_disable_handler(args: str = "") -> str:
    """/auto disable <name> — disable a rule."""
    name = args.strip()
    if not name:
        return "Usage: /auto disable <rule_name>"
    engine = _get_engine()
    if engine is None:
        return "Automation engine unavailable."
    rule = next((r for r in engine.rules if r.name == name), None)
    if rule is None:
        return f"Rule '{name}' not found."
    rule.enabled = False
    return f"Rule '{name}' disabled."


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_auto_commands(registry: Any) -> None:
    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("auto list", "List all automation rules", auto_list_handler))
    registry.register(SlashCommand("auto run", "Trigger a specific automation rule", auto_run_handler))
    registry.register(SlashCommand("auto tick", "Trigger scheduler tick", auto_tick_handler))
    registry.register(SlashCommand("auto enable", "Enable an automation rule", auto_enable_handler))
    registry.register(SlashCommand("auto disable", "Disable an automation rule", auto_disable_handler))
