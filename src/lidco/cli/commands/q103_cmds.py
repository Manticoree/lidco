"""Q103 CLI commands: /event-store /cqrs /saga /aggregate."""
from __future__ import annotations

_state: dict[str, object] = {}


def _get_store():
    from lidco.eventsourcing.store import EventStore
    if "event_store" not in _state:
        _state["event_store"] = EventStore(path=None)
    return _state["event_store"]


def _get_cmd_bus():
    from lidco.cqrs.bus import CommandBus
    if "cmd_bus" not in _state:
        _state["cmd_bus"] = CommandBus()
    return _state["cmd_bus"]


def _get_query_bus():
    from lidco.cqrs.bus import QueryBus
    if "query_bus" not in _state:
        _state["query_bus"] = QueryBus()
    return _state["query_bus"]


def _get_saga():
    from lidco.saga.coordinator import SagaCoordinator
    if "saga" not in _state:
        _state["saga"] = SagaCoordinator()
    return _state["saga"]


def register(registry) -> None:
    """Register Q103 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def event_store_handler(args: str) -> str:
        """Usage: /event-store <append agg_id type payload | load agg_id | list | clear | count | snapshot agg_id>"""
        parts = args.strip().split(maxsplit=3)
        if not parts:
            return "Usage: /event-store <append agg_id type payload | load agg_id | list | clear | count>"
        store = _get_store()
        cmd = parts[0].lower()
        if cmd == "append":
            if len(parts) < 3:
                return "Usage: /event-store append <agg_id> <event_type> [payload_json]"
            from lidco.eventsourcing.store import DomainEvent
            import json
            agg_id = parts[1]
            event_type = parts[2]
            payload = {}
            if len(parts) > 3:
                try:
                    payload = json.loads(parts[3])
                except json.JSONDecodeError:
                    payload = {"raw": parts[3]}
            version = store.current_version(agg_id) + 1
            event = DomainEvent.create(
                aggregate_id=agg_id,
                aggregate_type="Generic",
                event_type=event_type,
                version=version,
                payload=payload,
            )
            store.append(event)
            return f"Appended {event_type!r} v{version} for {agg_id!r} [{event.event_id[:8]}]"
        elif cmd == "load":
            if len(parts) < 2:
                return "Usage: /event-store load <agg_id>"
            events = store.load(parts[1])
            if not events:
                return f"No events for {parts[1]!r}"
            lines = [f"  v{e.version} [{e.event_type}] {e.event_id[:8]}" for e in events]
            return "\n".join(lines)
        elif cmd == "list":
            events = store.get_all()
            if not events:
                return "(no events)"
            lines = [f"  {e.aggregate_id!r} v{e.version} [{e.event_type}]" for e in events]
            return "\n".join(lines)
        elif cmd == "count":
            return f"Total events: {store.count()}"
        elif cmd == "clear":
            store.clear()
            return "Event store cleared."
        elif cmd == "version":
            if len(parts) < 2:
                return "Usage: /event-store version <agg_id>"
            v = store.current_version(parts[1])
            return f"Current version of {parts[1]!r}: {v}"
        return f"Unknown subcommand: {cmd}"

    async def cqrs_handler(args: str) -> str:
        """Usage: /cqrs <register-cmd name | dispatch-cmd name payload | list-cmds | list-queries>"""
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /cqrs <register-cmd name | dispatch-cmd name | list-cmds>"
        cmd_bus = _get_cmd_bus()
        query_bus = _get_query_bus()
        cmd = parts[0].lower()
        if cmd == "register-cmd":
            if len(parts) < 2:
                return "Usage: /cqrs register-cmd <name>"
            name = parts[1]
            cmd_bus.register(lambda c: f"handled:{name}", name=name)
            return f"Command handler registered: {name!r}"
        elif cmd == "dispatch-cmd":
            if len(parts) < 2:
                return "Usage: /cqrs dispatch-cmd <name>"
            name = parts[1]
            _Cmd = type(name, (), {})
            try:
                result = cmd_bus.dispatch(_Cmd(), name=name)
                return f"Result: success={result.success} data={result.data!r}"
            except Exception as e:
                return f"Error: {e}"
        elif cmd == "list-cmds":
            names = cmd_bus.registered_commands()
            return "\n".join(names) if names else "(none)"
        elif cmd == "list-queries":
            names = query_bus.registered_queries()
            return "\n".join(names) if names else "(none)"
        elif cmd == "register-query":
            if len(parts) < 2:
                return "Usage: /cqrs register-query <name>"
            name = parts[1]
            query_bus.register(lambda q: f"result:{name}", name=name)
            return f"Query handler registered: {name!r}"
        return f"Unknown subcommand: {cmd}"

    async def saga_handler(args: str) -> str:
        """Usage: /saga <add-step name | execute | steps | clear>"""
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: /saga <add-step name | execute | steps | clear>"
        coord = _get_saga()
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        if cmd == "add-step":
            if not rest:
                return "Usage: /saga add-step <name>"
            name = rest.strip()
            coord.add_step(
                name=name,
                action=lambda ctx: ctx.update({name: "done"}) or name,
                compensation=lambda ctx: ctx.pop(name, None),
                description=f"Demo step: {name}",
            )
            return f"Added saga step: {name!r}"
        elif cmd == "execute":
            result = coord.execute()
            lines = [
                f"saga_id={result.saga_id[:8]}",
                f"status={result.status.value}",
                f"completed={result.steps_completed}",
            ]
            if result.error:
                lines.append(f"error={result.error}")
            return "\n".join(lines)
        elif cmd == "steps":
            names = coord.step_names()
            return "\n".join(names) if names else "(no steps)"
        elif cmd == "clear":
            coord.clear()
            return "Saga cleared."
        return f"Unknown subcommand: {cmd}"

    async def aggregate_handler(args: str) -> str:
        """Usage: /aggregate <create type id | apply id event_type | history id | version id>"""
        from lidco.eventsourcing.aggregate import AggregateRoot
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /aggregate <create id | apply id event_type | history id | version id>"
        if "aggregates" not in _state:
            _state["aggregates"] = {}
        aggregates = _state["aggregates"]
        cmd = parts[0].lower()
        if cmd == "create":
            if len(parts) < 2:
                return "Usage: /aggregate create <id>"
            agg_id = parts[1]
            agg = AggregateRoot(aggregate_id=agg_id)
            aggregates[agg_id] = agg
            return f"Created aggregate {agg_id!r}"
        elif cmd == "apply":
            if len(parts) < 3:
                return "Usage: /aggregate apply <id> <event_type>"
            agg_id, event_type = parts[1], parts[2]
            agg = aggregates.get(agg_id)
            if agg is None:
                return f"Aggregate {agg_id!r} not found."
            event = agg._create_event(event_type)
            agg._apply_event(event)
            return f"Applied {event_type!r} (pending: {len(agg.pending_events)})"
        elif cmd == "history":
            if len(parts) < 2:
                return "Usage: /aggregate history <id>"
            agg_id = parts[1]
            agg = aggregates.get(agg_id)
            if agg is None:
                return f"Aggregate {agg_id!r} not found."
            events = agg.pending_events
            if not events:
                return "(no pending events)"
            lines = [f"  v{e.version} [{e.event_type}]" for e in events]
            return "\n".join(lines)
        elif cmd == "version":
            if len(parts) < 2:
                return "Usage: /aggregate version <id>"
            agg_id = parts[1]
            agg = aggregates.get(agg_id)
            if agg is None:
                return f"Aggregate {agg_id!r} not found."
            return f"Version: {agg.version}"
        return f"Unknown subcommand: {cmd}"

    registry.register(SlashCommand("event-store", "Event store management", event_store_handler))
    registry.register(SlashCommand("cqrs", "CQRS command/query bus", cqrs_handler))
    registry.register(SlashCommand("saga", "Saga orchestration", saga_handler))
    registry.register(SlashCommand("aggregate", "Aggregate root management", aggregate_handler))
