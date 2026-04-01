"""Q199 CLI commands: /query, /ast-query, /query-cache, /query-explain."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q199 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /query
    # ------------------------------------------------------------------

    async def query_handler(args: str) -> str:
        from lidco.query.parser import QueryParser, QueryParseError
        from lidco.query.executor import QueryExecutor, QueryResult

        if "executor" not in _state:
            _state["executor"] = QueryExecutor()
        executor: QueryExecutor = _state["executor"]  # type: ignore[assignment]

        query_str = args.strip()
        if not query_str:
            return "Usage: /query SELECT <fields> [WHERE ...] [ORDER BY ...] [LIMIT n]"

        parser = QueryParser()
        try:
            parsed = parser.parse(query_str)
        except QueryParseError as exc:
            return f"Parse error: {exc}"

        result: QueryResult = executor.execute(parsed)
        if not result.records:
            return f"No results ({result.query_time_ms:.1f}ms)"

        lines = [f"{result.total} result(s) in {result.query_time_ms:.1f}ms:"]
        for rec in result.records:
            fields = {f: getattr(rec, f, "") for f in parsed.select_fields}
            parts = [f"{k}={v}" for k, v in fields.items()]
            lines.append("  " + ", ".join(parts))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /ast-query
    # ------------------------------------------------------------------

    async def ast_query_handler(args: str) -> str:
        from lidco.query.ast_query import ASTQueryEngine, ASTNode, ASTPattern

        query_str = args.strip()
        if not query_str:
            return "Usage: /ast-query <node_type> [name_pattern]"

        parts = query_str.split(maxsplit=1)
        node_type = parts[0]
        name_pat = parts[1] if len(parts) > 1 else None

        if "ast_root" not in _state:
            return "No AST loaded. Load a file first."

        root: ASTNode = _state["ast_root"]  # type: ignore[assignment]
        engine = ASTQueryEngine()
        pattern = ASTPattern(node_type=node_type, name_pattern=name_pat)
        matches = engine.find(root, pattern)

        if not matches:
            return "No matching AST nodes."
        lines = [f"{len(matches)} match(es):"]
        for n in matches:
            lines.append(f"  {n.type} {n.name!r} (line {n.line})")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /query-cache
    # ------------------------------------------------------------------

    async def query_cache_handler(args: str) -> str:
        from lidco.query.cache import QueryCache

        if "cache" not in _state:
            _state["cache"] = QueryCache()
        cache: QueryCache = _state["cache"]  # type: ignore[assignment]

        sub = args.strip().lower()

        if sub == "stats":
            s = cache.stats()
            return (
                f"Cache stats: {s['size']} entries, "
                f"{s['hits']} hits, {s['misses']} misses, "
                f"{s['evictions']} evictions"
            )

        if sub == "clear":
            cache.clear()
            return "Query cache cleared."

        if sub == "evict":
            n = cache.evict_expired()
            return f"Evicted {n} expired entries."

        return (
            "Usage: /query-cache <subcommand>\n"
            "  stats   — show cache statistics\n"
            "  clear   — clear entire cache\n"
            "  evict   — evict expired entries"
        )

    # ------------------------------------------------------------------
    # /query-explain
    # ------------------------------------------------------------------

    async def query_explain_handler(args: str) -> str:
        from lidco.query.parser import QueryParser, QueryParseError

        query_str = args.strip()
        if not query_str:
            return "Usage: /query-explain SELECT <fields> [WHERE ...] [ORDER BY ...] [LIMIT n]"

        parser = QueryParser()
        try:
            parsed = parser.parse(query_str)
        except QueryParseError as exc:
            return f"Parse error: {exc}"

        lines = ["Query plan:"]
        lines.append(f"  SELECT: {', '.join(parsed.select_fields)}")
        if parsed.where_clauses:
            for wc in parsed.where_clauses:
                lines.append(f"  WHERE: {wc.field} {wc.operator} {wc.value!r}")
        if parsed.order_by:
            for oc in parsed.order_by:
                direction = "ASC" if oc.ascending else "DESC"
                lines.append(f"  ORDER BY: {oc.field} {direction}")
        if parsed.limit is not None:
            lines.append(f"  LIMIT: {parsed.limit}")
        return "\n".join(lines)

    registry.register(SlashCommand("query", "Execute structured code query", query_handler))
    registry.register(SlashCommand("ast-query", "AST pattern query", ast_query_handler))
    registry.register(SlashCommand("query-cache", "Manage query cache", query_cache_handler))
    registry.register(SlashCommand("query-explain", "Explain query execution plan", query_explain_handler))
