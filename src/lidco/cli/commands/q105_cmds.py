"""Q105 CLI commands: /value-object /entity /domain-events /money."""
from __future__ import annotations

_state: dict[str, object] = {}


def _get_publisher():
    from lidco.domain.events import DomainEventPublisher
    if "publisher" not in _state:
        _state["publisher"] = DomainEventPublisher()
    return _state["publisher"]


def register(registry) -> None:
    """Register Q105 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def value_object_handler(args: str) -> str:
        """Usage: /value-object <demo | money amount [currency] | email addr | phone number>"""
        from lidco.domain.value_object import Money, EmailAddress, PhoneNumber, ValueObject
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /value-object <demo | money amount [currency] | email addr | phone number>"
        cmd = parts[0].lower()
        if cmd == "demo":
            m1 = Money(10.00, "USD")
            m2 = Money(5.50, "USD")
            total = m1.add(m2)
            return (
                f"Money: {m1} + {m2} = {total}\n"
                f"Equal: {m1 == Money(10.00, 'USD')}\n"
                f"Hash: {hash(m1) == hash(Money(10.00, 'USD'))}"
            )
        elif cmd == "money":
            if len(parts) < 2:
                return "Usage: /value-object money <amount> [currency]"
            try:
                amount = float(parts[1])
                currency = parts[2] if len(parts) > 2 else "USD"
                m = Money(amount, currency)
                return f"{m}  positive={m.is_positive()}  zero={m.is_zero()}"
            except ValueError as e:
                return f"Error: {e}"
        elif cmd == "email":
            if len(parts) < 2:
                return "Usage: /value-object email <address>"
            try:
                e = EmailAddress(parts[1])
                return f"{e}  domain={e.domain}  local={e.local_part}"
            except ValueError as e:
                return f"Invalid: {e}"
        elif cmd == "phone":
            if len(parts) < 2:
                return "Usage: /value-object phone <number>"
            try:
                p = PhoneNumber(parts[1])
                return f"{p}  digits={p.value}"
            except ValueError as e:
                return f"Invalid: {e}"
        return f"Unknown subcommand: {cmd}"

    async def entity_handler(args: str) -> str:
        """Usage: /entity <create [id] | touch id | delete id | restore id | list | info id>"""
        from lidco.domain.entity import Entity, TimestampedEntity
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: /entity <create [id] | touch id | delete id | restore id | list | info id>"
        if "entities" not in _state:
            _state["entities"] = {}
        entities = _state["entities"]
        cmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if cmd == "create":
            eid = rest or None
            e = TimestampedEntity(eid)
            entities[e.id] = e
            return f"Created entity: {e.id}  v{e.version}"
        elif cmd == "touch":
            if not rest:
                return "Usage: /entity touch <id>"
            e = entities.get(rest)
            if e is None:
                return f"Not found: {rest!r}"
            e.touch()
            return f"Touched {rest}: v{e.version}"
        elif cmd == "delete":
            if not rest:
                return "Usage: /entity delete <id>"
            e = entities.get(rest)
            if e is None:
                return f"Not found: {rest!r}"
            e.soft_delete()
            return f"Soft-deleted: {rest}  deleted={e.is_deleted}"
        elif cmd == "restore":
            if not rest:
                return "Usage: /entity restore <id>"
            e = entities.get(rest)
            if e is None:
                return f"Not found: {rest!r}"
            e.restore()
            return f"Restored: {rest}  deleted={e.is_deleted}"
        elif cmd == "list":
            if not entities:
                return "(empty)"
            lines = [f"  {e.id}  v{e.version}  deleted={e.is_deleted}" for e in entities.values()]
            return "\n".join(lines)
        elif cmd == "info":
            if not rest:
                return "Usage: /entity info <id>"
            e = entities.get(rest)
            if e is None:
                return f"Not found: {rest!r}"
            return str(e.to_dict())
        return f"Unknown subcommand: {cmd}"

    async def domain_events_handler(args: str) -> str:
        """Usage: /domain-events <publish type [payload] | subscribe type | history [type] | clear | count type>"""
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /domain-events <publish type | subscribe type | history [type] | clear | count type>"
        publisher = _get_publisher()
        cmd = parts[0].lower()
        if cmd == "publish":
            if len(parts) < 2:
                return "Usage: /domain-events publish <event_type> [payload_json]"
            import json
            event_type = parts[1]
            payload = {}
            if len(parts) > 2:
                try:
                    payload = json.loads(parts[2])
                except json.JSONDecodeError:
                    payload = {"data": parts[2]}
            msg = publisher.publish(event_type, payload)
            return f"Published {event_type!r} [{msg.event_id[:8]}]"
        elif cmd == "subscribe":
            if len(parts) < 2:
                return "Usage: /domain-events subscribe <event_type>"
            event_type = parts[1]
            if "log" not in _state:
                _state["log"] = []
            log = _state["log"]
            hid = publisher.subscribe(event_type, lambda e: log.append(e.event_type))
            return f"Subscribed to {event_type!r} (handler_id={hid[:8]})"
        elif cmd == "history":
            event_type = parts[1] if len(parts) > 1 else None
            events = publisher.history(event_type=event_type, limit=20)
            if not events:
                return "(no events)"
            lines = [f"  [{e.event_type}] {e.event_id[:8]}" for e in events]
            return "\n".join(lines)
        elif cmd == "clear":
            n = publisher.clear_history()
            return f"Cleared {n} events."
        elif cmd == "count":
            event_type = parts[1] if len(parts) > 1 else None
            events = publisher.history(event_type=event_type)
            return f"Event count: {len(events)}"
        elif cmd == "types":
            types = publisher.subscribed_types()
            return "\n".join(types) if types else "(none)"
        return f"Unknown subcommand: {cmd}"

    async def money_handler(args: str) -> str:
        """Usage: /money <add a1 c1 a2 c2 | subtract a1 c1 a2 c2 | multiply amount currency factor | compare a1 c1 a2 c2>"""
        from lidco.domain.value_object import Money
        parts = args.strip().split()
        if not parts:
            return "Usage: /money <add | subtract | multiply>"
        cmd = parts[0].lower()
        if cmd == "add":
            if len(parts) < 5:
                return "Usage: /money add <amount1> <currency1> <amount2> <currency2>"
            try:
                m1 = Money(float(parts[1]), parts[2])
                m2 = Money(float(parts[3]), parts[4])
                result = m1.add(m2)
                return f"{m1} + {m2} = {result}"
            except (ValueError, IndexError) as e:
                return f"Error: {e}"
        elif cmd == "subtract":
            if len(parts) < 5:
                return "Usage: /money subtract <amount1> <currency1> <amount2> <currency2>"
            try:
                m1 = Money(float(parts[1]), parts[2])
                m2 = Money(float(parts[3]), parts[4])
                result = m1.subtract(m2)
                return f"{m1} - {m2} = {result}"
            except (ValueError, IndexError) as e:
                return f"Error: {e}"
        elif cmd == "multiply":
            if len(parts) < 4:
                return "Usage: /money multiply <amount> <currency> <factor>"
            try:
                m = Money(float(parts[1]), parts[2])
                result = m.multiply(float(parts[3]))
                return f"{m} × {parts[3]} = {result}"
            except (ValueError, IndexError) as e:
                return f"Error: {e}"
        return f"Unknown subcommand: {cmd}"

    registry.register(SlashCommand("value-object", "Value object creation and comparison", value_object_handler))
    registry.register(SlashCommand("entity", "Domain entity management", entity_handler))
    registry.register(SlashCommand("domain-events", "Domain event publishing and subscription", domain_events_handler))
    registry.register(SlashCommand("money", "Money value object arithmetic", money_handler))
