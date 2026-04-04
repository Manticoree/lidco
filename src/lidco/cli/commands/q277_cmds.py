"""Q277 CLI commands: /annotate, /markers, /annotation-overlay, /search-annotations."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q277 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # shared engine/registry singletons (per registration call)
    _engine = None
    _markers = None

    def _get_engine():
        nonlocal _engine
        if _engine is None:
            from lidco.annotations.engine import AnnotationEngine
            _engine = AnnotationEngine()
        return _engine

    def _get_markers():
        nonlocal _markers
        if _markers is None:
            from lidco.annotations.markers import MarkerRegistry
            _markers = MarkerRegistry()
        return _markers

    # ------------------------------------------------------------------
    # /annotate
    # ------------------------------------------------------------------

    async def annotate_handler(args: str) -> str:
        engine = _get_engine()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            tokens = rest.split(maxsplit=3)
            if len(tokens) < 3:
                return "Usage: /annotate add <file> <line> <text> [category]"
            file_path = tokens[0]
            try:
                line = int(tokens[1])
            except ValueError:
                return "Line must be an integer."
            remaining = tokens[2] if len(tokens) == 3 else tokens[2]
            # check for optional category at end
            if len(tokens) == 4:
                text = tokens[2]
                category = tokens[3]
            else:
                text = tokens[2]
                category = "note"
            ann = engine.add(file_path, line, text, category=category)
            return f"Added annotation {ann.id} at {file_path}:{line}."

        if sub == "remove":
            if not rest:
                return "Usage: /annotate remove <id>"
            ok = engine.remove(rest)
            return f"Removed {rest}." if ok else f"Annotation {rest} not found."

        if sub == "list":
            fp = rest if rest else None
            if fp:
                anns = engine.for_file(fp)
            else:
                anns = engine.all_annotations()
            if not anns:
                return "No annotations."
            lines = []
            for a in anns:
                lines.append(f"  {a.id}  {a.file_path}:{a.line}  [{a.category}] {a.text}")
            return "\n".join(lines)

        if sub == "clear":
            fp = rest if rest else None
            n = engine.clear(fp)
            return f"Cleared {n} annotation(s)."

        return (
            "Usage: /annotate <subcommand>\n"
            "  add <file> <line> <text> [category] — add annotation\n"
            "  remove <id>                         — remove annotation\n"
            "  list [file]                         — list annotations\n"
            "  clear [file]                        — clear annotations"
        )

    # ------------------------------------------------------------------
    # /markers
    # ------------------------------------------------------------------

    async def markers_handler(args: str) -> str:
        reg = _get_markers()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "list":
            markers = reg.all_markers()
            if not markers:
                return "No markers."
            lines = []
            for m in markers:
                lines.append(f"  {m.name} (prefix={m.prefix}, priority={m.priority})")
            return "\n".join(lines)

        if sub == "add":
            tokens = rest.split()
            if len(tokens) < 2:
                return "Usage: /markers add <name> <prefix> [priority]"
            name = tokens[0]
            prefix = tokens[1]
            priority = int(tokens[2]) if len(tokens) > 2 else 0
            from lidco.annotations.markers import Marker
            reg.register(Marker(name=name, prefix=prefix, priority=priority))
            return f"Registered marker {name}."

        if sub == "remove":
            if not rest:
                return "Usage: /markers remove <name>"
            ok = reg.remove(rest)
            return f"Removed {rest}." if ok else f"Cannot remove {rest} (built-in or not found)."

        if sub == "scan":
            if not rest:
                return "Usage: /markers scan <text>"
            hits = reg.scan_text(rest)
            if not hits:
                return "No markers found in text."
            lines = []
            for h in hits:
                lines.append(f"  line {h['line']}: {h['marker']} — {h['text']}")
            return "\n".join(lines)

        return (
            "Usage: /markers <subcommand>\n"
            "  list                          — list all markers\n"
            "  add <name> <prefix> [priority] — add custom marker\n"
            "  remove <name>                 — remove custom marker\n"
            "  scan <text>                   — scan text for markers"
        )

    # ------------------------------------------------------------------
    # /annotation-overlay
    # ------------------------------------------------------------------

    async def overlay_handler(args: str) -> str:
        from lidco.annotations.overlay import AnnotationOverlay

        engine = _get_engine()
        overlay = AnnotationOverlay(engine, _get_markers())
        file_path = args.strip()
        if not file_path:
            return "Usage: /annotation-overlay <file>"
        # dummy code lines for demonstration
        code_lines = [
            "# file: " + file_path,
            "def main():",
            '    print("hello")',
            "    return 0",
        ]
        text = overlay.render_text(file_path, code_lines)
        return text if text else "No overlay content."

    # ------------------------------------------------------------------
    # /search-annotations
    # ------------------------------------------------------------------

    async def search_annotations_handler(args: str) -> str:
        from lidco.annotations.search import AnnotationSearch

        engine = _get_engine()
        search = AnnotationSearch(engine)
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "query":
            if not rest:
                return "Usage: /search-annotations query <text>"
            results = search.search(rest)
            if not results:
                return "No results."
            lines = []
            for r in results:
                a = r.annotation
                lines.append(f"  [{r.relevance:.1f}] {a.file_path}:{a.line} [{a.category}] {a.text}")
            return "\n".join(lines)

        if sub == "by-file":
            grouped = search.by_file()
            if not grouped:
                return "No annotations."
            lines = []
            for fp, anns in grouped.items():
                lines.append(f"  {fp}: {len(anns)} annotation(s)")
            return "\n".join(lines)

        if sub == "by-category":
            grouped = search.by_category()
            if not grouped:
                return "No annotations."
            lines = []
            for cat, anns in grouped.items():
                lines.append(f"  {cat}: {len(anns)} annotation(s)")
            return "\n".join(lines)

        if sub == "stats":
            s = search.stats()
            return (
                f"Total: {s['total']}  "
                f"Files: {len(s['by_file'])}  "
                f"Categories: {len(s['by_category'])}  "
                f"Authors: {len(s['by_author'])}"
            )

        if sub == "export":
            return search.export()

        return (
            "Usage: /search-annotations <subcommand>\n"
            "  query <text>   — search annotations\n"
            "  by-file        — group by file\n"
            "  by-category    — group by category\n"
            "  stats          — show statistics\n"
            "  export         — export as JSON"
        )

    registry.register(SlashCommand("annotate", "Inline annotation management", annotate_handler))
    registry.register(SlashCommand("markers", "Code marker management", markers_handler))
    registry.register(SlashCommand("annotation-overlay", "Show annotated code overlay", overlay_handler))
    registry.register(SlashCommand("search-annotations", "Search and aggregate annotations", search_annotations_handler))
