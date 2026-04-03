"""Q250 CLI commands: /detect-lang, /parse-universal, /cross-link, /polyglot-search."""
from __future__ import annotations


def register(registry) -> None:  # noqa: ANN001
    """Register Q250 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /detect-lang
    # ------------------------------------------------------------------

    async def detect_lang_handler(args: str) -> str:
        from lidco.polyglot.detector import LanguageDetector

        detector = LanguageDetector()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "file":
            if not rest:
                return "Usage: /detect-lang file <filename>"
            result = detector.detect(rest)
            return f"{result.language} (confidence={result.confidence:.2f}, method={result.method})"

        if sub == "content":
            if not rest:
                return "Usage: /detect-lang content <source code>"
            result = detector.detect("", rest)
            return f"{result.language} (confidence={result.confidence:.2f}, method={result.method})"

        if sub == "languages":
            langs = detector.supported_languages()
            return "Supported languages: " + ", ".join(langs)

        return (
            "Usage: /detect-lang <subcommand>\n"
            "  file <filename>       — detect by filename\n"
            "  content <source code> — detect by content\n"
            "  languages             — list supported languages"
        )

    # ------------------------------------------------------------------
    # /parse-universal
    # ------------------------------------------------------------------

    async def parse_universal_handler(args: str) -> str:
        from lidco.polyglot.parser import UniversalParser

        parser = UniversalParser()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "parse":
            if not rest:
                return "Usage: /parse-universal parse <language> <source>"
            lang_parts = rest.split(maxsplit=1)
            lang = lang_parts[0]
            source = lang_parts[1] if len(lang_parts) > 1 else ""
            symbols = parser.parse(source, lang)
            if not symbols:
                return "No symbols found."
            lines = [f"{len(symbols)} symbol(s):"]
            for s in symbols:
                lines.append(f"  {s.kind} {s.name} L{s.line}")
            return "\n".join(lines)

        if sub == "imports":
            if not rest:
                return "Usage: /parse-universal imports <language> <source>"
            lang_parts = rest.split(maxsplit=1)
            lang = lang_parts[0]
            source = lang_parts[1] if len(lang_parts) > 1 else ""
            imports = parser.extract_imports(source, lang)
            if not imports:
                return "No imports found."
            return "Imports: " + ", ".join(imports)

        return (
            "Usage: /parse-universal <subcommand>\n"
            "  parse <lang> <source>   — extract symbols\n"
            "  imports <lang> <source> — extract imports"
        )

    # ------------------------------------------------------------------
    # /cross-link
    # ------------------------------------------------------------------

    async def cross_link_handler(args: str) -> str:
        from lidco.polyglot.linker import CrossLanguageLinker
        from lidco.polyglot.parser import Symbol

        linker = CrossLanguageLinker()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "demo":
            # Demonstrate with sample symbols
            py_sym = Symbol(name="process", kind="function", language="python", line=1)
            js_sym = Symbol(name="process", kind="function", language="javascript", line=5)
            linker.add_symbols([py_sym, js_sym])
            return linker.summary()

        if sub == "summary":
            return linker.summary()

        return (
            "Usage: /cross-link <subcommand>\n"
            "  demo    — demonstrate cross-language linking\n"
            "  summary — show link summary"
        )

    # ------------------------------------------------------------------
    # /polyglot-search
    # ------------------------------------------------------------------

    async def polyglot_search_handler(args: str) -> str:
        from lidco.polyglot.search import PolyglotSearch

        search = PolyglotSearch()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "normalize":
            if not rest:
                return "Usage: /polyglot-search normalize <name>"
            return f"Normalized: {search.normalize_name(rest)}"

        if sub == "stats":
            st = search.stats()
            if not st:
                return "No symbols indexed."
            return "\n".join(f"  {lang}: {count}" for lang, count in sorted(st.items()))

        return (
            "Usage: /polyglot-search <subcommand>\n"
            "  normalize <name> — normalize a symbol name\n"
            "  stats            — show symbol stats"
        )

    registry.register(SlashCommand("detect-lang", "Detect programming language", detect_lang_handler))
    registry.register(SlashCommand("parse-universal", "Universal symbol parser", parse_universal_handler))
    registry.register(SlashCommand("cross-link", "Cross-language symbol linking", cross_link_handler))
    registry.register(SlashCommand("polyglot-search", "Polyglot symbol search", polyglot_search_handler))
