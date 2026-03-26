"""Q101 CLI commands: /cache /pool /observer /command."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_state: dict[str, object] = {}


def _get_cache():
    from lidco.core.cache import LRUCache
    if "cache" not in _state:
        _state["cache"] = LRUCache(maxsize=256)
    return _state["cache"]


def _get_pool():
    from lidco.core.object_pool import ObjectPool
    if "pool" not in _state:
        _state["pool"] = ObjectPool(factory=dict, max_size=5)
    return _state["pool"]


def _get_observer():
    from lidco.patterns.observer import ObservableValue
    if "observer" not in _state:
        _state["observer"] = ObservableValue(None)
    return _state["observer"]


def _get_history():
    from lidco.patterns.command import CommandHistory
    if "history" not in _state:
        _state["history"] = CommandHistory(max_history=50)
    return _state["history"]


def register(registry) -> None:
    """Register Q101 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def cache_handler(args: str) -> str:
        """Usage: /cache <set key value | get key | delete key | stats | clear>"""
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /cache <set key value | get key | delete key | stats | clear>"
        cache = _get_cache()
        cmd = parts[0].lower()
        if cmd == "set":
            if len(parts) < 3:
                return "Usage: /cache set <key> <value>"
            cache.set(parts[1], parts[2])
            return f"Cached: {parts[1]} = {parts[2]!r}"
        elif cmd == "get":
            if len(parts) < 2:
                return "Usage: /cache get <key>"
            val = cache.get(parts[1])
            return f"{parts[1]} = {val!r}"
        elif cmd == "delete":
            if len(parts) < 2:
                return "Usage: /cache delete <key>"
            removed = cache.delete(parts[1])
            return f"Deleted: {removed}"
        elif cmd == "stats":
            s = cache.stats()
            total = s.hits + s.misses
            hit_rate = s.hits / total if total else 0.0
            return (
                f"size={s.size}  hits={s.hits}  misses={s.misses}  "
                f"hit_rate={hit_rate:.1%}  evictions={s.evictions}"
            )
        elif cmd == "clear":
            cache.clear()
            return "Cache cleared."
        elif cmd == "keys":
            keys = cache.keys()
            return "\n".join(keys) if keys else "(empty)"
        return f"Unknown subcommand: {cmd}"

    async def pool_handler(args: str) -> str:
        """Usage: /pool <stats | drain | info>"""
        cmd = args.strip().lower() or "stats"
        pool = _get_pool()
        if cmd == "stats":
            s = pool.stats()
            return (
                f"pool_size={s.pool_size}  in_use={s.in_use}  "
                f"total_created={s.total_created}  total_acquired={s.total_acquired}  "
                f"total_released={s.total_released}"
            )
        elif cmd == "drain":
            n = pool.drain()
            return f"Drained {n} object(s) from pool."
        elif cmd == "info":
            return f"size={pool.size}  pool_size={pool.pool_size}"
        return f"Unknown subcommand: {cmd}"

    async def observer_handler(args: str) -> str:
        """Usage: /observer <set value | get | watch name | unwatch name | count>"""
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /observer <set value | get | watch name | unwatch name | count>"
        obs = _get_observer()
        cmd = parts[0].lower()
        if cmd == "set":
            if len(parts) < 2:
                return "Usage: /observer set <value>"
            obs.value = " ".join(parts[1:])
            return f"Value set to {obs.value!r}"
        elif cmd == "get":
            return f"Current value: {obs.value!r}"
        elif cmd == "watch":
            if len(parts) < 2:
                return "Usage: /observer watch <name>"
            changes: list[str] = []
            def _watcher(event: str, **kwargs):
                changes.append(f"{event}: {kwargs}")
            obs.add_observer(parts[1], _watcher)
            return f"Observer {parts[1]!r} registered."
        elif cmd == "unwatch":
            if len(parts) < 2:
                return "Usage: /observer unwatch <name>"
            removed = obs.remove_observer(parts[1])
            return f"Removed: {removed}"
        elif cmd == "count":
            return f"Observer count: {obs.observer_count}"
        return f"Unknown subcommand: {cmd}"

    async def command_handler(args: str) -> str:
        """Usage: /command <set key value | delete key | undo | redo | history | clear>"""
        from lidco.patterns.command import SetValueCommand, DeleteKeyCommand
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /command <set key value | delete key | undo | redo | history | clear>"
        history = _get_history()
        if "target" not in _state:
            _state["target"] = {}
        target = _state["target"]
        cmd = parts[0].lower()
        if cmd == "set":
            if len(parts) < 3:
                return "Usage: /command set <key> <value>"
            c = SetValueCommand(target=target, key=parts[1], value=parts[2],  # type: ignore[arg-type]
                                description=f"set {parts[1]}")
            history.execute(c)
            return f"Executed: set {parts[1]} = {parts[2]!r}"
        elif cmd == "delete":
            if len(parts) < 2:
                return "Usage: /command delete <key>"
            c = DeleteKeyCommand(target=target, key=parts[1],  # type: ignore[arg-type]
                                 description=f"delete {parts[1]}")
            history.execute(c)
            return f"Executed: delete {parts[1]}"
        elif cmd == "undo":
            c = history.undo()
            return f"Undid: {c.description}" if c else "Nothing to undo."
        elif cmd == "redo":
            c = history.redo()
            return f"Redid: {c.description}" if c else "Nothing to redo."
        elif cmd == "history":
            cmds = history.history
            if not cmds:
                return "(empty)"
            lines = [f"  {i+1}. {c.description}" for i, c in enumerate(cmds)]
            return "\n".join(lines)
        elif cmd == "clear":
            history.clear()
            return "History cleared."
        elif cmd == "state":
            return str(target)
        return f"Unknown subcommand: {cmd}"

    registry.register(SlashCommand("cache", "LRU cache operations", cache_handler))
    registry.register(SlashCommand("pool", "Object pool stats and management", pool_handler))
    registry.register(SlashCommand("observer", "Observable value and observer management", observer_handler))
    registry.register(SlashCommand("command", "Command history with undo/redo", command_handler))
