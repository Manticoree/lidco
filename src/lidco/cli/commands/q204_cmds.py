"""Q204 CLI commands: /transcript, /transcript-search, /timeline, /transcript-export."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q204 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /transcript
    # ------------------------------------------------------------------

    async def transcript_handler(args: str) -> str:
        from lidco.transcript.store import TranscriptStore

        if "store" not in _state:
            _state["store"] = TranscriptStore()
        store: TranscriptStore = _state["store"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            entries = store.list_entries(limit=20)
            if not entries:
                return "No transcript entries."
            lines = [f"{len(entries)} entry(ies):"]
            for e in entries:
                preview = e.content[:60].replace("\n", " ")
                lines.append(f"  [{e.role}] {e.id}: {preview}")
            return "\n".join(lines)

        if sub == "count":
            return f"Transcript has {store.count()} entry(ies)."

        if sub == "get":
            if not rest:
                return "Usage: /transcript get <id>"
            entry = store.get(rest)
            if entry is None:
                return f"Entry '{rest}' not found."
            return f"[{entry.role}] {entry.content}"

        if sub == "clear":
            removed = store.clear()
            return f"Cleared {removed} entry(ies)."

        return (
            "Usage: /transcript <subcommand>\n"
            "  list    — list recent entries\n"
            "  count   — show entry count\n"
            "  get <id> — show entry by ID\n"
            "  clear   — remove all entries"
        )

    # ------------------------------------------------------------------
    # /transcript-search
    # ------------------------------------------------------------------

    async def transcript_search_handler(args: str) -> str:
        from lidco.transcript.search import TranscriptSearch
        from lidco.transcript.store import TranscriptStore

        if "store" not in _state:
            _state["store"] = TranscriptStore()
        store: TranscriptStore = _state["store"]  # type: ignore[assignment]
        search = TranscriptSearch(store)

        query = args.strip()
        if not query:
            return "Usage: /transcript-search <query>"

        matches = search.regex_search(query)
        if not matches:
            return f"No matches for '{query}'."
        lines = [f"Found {len(matches)} match(es) for '{query}':"]
        for m in matches[:20]:
            preview = m.context[:60].replace("\n", " ")
            lines.append(f"  [{m.entry.role}] {m.entry.id}: {preview}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /timeline
    # ------------------------------------------------------------------

    async def timeline_handler(args: str) -> str:
        from lidco.transcript.timeline import SessionTimeline

        if "timeline" not in _state:
            _state["timeline"] = SessionTimeline()
        tl: SessionTimeline = _state["timeline"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "show":
            return tl.render_text()

        if sub == "summary":
            return tl.summary()

        if sub == "count":
            return f"Timeline has {tl.event_count()} event(s)."

        return (
            "Usage: /timeline <subcommand>\n"
            "  show     — render text timeline\n"
            "  summary  — show summary\n"
            "  count    — show event count"
        )

    # ------------------------------------------------------------------
    # /transcript-export
    # ------------------------------------------------------------------

    async def transcript_export_handler(args: str) -> str:
        from lidco.transcript.export import ExportFormat, TranscriptExporter
        from lidco.transcript.store import TranscriptStore

        if "store" not in _state:
            _state["store"] = TranscriptStore()
        store: TranscriptStore = _state["store"]  # type: ignore[assignment]
        exporter = TranscriptExporter(store)

        fmt = args.strip().lower() if args.strip() else "text"
        format_map = {
            "markdown": ExportFormat.MARKDOWN,
            "md": ExportFormat.MARKDOWN,
            "json": ExportFormat.JSON,
            "text": ExportFormat.TEXT,
            "txt": ExportFormat.TEXT,
        }

        export_fmt = format_map.get(fmt)
        if export_fmt is None:
            return f"Unknown format '{fmt}'. Supported: markdown, json, text"

        result = exporter.export(export_fmt)
        if not result.strip():
            return "Nothing to export — transcript is empty."
        return result

    registry.register(SlashCommand("transcript", "Transcript store", transcript_handler))
    registry.register(SlashCommand("transcript-search", "Search transcript", transcript_search_handler))
    registry.register(SlashCommand("timeline", "Session timeline", timeline_handler))
    registry.register(SlashCommand("transcript-export", "Export transcript", transcript_export_handler))
