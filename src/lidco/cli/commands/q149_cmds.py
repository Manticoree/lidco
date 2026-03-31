"""Q149 CLI commands: /complete."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q149 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def complete_handler(args: str) -> str:
        from lidco.completion.trie import CompletionTrie
        from lidco.completion.context_completer import ContextCompleter
        from lidco.completion.ranker import CompletionRanker
        from lidco.completion.cache import CompletionCache

        if "trie" not in _state:
            _state["trie"] = CompletionTrie()
        if "completer" not in _state:
            _state["completer"] = ContextCompleter()
        if "ranker" not in _state:
            _state["ranker"] = CompletionRanker()
        if "cache" not in _state:
            _state["cache"] = CompletionCache()

        trie: CompletionTrie = _state["trie"]  # type: ignore[assignment]
        completer: ContextCompleter = _state["completer"]  # type: ignore[assignment]
        ranker: CompletionRanker = _state["ranker"]  # type: ignore[assignment]
        cache: CompletionCache = _state["cache"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "prefix":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "insert":
                word = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                if not word:
                    return "Usage: /complete prefix insert <word>"
                trie.insert(word)
                return f"Inserted '{word}' into trie."
            if action == "search":
                prefix = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                if not prefix:
                    return "Usage: /complete prefix search <prefix>"
                matches = trie.autocomplete(prefix)
                return json.dumps(matches)
            if action == "delete":
                word = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                if not word:
                    return "Usage: /complete prefix delete <word>"
                ok = trie.delete(word)
                return f"Deleted '{word}'." if ok else f"'{word}' not found."
            if action == "words":
                return json.dumps(trie.words())
            if action == "size":
                return f"Trie size: {trie.size}"
            return "Usage: /complete prefix insert|search|delete|words|size"

        if sub == "context":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "add":
                payload = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                try:
                    data = json.loads(payload)
                    category = data.get("category", "")
                    items = data.get("items", [])
                    descs = data.get("descriptions", {})
                    completer.add_source(category, items, descs)
                    return f"Added source '{category}' with {len(items)} items."
                except (json.JSONDecodeError, AttributeError):
                    return "Usage: /complete context add {\"category\":\"...\",\"items\":[...]}"
            if action == "complete":
                text = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                items = completer.complete(text)
                return json.dumps([{"text": i.text, "category": i.category, "score": i.score} for i in items])
            if action == "sources":
                return json.dumps(completer.sources)
            if action == "remove":
                cat = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                completer.remove_source(cat)
                return f"Removed source '{cat}'."
            return "Usage: /complete context add|complete|sources|remove"

        if sub == "rank":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "items":
                payload = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                try:
                    data = json.loads(payload)
                    items = data.get("items", [])
                    query = data.get("query", "")
                    counts = data.get("usage_counts")
                    rec = data.get("recency")
                    ranked = ranker.rank(items, query, usage_counts=counts, recency=rec)
                    return json.dumps([{"text": r.text, "score": r.score} for r in ranked])
                except (json.JSONDecodeError, AttributeError):
                    return "Usage: /complete rank items {\"items\":[...],\"query\":\"...\"}"
            if action == "top":
                payload = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                try:
                    data = json.loads(payload)
                    items = data.get("items", [])
                    query = data.get("query", "")
                    n = data.get("n", 5)
                    top = ranker.top(items, query, n=n)
                    return json.dumps([{"text": r.text, "score": r.score} for r in top])
                except (json.JSONDecodeError, AttributeError):
                    return "Usage: /complete rank top {\"items\":[...],\"query\":\"...\",\"n\":5}"
            return "Usage: /complete rank items|top"

        if sub == "cache":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "stats":
                return json.dumps(cache.stats())
            if action == "put":
                payload = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                try:
                    data = json.loads(payload)
                    prefix = data.get("prefix", "")
                    results = data.get("results", [])
                    cache.put(prefix, results)
                    return f"Cached {len(results)} results for '{prefix}'."
                except (json.JSONDecodeError, AttributeError):
                    return "Usage: /complete cache put {\"prefix\":\"...\",\"results\":[...]}"
            if action == "get":
                prefix = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                result = cache.get(prefix)
                if result is None:
                    return "Cache miss."
                return json.dumps(result)
            if action == "invalidate":
                prefix = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                if prefix:
                    cache.invalidate(prefix)
                    return f"Invalidated '{prefix}'."
                cache.invalidate()
                return "Cache cleared."
            if action == "evict":
                count = cache.evict_expired()
                return f"Evicted {count} expired entries."
            return "Usage: /complete cache stats|put|get|invalidate|evict"

        return "Usage: /complete prefix|context|rank|cache"

    registry.register(SlashCommand("complete", "Smart completion & autocomplete", complete_handler))
