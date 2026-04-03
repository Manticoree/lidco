"""Q258 CLI commands: /doc-coverage, /gen-docs, /lint-docs, /search-docs."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q258 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /doc-coverage
    # ------------------------------------------------------------------

    async def doc_coverage_handler(args: str) -> str:
        from lidco.docgen.coverage import DocCoverageAnalyzer

        if "coverage" not in _state:
            _state["coverage"] = DocCoverageAnalyzer()

        analyzer: DocCoverageAnalyzer = _state["coverage"]  # type: ignore[assignment]

        source = args.strip()
        if not source:
            return "Usage: /doc-coverage <python-source>"

        try:
            result = analyzer.analyze(source)
        except ValueError as exc:
            return f"Error: {exc}"

        return analyzer.summary(result)

    # ------------------------------------------------------------------
    # /gen-docs
    # ------------------------------------------------------------------

    async def gen_docs_handler(args: str) -> str:
        from lidco.docgen.generator_v2 import DocGeneratorV2

        if "gen" not in _state:
            _state["gen"] = DocGeneratorV2()

        gen: DocGeneratorV2 = _state["gen"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "module":
            inner = rest.split(maxsplit=1)
            name = inner[0] if inner else "unnamed"
            source = inner[1] if len(inner) > 1 else ""
            if not source:
                return "Usage: /gen-docs module <name> <source>"
            return gen.generate_module(source, name)

        if sub == "function":
            inner = rest.split(maxsplit=1)
            func_name = inner[0] if inner else ""
            source = inner[1] if len(inner) > 1 else ""
            if not func_name or not source:
                return "Usage: /gen-docs function <name> <source>"
            return gen.generate_function(source, func_name)

        if sub == "class":
            inner = rest.split(maxsplit=1)
            cls_name = inner[0] if inner else ""
            source = inner[1] if len(inner) > 1 else ""
            if not cls_name or not source:
                return "Usage: /gen-docs class <name> <source>"
            return gen.generate_class(source, cls_name)

        return "Usage: /gen-docs <module|function|class> ..."

    # ------------------------------------------------------------------
    # /lint-docs
    # ------------------------------------------------------------------

    async def lint_docs_handler(args: str) -> str:
        from lidco.docgen.linter import DocLinter

        if "linter" not in _state:
            _state["linter"] = DocLinter()

        linter: DocLinter = _state["linter"]  # type: ignore[assignment]

        source = args.strip()
        if not source:
            return "Usage: /lint-docs <python-source>"

        try:
            issues = linter.lint(source)
        except ValueError as exc:
            return f"Error: {exc}"

        if not issues:
            return "No documentation lint issues found."

        lines = [linter.summary(issues), ""]
        for issue in issues:
            lines.append(f"  L{issue.line} [{issue.severity}] {issue.rule}: {issue.message}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /search-docs
    # ------------------------------------------------------------------

    async def search_docs_handler(args: str) -> str:
        from lidco.docgen.search_engine import DocSearchEngine

        if "search" not in _state:
            _state["search"] = DocSearchEngine()

        engine: DocSearchEngine = _state["search"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "index":
            # /search-docs index <title> | <content>
            if "|" not in rest:
                return "Usage: /search-docs index <title> | <content>"
            title, content = rest.split("|", 1)
            engine.index(title.strip(), content.strip())
            return f"Indexed: {title.strip()}"

        if sub == "query":
            if not rest:
                return "Usage: /search-docs query <search-terms>"
            results = engine.search(rest)
            if not results:
                return "No results found."
            lines = [f"Found {len(results)} result(s):"]
            for r in results:
                lines.append(f"  [{r.score}] {r.title}: {r.snippet[:80]}")
            return "\n".join(lines)

        if sub == "clear":
            engine.clear()
            return "Search index cleared."

        if sub == "stats":
            s = engine.stats()
            return f"Indexed: {s['indexed_count']} docs, {s['total_terms']} unique terms"

        return "Usage: /search-docs <index|query|clear|stats> ..."

    # ------------------------------------------------------------------
    # Register all
    # ------------------------------------------------------------------

    registry.register(SlashCommand("doc-coverage", "Analyze documentation coverage", doc_coverage_handler))
    registry.register(SlashCommand("gen-docs", "Generate documentation from source", gen_docs_handler))
    registry.register(SlashCommand("lint-docs", "Lint documentation for issues", lint_docs_handler))
    registry.register(SlashCommand("search-docs", "Search indexed documentation", search_docs_handler))
