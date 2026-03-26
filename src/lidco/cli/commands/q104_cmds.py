"""Q104 CLI commands: /repo /uow /spec /domain-service."""
from __future__ import annotations

_state: dict[str, object] = {}


def _get_repo():
    from lidco.repository.base import Repository
    if "repo" not in _state:
        _state["repo"] = Repository(entity_type="Item")
    return _state["repo"]


def _get_uow():
    from lidco.repository.unit_of_work import UnitOfWork
    if "uow" not in _state:
        _state["uow"] = UnitOfWork()
    return _state["uow"]


def _get_service_registry():
    from lidco.domain.service import ServiceRegistry
    if "service_registry" not in _state:
        _state["service_registry"] = ServiceRegistry()
    return _state["service_registry"]


def register(registry) -> None:
    """Register Q104 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def repo_handler(args: str) -> str:
        """Usage: /repo <save id value | get id | delete id | list | count | clear>"""
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /repo <save id value | get id | delete id | list | count | clear>"
        repo = _get_repo()
        cmd = parts[0].lower()
        if cmd == "save":
            if len(parts) < 3:
                return "Usage: /repo save <id> <value>"

            class _Item:
                def __init__(self, iid, val):
                    self.id = iid
                    self.value = val
                def __repr__(self):
                    return f"Item(id={self.id!r}, value={self.value!r})"

            repo.save(_Item(parts[1], parts[2]))
            return f"Saved item {parts[1]!r}"
        elif cmd == "get":
            if len(parts) < 2:
                return "Usage: /repo get <id>"
            from lidco.repository.base import EntityNotFoundError
            try:
                entity = repo.get_by_id(parts[1])
                return repr(entity)
            except EntityNotFoundError:
                return f"Not found: {parts[1]!r}"
        elif cmd == "delete":
            if len(parts) < 2:
                return "Usage: /repo delete <id>"
            removed = repo.delete(parts[1])
            return f"Deleted: {removed}"
        elif cmd == "list":
            entities = repo.find_all()
            if not entities:
                return "(empty)"
            return "\n".join(repr(e) for e in entities)
        elif cmd == "count":
            return f"Count: {repo.count()}"
        elif cmd == "clear":
            repo.clear()
            return "Repository cleared."
        elif cmd == "exists":
            if len(parts) < 2:
                return "Usage: /repo exists <id>"
            return str(repo.exists(parts[1]))
        return f"Unknown subcommand: {cmd}"

    async def uow_handler(args: str) -> str:
        """Usage: /uow <begin | new id | dirty id | removed id | commit | rollback | status>"""
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: /uow <begin | new id | dirty id | removed id | commit | rollback | status>"
        uow = _get_uow()
        cmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if cmd == "begin":
            uow.begin()
            return "Transaction started."
        elif cmd == "new":
            if not rest:
                return "Usage: /uow new <id>"

            class _E:
                def __init__(self, eid):
                    self.id = eid

            uow.register_new(_E(rest))
            return f"Registered new: {rest!r}"
        elif cmd == "dirty":
            if not rest:
                return "Usage: /uow dirty <id>"

            class _E:
                def __init__(self, eid):
                    self.id = eid

            uow.register_dirty(_E(rest))
            return f"Registered dirty: {rest!r}"
        elif cmd == "removed":
            if not rest:
                return "Usage: /uow removed <id>"

            class _E:
                def __init__(self, eid):
                    self.id = eid

            uow.register_removed(_E(rest))
            return f"Registered removed: {rest!r}"
        elif cmd == "commit":
            summary = uow.commit()
            return (
                f"Committed:\n"
                f"  new={summary['new']}\n"
                f"  dirty={summary['dirty']}\n"
                f"  removed={summary['removed']}"
            )
        elif cmd == "rollback":
            uow.rollback()
            return "Transaction rolled back."
        elif cmd == "status":
            return (
                f"active={uow.is_active()}\n"
                f"pending_new={uow.pending_new()}\n"
                f"pending_dirty={uow.pending_dirty()}\n"
                f"pending_removed={uow.pending_removed()}\n"
                f"commits={uow.commit_count()}"
            )
        return f"Unknown subcommand: {cmd}"

    async def spec_handler(args: str) -> str:
        """Usage: /spec <eval predicate value | compose and|or|not>"""
        from lidco.domain.specification import spec
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /spec <eval gt:N value | eval lt:N value | compose and|or|not>"
        cmd = parts[0].lower()
        if cmd == "eval":
            if len(parts) < 3:
                return "Usage: /spec eval <gt:N|lt:N|eq:N|nonempty> <value>"
            rule, val_str = parts[1], parts[2]
            try:
                val = float(val_str)
            except ValueError:
                val = val_str
            if rule.startswith("gt:"):
                threshold = float(rule[3:])
                s = spec(lambda x, t=threshold: x > t, f">{threshold}")
            elif rule.startswith("lt:"):
                threshold = float(rule[3:])
                s = spec(lambda x, t=threshold: x < t, f"<{threshold}")
            elif rule.startswith("eq:"):
                expected = rule[3:]
                s = spec(lambda x, e=expected: str(x) == e, f"=={expected}")
            elif rule == "nonempty":
                s = spec(lambda x: bool(x), "nonempty")
            else:
                return f"Unknown rule: {rule}. Try gt:N, lt:N, eq:val, nonempty"
            result = s.is_satisfied_by(val)
            return f"{val!r} satisfies {rule!r}: {result}"
        elif cmd == "demo":
            items = [1, 5, 10, 15, 20]
            gt10 = spec(lambda x: x > 10, ">10")
            lt15 = spec(lambda x: x < 15, "<15")
            combined = gt10 & lt15
            filtered = combined.filter(items)
            return f"Items {items} where >10 AND <15: {filtered}"
        return f"Unknown subcommand: {cmd}"

    async def domain_service_handler(args: str) -> str:
        """Usage: /domain-service <register name | get name | list | unregister name | clear>"""
        from lidco.domain.service import DomainService, DomainServiceNotFoundError
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: /domain-service <register name | get name | list | unregister name | clear>"
        reg = _get_service_registry()
        cmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""
        if cmd == "register":
            if not rest:
                return "Usage: /domain-service register <name>"
            svc = DomainService()
            svc.service_name = rest
            reg.register(rest, svc)
            return f"Registered domain service: {rest!r}"
        elif cmd == "get":
            if not rest:
                return "Usage: /domain-service get <name>"
            try:
                svc = reg.get(rest)
                return f"Service {rest!r}: {type(svc).__name__} valid={svc.is_valid()}"
            except DomainServiceNotFoundError:
                return f"Not found: {rest!r}"
        elif cmd == "list":
            names = reg.list()
            return "\n".join(names) if names else "(none)"
        elif cmd == "unregister":
            if not rest:
                return "Usage: /domain-service unregister <name>"
            removed = reg.unregister(rest)
            return f"Unregistered: {removed}"
        elif cmd == "clear":
            reg.clear()
            return "Domain service registry cleared."
        return f"Unknown subcommand: {cmd}"

    registry.register(SlashCommand("repo", "Generic repository management", repo_handler))
    registry.register(SlashCommand("uow", "Unit of Work transaction management", uow_handler))
    registry.register(SlashCommand("spec", "Specification pattern evaluation", spec_handler))
    registry.register(SlashCommand("domain-service", "Domain service registry", domain_service_handler))
