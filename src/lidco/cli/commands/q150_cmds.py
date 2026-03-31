"""Q150 CLI commands: /log."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q150 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def log_handler(args: str) -> str:
        from lidco.logging.structured_logger import StructuredLogger
        from lidco.logging.log_router import LogRouter
        from lidco.logging.log_rotator import LogRotator, RotationPolicy
        from lidco.logging.log_searcher import LogSearcher, SearchQuery

        if "logger" not in _state:
            _state["logger"] = StructuredLogger("cli")
        if "router" not in _state:
            _state["router"] = LogRouter()
        if "rotator" not in _state:
            _state["rotator"] = LogRotator()
        if "searcher" not in _state:
            _state["searcher"] = LogSearcher()

        logger: StructuredLogger = _state["logger"]  # type: ignore[assignment]
        router: LogRouter = _state["router"]  # type: ignore[assignment]
        rotator: LogRotator = _state["rotator"]  # type: ignore[assignment]
        searcher: LogSearcher = _state["searcher"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "write":
            w_parts = rest.strip().split(maxsplit=1)
            level = w_parts[0].lower() if w_parts else "info"
            msg = w_parts[1] if len(w_parts) > 1 else ""
            if not msg:
                return "Usage: /log write <level> <message>"
            valid = {"debug", "info", "warning", "error", "critical"}
            if level not in valid:
                return f"Invalid level '{level}'. Choose from: {', '.join(sorted(valid))}"
            getattr(logger, level)(msg)
            router.route(logger.records[-1])
            return f"Logged [{level.upper()}]: {msg}"

        if sub == "search":
            query = SearchQuery(text=rest.strip() or None)
            result = searcher.search(logger.records, query)
            if not result.records:
                return "No matching records."
            lines = [f"Found {result.total_matched} record(s):"]
            for r in result.records[:10]:
                lines.append(f"  [{r.level.upper()}] {r.logger_name}: {r.message}")
            if result.total_matched > 10:
                lines.append(f"  ... and {result.total_matched - 10} more")
            return "\n".join(lines)

        if sub == "routes":
            routes = router.list_routes()
            if not routes:
                return "No routes configured."
            lines = [f"Routes ({len(routes)}):"]
            for r in routes:
                status = "enabled" if r.enabled else "disabled"
                lines.append(f"  {r.name} [{r.min_level}] ({status})")
            return "\n".join(lines)

        if sub == "rotate":
            if not logger.records:
                return "No records to rotate."
            archive = rotator.rotate(logger.records)
            logger.clear()
            return f"Rotated {archive.record_count} record(s) into archive {archive.id}."

        if sub == "stats":
            counts = searcher.count_by_level(logger.records)
            total = len(logger.records)
            archived = rotator.total_archived
            routed = router.routed_count
            lines = [
                f"Total records: {total}",
                f"Archived: {archived}",
                f"Routed: {routed}",
                f"By level: {json.dumps(counts)}",
            ]
            return "\n".join(lines)

        return "Usage: /log write|search|routes|rotate|stats"

    registry.register(SlashCommand("log", "Log management & structured logging", log_handler))
