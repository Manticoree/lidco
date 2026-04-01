"""Q209 CLI commands: /semantic-search, /intent, /code-query, /context-assemble."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q209 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /semantic-search
    # ------------------------------------------------------------------

    async def semantic_search_handler(args: str) -> str:
        from lidco.understanding.semantic_search import (
            SemanticSearchIndex,
            SearchScope,
        )

        if "search_index" not in _state:
            _state["search_index"] = SemanticSearchIndex()
        idx: SemanticSearchIndex = _state["search_index"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            # add <path> <content>
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /semantic-search add <path> <content>"
            path, content = tokens
            idx.add_document(path, path, content)
            return f"Added document: {path}"

        if sub == "query":
            if not rest:
                return "Usage: /semantic-search query <text>"
            results = idx.search(rest)
            if not results:
                return "No results found."
            lines = [f"{len(results)} result(s):"]
            for r in results:
                lines.append(f"  {r.path} (score={r.score}): {r.snippet[:80]}")
            return "\n".join(lines)

        if sub == "count":
            return f"Indexed documents: {idx.document_count()}"

        if sub == "clear":
            idx.clear()
            return "Index cleared."

        return (
            "Usage: /semantic-search <subcommand>\n"
            "  add <path> <content>  — index a document\n"
            "  query <text>          — search the index\n"
            "  count                 — show document count\n"
            "  clear                 — clear the index"
        )

    # ------------------------------------------------------------------
    # /intent
    # ------------------------------------------------------------------

    async def intent_handler(args: str) -> str:
        from lidco.understanding.intent_classifier import IntentClassifier

        if "classifier" not in _state:
            _state["classifier"] = IntentClassifier()
        clf: IntentClassifier = _state["classifier"]  # type: ignore[assignment]

        query = args.strip()
        if not query:
            return "Usage: /intent <query>"

        result = clf.classify(query)
        secondary = result.secondary_intent.value if result.secondary_intent else "none"
        return (
            f"Intent: {result.intent.value}\n"
            f"Confidence: {result.confidence}\n"
            f"Secondary: {secondary}"
        )

    # ------------------------------------------------------------------
    # /code-query
    # ------------------------------------------------------------------

    async def code_query_handler(args: str) -> str:
        from lidco.understanding.query_engine import CodeQueryEngine

        if "query_engine" not in _state:
            _state["query_engine"] = CodeQueryEngine()
        engine: CodeQueryEngine = _state["query_engine"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "search":
            if not rest:
                return "Usage: /code-query search <query>"
            result = engine.query(rest)
            if not result.matches:
                return "No matches found."
            lines = [f"{result.total} match(es):"]
            for m in result.matches:
                lines.append(f"  {m['path']} — {m['name']} (score={m['score']})")
            return "\n".join(lines)

        if sub == "explain":
            if not rest:
                return "Usage: /code-query explain <query>"
            return engine.explain(rest)

        if sub == "history":
            h = engine.history()
            if not h:
                return "No query history."
            return "\n".join(f"  {i+1}. {q}" for i, q in enumerate(h))

        return (
            "Usage: /code-query <subcommand>\n"
            "  search <query>  — search code\n"
            "  explain <query> — explain query interpretation\n"
            "  history         — show query history"
        )

    # ------------------------------------------------------------------
    # /context-assemble
    # ------------------------------------------------------------------

    async def context_assemble_handler(args: str) -> str:
        from lidco.understanding.context_assembler import ContextAssembler

        if "assembler" not in _state:
            _state["assembler"] = ContextAssembler()
        asm: ContextAssembler = _state["assembler"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /context-assemble add <path> <content>"
            path, content = tokens
            asm.add_source(path, content)
            return f"Added source: {path}"

        if sub == "run":
            if not rest:
                return "Usage: /context-assemble run <query>"
            result = asm.assemble(rest)
            lines = [
                f"Assembled {len(result.entries)} file(s), "
                f"{result.total_tokens} tokens ({result.budget_used:.1%} budget)"
            ]
            for e in result.entries:
                lines.append(f"  {e.path} (relevance={e.relevance}, ~{e.tokens_estimate} tokens)")
            return "\n".join(lines)

        if sub == "count":
            return f"Sources: {asm.source_count()}"

        if sub == "clear":
            asm.clear()
            return "Sources cleared."

        return (
            "Usage: /context-assemble <subcommand>\n"
            "  add <path> <content>  — add a source file\n"
            "  run <query>           — assemble context for query\n"
            "  count                 — show source count\n"
            "  clear                 — clear all sources"
        )

    registry.register(SlashCommand("semantic-search", "TF-IDF semantic code search", semantic_search_handler))
    registry.register(SlashCommand("intent", "Classify user query intent", intent_handler))
    registry.register(SlashCommand("code-query", "Natural language code query", code_query_handler))
    registry.register(SlashCommand("context-assemble", "Auto-gather relevant context", context_assemble_handler))
