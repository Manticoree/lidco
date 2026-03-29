"""Q117 CLI commands: /hook (Task 721)."""
from __future__ import annotations

import json

from lidco.hooks.event_bus import HookEvent, HookEventBus
from lidco.hooks.conditional_filter import HookRegistry

_state: dict[str, object] = {
    "bus": HookEventBus(),
    "registry": HookRegistry(),
}


def _get_bus() -> HookEventBus:
    return _state["bus"]  # type: ignore[return-value]


def _get_registry() -> HookRegistry:
    return _state["registry"]  # type: ignore[return-value]


def register(registry) -> None:
    """Register Q117 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def hook_handler(args: str) -> str:
        parts = args.strip().split(maxsplit=2)
        sub = parts[0].lower() if parts else ""

        if sub == "list":
            bus = _get_bus()
            registry_ = _get_registry()
            defns = registry_.list_definitions()
            if not defns:
                return "No hooks registered."
            lines = [f"Registered hooks ({len(defns)}):"]
            for d in defns:
                count = bus.subscriber_count(d.event_type)
                pat = f" [pattern={d.if_pattern}]" if d.if_pattern else ""
                lines.append(f"  {d.name} -> {d.event_type} ({count} subscriber(s)){pat}")
            return "\n".join(lines)

        if sub == "emit":
            if len(parts) < 2:
                return "Usage: /hook emit <type> [json_payload]"
            event_type = parts[1]
            payload_str = parts[2] if len(parts) > 2 else "{}"
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                return f"Invalid JSON payload: {payload_str}"
            if not isinstance(payload, dict):
                return "Payload must be a JSON object."
            event = HookEvent(event_type=event_type, payload=payload)
            bus = _get_bus()
            count = bus.emit(event)
            return f"Emitted '{event_type}' to {count} handler(s)."

        if sub == "add-http":
            if len(parts) < 3:
                return "Usage: /hook add-http <event_type> <url>"
            event_type = parts[1]
            url = parts[2]
            from lidco.hooks.http_delivery import HttpHookDelivery, HttpHookConfig
            from lidco.hooks.conditional_filter import HookDefinition

            config = HttpHookConfig(url=url)
            delivery = HttpHookDelivery(config)
            defn = HookDefinition(
                name=f"http-{event_type}-{url[:30]}",
                event_type=event_type,
                handler=delivery.as_hook_handler(),
            )
            registry_ = _get_registry()
            registry_.register(defn)
            return f"Registered HTTP hook for '{event_type}' -> {url}"

        if sub == "add-filter":
            if len(parts) < 3:
                return "Usage: /hook add-filter <event_type> <pattern>"
            event_type = parts[1]
            pattern = parts[2]
            from lidco.hooks.conditional_filter import HookDefinition, ConditionalFilter

            log_entries: list[str] = []
            _state.setdefault("filter_logs", log_entries)

            def _log_handler(event: HookEvent) -> None:
                log_entries.append(f"[{event.event_type}] {event.payload}")

            defn = HookDefinition(
                name=f"filter-{event_type}-{pattern[:20]}",
                event_type=event_type,
                handler=_log_handler,
                if_pattern=pattern,
            )
            registry_ = _get_registry()
            registry_.register(defn)
            return f"Registered filter hook for '{event_type}' with pattern '{pattern}'."

        if sub == "clear":
            bus = _get_bus()
            bus.clear()
            new_bus = HookEventBus()
            new_registry = HookRegistry(bus=new_bus)
            _state["bus"] = new_bus
            _state["registry"] = new_registry
            return "All hooks cleared."

        return (
            "Usage: /hook <sub>\n"
            "  list                          -- list hooks and subscriber counts\n"
            "  emit <type> [json_payload]    -- emit a HookEvent\n"
            "  add-http <event_type> <url>   -- register HTTP webhook\n"
            "  add-filter <event_type> <pat> -- register conditional filter\n"
            "  clear                         -- clear all subscribers"
        )

    registry.register(SlashCommand("hook", "Hook system management", hook_handler))
