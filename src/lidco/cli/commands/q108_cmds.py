"""Q108 CLI commands: /docgen /snippet /imports /error-monitor."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q108 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /docgen — docstring generator                                        #
    # ------------------------------------------------------------------ #

    async def docgen_handler(args: str) -> str:
        from lidco.docgen.generator import DocGenerator, DocStyle, DocGenError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_gen() -> DocGenerator:
            style = _state.get("docgen_style", DocStyle.GOOGLE)
            return DocGenerator(style=style)  # type: ignore[arg-type]

        if sub == "demo":
            source = (
                "def add(a: int, b: int) -> int:\n"
                "    return a + b\n\n"
                "class Calculator:\n"
                "    def multiply(self, x: float, y: float) -> float:\n"
                "        return x * y\n"
            )
            gen = _get_gen()
            functions = gen.parse_functions(source)
            lines = ["Docstring generation demo:", ""]
            for fn in functions:
                doc = gen.generate_docstring(fn)
                lines.append(f"# {fn.name}()")
                lines.append('"""')
                lines.append(doc)
                lines.append('"""')
                lines.append("")
            return "\n".join(lines)

        if sub == "parse":
            if not rest:
                return "Usage: /docgen parse <python source>"
            try:
                gen = _get_gen()
                functions = gen.parse_functions(rest)
                if not functions:
                    return "No functions found in source."
                lines = []
                for fn in functions:
                    params = ", ".join(p.name for p in fn.params)
                    ret = f" -> {fn.return_annotation}" if fn.return_annotation else ""
                    has_doc = " [has docstring]" if fn.has_docstring() else " [missing docstring]"
                    lines.append(f"  {fn.name}({params}){ret}{has_doc}")
                return "\n".join(lines)
            except DocGenError as exc:
                return f"Error: {exc}"

        if sub == "generate":
            if not rest:
                return "Usage: /docgen generate <def line or source>"
            source = rest if "def " in rest else f"def {rest}:\n    pass\n"
            try:
                gen = _get_gen()
                functions = gen.parse_functions(source)
                if not functions:
                    return "Could not parse function."
                doc = gen.generate_docstring(functions[0])
                return f'"""\n{doc}\n"""'
            except DocGenError as exc:
                return f"Error: {exc}"

        if sub == "check":
            if not rest:
                return "Usage: /docgen check <python source>"
            try:
                gen = _get_gen()
                missing = gen.needs_docstring(rest)
                if not missing:
                    return "All functions/classes have docstrings."
                return "Missing docstrings: " + ", ".join(missing)
            except DocGenError as exc:
                return f"Error: {exc}"

        if sub == "style":
            if not rest:
                current = _state.get("docgen_style", DocStyle.GOOGLE)
                return f"Current style: {current.value}. Options: google, numpy, rst, plain"
            try:
                style = DocStyle(rest.lower())
                _state["docgen_style"] = style
                return f"Docstring style set to: {style.value}"
            except ValueError:
                return f"Unknown style: {rest!r}. Options: google, numpy, rst, plain"

        return (
            "Usage: /docgen <sub>\n"
            "  demo                — show generation example\n"
            "  parse <source>      — parse functions from source\n"
            "  generate <source>   — generate docstring\n"
            "  check <source>      — find missing docstrings\n"
            "  style [name]        — get/set docstring style"
        )

    # ------------------------------------------------------------------ #
    # /snippet — snippet manager                                           #
    # ------------------------------------------------------------------ #

    async def snippet_handler(args: str) -> str:
        import tempfile
        from pathlib import Path
        from lidco.snippets.store import Snippet, SnippetStore, SnippetError

        def _get_store() -> SnippetStore:
            if "snippet_store" not in _state:
                tmp = Path(tempfile.gettempdir()) / "lidco_snippets"
                _state["snippet_store"] = SnippetStore(base_dir=tmp)
            return _state["snippet_store"]  # type: ignore[return-value]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "demo":
            store = SnippetStore(base_dir=Path(tempfile.mkdtemp()))
            store.save(Snippet(
                name="logger",
                body='import logging\nlog = logging.getLogger("${MODULE}")\n',
                description="Standard logger setup",
                language="python",
                tags=["logging", "setup"],
            ))
            store.save(Snippet(
                name="dataclass-base",
                body="@dataclass\nclass ${ClassName}:\n    ${field}: ${type}\n",
                description="Basic dataclass skeleton",
                language="python",
                tags=["dataclass"],
            ))
            lines = ["Snippet store demo:", ""]
            for s in store.list_all():
                expanded = s.expand({"MODULE": "myapp", "ClassName": "MyModel", "field": "name", "type": "str"})
                lines.append(f"# {s.name}: {s.description}")
                lines.append(f"  Variables: {s.variables()}")
                lines.append(f"  Expanded:\n{expanded}")
            return "\n".join(lines)

        if sub == "save":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /snippet save <name> <body>"
            name, body = tokens[0], tokens[1]
            try:
                store = _get_store()
                store.save(Snippet(name=name, body=body))
                return f"Snippet '{name}' saved."
            except SnippetError as exc:
                return f"Error: {exc}"

        if sub == "get":
            if not rest:
                return "Usage: /snippet get <name>"
            store = _get_store()
            s = store.get(rest)
            if s is None:
                return f"Snippet not found: {rest!r}"
            return f"# {s.name}\n{s.body}"

        if sub == "expand":
            tokens = rest.split(maxsplit=1)
            name = tokens[0] if tokens else ""
            bindings_raw = tokens[1] if len(tokens) > 1 else ""
            if not name:
                return "Usage: /snippet expand <name> [KEY=VAL ...]"
            store = _get_store()
            bindings: dict[str, str] = {}
            for pair in bindings_raw.split():
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    bindings[k] = v
            try:
                return store.expand(name, bindings)
            except SnippetError as exc:
                return f"Error: {exc}"

        if sub == "list":
            store = _get_store()
            snippets = store.list_all()
            if not snippets:
                return "No snippets saved."
            lines = [f"Snippets ({len(snippets)}):"]
            for s in snippets:
                tags = f" [{', '.join(s.tags)}]" if s.tags else ""
                lines.append(f"  {s.name} — {s.description}{tags}")
            return "\n".join(lines)

        if sub == "search":
            if not rest:
                return "Usage: /snippet search <query>"
            store = _get_store()
            results = store.search(rest)
            if not results:
                return f"No snippets matching: {rest!r}"
            return "\n".join(f"  {s.name} — {s.description}" for s in results)

        if sub == "delete":
            if not rest:
                return "Usage: /snippet delete <name>"
            store = _get_store()
            if store.delete(rest):
                return f"Snippet '{rest}' deleted."
            return f"Snippet not found: {rest!r}"

        if sub == "reset":
            _state.pop("snippet_store", None)
            return "Snippet store reset."

        return (
            "Usage: /snippet <sub>\n"
            "  demo                         — show snippet demo\n"
            "  save <name> <body>           — save a snippet\n"
            "  get <name>                   — show snippet\n"
            "  expand <name> [KEY=VAL ...]  — expand with variables\n"
            "  list                         — list all snippets\n"
            "  search <query>               — search snippets\n"
            "  delete <name>                — delete a snippet\n"
            "  reset                        — reset store"
        )

    # ------------------------------------------------------------------ #
    # /imports — import resolver                                           #
    # ------------------------------------------------------------------ #

    async def imports_handler(args: str) -> str:
        from lidco.imports.resolver import ImportResolver, ImportResolverError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_resolver() -> ImportResolver:
            if "resolver" not in _state:
                _state["resolver"] = ImportResolver()
            return _state["resolver"]  # type: ignore[return-value]

        if sub == "demo":
            source = "data = Path('.')\nresult = json.dumps({'a': 1})\nlog = getLogger('app')\n"
            resolver = ImportResolver()
            result = resolver.resolve(source)
            lines = [f"Source:\n{source}", "Detected undefined names:", ""]
            for name in result.undefined_names:
                lines.append(f"  {name!r}")
            lines.append("\nSuggested imports:")
            lines.append(result.import_block() or "  (none)")
            return "\n".join(lines)

        if sub == "resolve":
            if not rest:
                return "Usage: /imports resolve <python source>"
            try:
                resolver = _get_resolver()
                result = resolver.resolve(rest)
                if not result.undefined_names:
                    return "No undefined names found."
                lines = [f"Undefined: {', '.join(result.undefined_names)}", ""]
                block = result.import_block()
                lines.append("Suggested imports:")
                lines.append(block if block else "  (no known imports)")
                return "\n".join(lines)
            except ImportResolverError as exc:
                return f"Error: {exc}"

        if sub == "suggest":
            if not rest:
                return "Usage: /imports suggest <name>"
            resolver = _get_resolver()
            suggestion = resolver.suggest_for_name(rest)
            if suggestion is None:
                return f"No known import for: {rest!r}"
            stdlib = "stdlib" if suggestion.is_stdlib else "third-party"
            return f"{suggestion.import_stmt}  [{stdlib}, confidence: {suggestion.confidence:.0%}]"

        if sub == "known":
            resolver = _get_resolver()
            names = resolver.known_names()
            return f"Known names ({len(names)}): " + ", ".join(names[:30]) + (
                f" ... (+{len(names)-30} more)" if len(names) > 30 else ""
            )

        if sub == "prepend":
            if not rest:
                return "Usage: /imports prepend <python source>"
            try:
                resolver = _get_resolver()
                result = resolver.resolve(rest)
                new_source = resolver.prepend_imports(rest, result)
                return new_source
            except ImportResolverError as exc:
                return f"Error: {exc}"

        return (
            "Usage: /imports <sub>\n"
            "  demo              — show resolver demo\n"
            "  resolve <source>  — find undefined names + suggest imports\n"
            "  suggest <name>    — suggest import for one name\n"
            "  known             — list all known names\n"
            "  prepend <source>  — return source with imports prepended"
        )

    # ------------------------------------------------------------------ #
    # /error-monitor — error pattern monitor                              #
    # ------------------------------------------------------------------ #

    async def error_monitor_handler(args: str) -> str:
        from lidco.monitoring.error_monitor import (
            ErrorMonitor, ErrorPattern, Severity, MonitorError,
        )

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_monitor() -> ErrorMonitor:
            if "monitor" not in _state:
                _state["monitor"] = ErrorMonitor.with_defaults()
            return _state["monitor"]  # type: ignore[return-value]

        if sub == "demo":
            monitor = ErrorMonitor.with_defaults()
            log_lines = [
                "2024-01-01 12:00:01 INFO Starting app...",
                "2024-01-01 12:00:02 ERROR TypeError: 'NoneType' object is not subscriptable",
                "2024-01-01 12:00:03 INFO Retrying...",
                "Traceback (most recent call last):",
                "  File 'app.py', line 42, in main",
                "ImportError: No module named 'requests'",
                "HTTP 500 Internal Server Error",
            ]
            events = monitor.feed_lines(log_lines, source="demo")
            lines = [f"Processed {len(log_lines)} lines, found {len(events)} event(s):", ""]
            for e in events:
                lines.append(f"  {e.format()}")
            summary = monitor.summary()
            lines.append(f"\nSummary: {summary}")
            return "\n".join(lines)

        if sub == "feed":
            if not rest:
                return "Usage: /error-monitor feed <log line>"
            monitor = _get_monitor()
            events = monitor.feed_line(rest)
            if not events:
                return f"No patterns matched: {rest!r}"
            return "\n".join(e.format() for e in events)

        if sub == "events":
            monitor = _get_monitor()
            limit = 20
            if rest.isdigit():
                limit = int(rest)
            events = monitor.events(limit=limit)
            if not events:
                return "No events captured."
            return "\n".join(e.format() for e in events)

        if sub == "summary":
            monitor = _get_monitor()
            s = monitor.summary()
            total = monitor.event_count()
            if total == 0:
                return "No events captured."
            lines = [f"Total events: {total}"]
            for severity, count in sorted(s.items()):
                lines.append(f"  {severity.upper()}: {count}")
            return "\n".join(lines)

        if sub == "patterns":
            monitor = _get_monitor()
            patterns = monitor.list_patterns()
            lines = [f"Active patterns ({len(patterns)}):"]
            for p in patterns:
                lines.append(f"  [{p.severity.value.upper()}] {p.id} — {p.description}")
            return "\n".join(lines)

        if sub == "clear":
            monitor = _get_monitor()
            monitor.clear_events()
            return "Events cleared."

        if sub == "reset":
            _state.pop("monitor", None)
            return "Error monitor reset to defaults on next use."

        return (
            "Usage: /error-monitor <sub>\n"
            "  demo            — process sample log and show events\n"
            "  feed <line>     — feed one log line\n"
            "  events [N]      — show last N events (default 20)\n"
            "  summary         — show event counts by severity\n"
            "  patterns        — list active patterns\n"
            "  clear           — clear event history\n"
            "  reset           — reset monitor"
        )

    registry.register(SlashCommand("docgen", "Docstring generator", docgen_handler))
    registry.register(SlashCommand("snippet", "Code snippet manager", snippet_handler))
    registry.register(SlashCommand("imports", "Import resolver", imports_handler))
    registry.register(SlashCommand("error-monitor", "Error pattern monitor", error_monitor_handler))
