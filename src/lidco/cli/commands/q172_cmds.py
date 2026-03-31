"""CLI commands for Q172 — Embeddings & Semantic Retrieval."""

from __future__ import annotations

from lidco.cli.commands.registry import SlashCommand

_state: dict[str, object] = {}


def register_q172_commands(registry) -> None:
    """Register Q172 commands with *registry*."""

    def _get_store():
        from lidco.embeddings.vector_store import VectorStore

        if "store" not in _state:
            _state["store"] = VectorStore()
        return _state["store"]

    def _get_generator():
        from lidco.embeddings.generator import EmbeddingGenerator

        if "generator" not in _state:
            _state["generator"] = EmbeddingGenerator()
        return _state["generator"]

    def _get_retriever():
        from lidco.embeddings.retriever import HybridRetriever

        if "retriever" not in _state:
            _state["retriever"] = HybridRetriever(
                vector_store=_get_store(),
                generator=_get_generator(),
            )
        return _state["retriever"]

    def _get_injector():
        from lidco.embeddings.auto_context import AutoContextInjector

        if "injector" not in _state:
            _state["injector"] = AutoContextInjector(retriever=_get_retriever())
        return _state["injector"]

    # ------------------------------------------------------------------
    # /index build|status|clear
    # ------------------------------------------------------------------

    async def index_handler(args: str) -> str:
        sub = args.strip().lower()
        store = _get_store()

        if sub == "build":
            return "Indexing started... (would index project files)"
        if sub == "status":
            return f"Index status: {store.count()} entries"
        if sub == "clear":
            count = store.count()
            store.clear()
            return f"Index cleared: {count} entries removed"
        return "Usage: /index build|status|clear"

    # ------------------------------------------------------------------
    # /search <query> [--semantic|--keyword|--hybrid]
    # ------------------------------------------------------------------

    async def search_handler(args: str) -> str:
        text = args.strip()
        if not text:
            return "Usage: /search <query> [--semantic|--keyword|--hybrid]"

        retriever = _get_retriever()

        mode = "hybrid"
        query = text
        for flag in ("--semantic", "--keyword", "--hybrid"):
            if flag in query:
                mode = flag.lstrip("-")
                query = query.replace(flag, "").strip()

        if not query:
            return "Usage: /search <query> [--semantic|--keyword|--hybrid]"

        if mode == "semantic":
            results = retriever.search_semantic(query, top_k=10)
        elif mode == "keyword":
            results = retriever.search_keyword(query, top_k=10)
        else:
            results = retriever.search(query, top_k=10)

        if not results:
            return f"No results found for: {query}"

        lines: list[str] = [f"Search results ({mode}):"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"  {i}. {r.file_path}:{r.start_line}-{r.end_line}"
                f" (score: {r.score:.4f}, type: {r.chunk_type})"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /context-sources
    # ------------------------------------------------------------------

    async def context_sources_handler(args: str) -> str:
        injector = _get_injector()
        cfg = injector.config
        status = "enabled" if cfg.enabled else "disabled"
        return (
            f"Auto-context injection: {status}\n"
            f"Max snippets: {cfg.max_snippets}\n"
            f"Max tokens: {cfg.max_tokens}"
        )

    # ------------------------------------------------------------------

    registry.register(
        SlashCommand("index", "Manage semantic index (build/status/clear)", index_handler)
    )
    registry.register(
        SlashCommand("search", "Semantic search across codebase", search_handler)
    )
    registry.register(
        SlashCommand(
            "context-sources",
            "Show auto-context injection settings",
            context_sources_handler,
        )
    )
