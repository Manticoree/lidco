"""Q138 CLI commands: /resilience."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q138 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def resilience_handler(args: str) -> str:
        from lidco.resilience.retry_executor import RetryExecutor, RetryConfig
        from lidco.resilience.fallback_chain import FallbackChain
        from lidco.resilience.partial_collector import PartialCollector
        from lidco.resilience.error_boundary import ErrorBoundary

        if "retry" not in _state:
            _state["retry"] = RetryExecutor()
        if "fallback" not in _state:
            _state["fallback"] = FallbackChain()
        if "collector" not in _state:
            _state["collector"] = PartialCollector()
        if "boundary" not in _state:
            _state["boundary"] = ErrorBoundary()

        executor: RetryExecutor = _state["retry"]  # type: ignore[assignment]
        chain: FallbackChain = _state["fallback"]  # type: ignore[assignment]
        collector: PartialCollector = _state["collector"]  # type: ignore[assignment]
        boundary: ErrorBoundary = _state["boundary"]  # type: ignore[assignment]

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "retry":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "stats":
                return json.dumps(executor.stats, indent=2)
            if action == "reset":
                executor.reset_stats()
                return "Retry stats reset."
            if action == "test":
                counter = {"n": 0}

                def flaky():
                    counter["n"] += 1
                    if counter["n"] < 3:
                        raise RuntimeError("flaky")
                    return "ok"

                result = executor.execute(flaky)
                return f"success={result.success}, attempts={result.attempts}, result={result.result!r}"
            if action == "config":
                cfg = executor._config
                return (
                    f"max_retries={cfg.max_retries}, base_delay={cfg.base_delay}, "
                    f"max_delay={cfg.max_delay}, backoff_factor={cfg.backoff_factor}"
                )
            return json.dumps(executor.stats, indent=2)

        if sub == "fallback":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "count":
                return f"Fallback chain length: {len(chain)}"
            if action == "clear":
                chain.clear()
                return "Fallback chain cleared."
            if action == "test":
                chain.clear()
                chain.add("fail", lambda: (_ for _ in ()).throw(RuntimeError("nope")))
                chain.add("ok", lambda: "fallback-ok")
                result = chain.execute()
                return f"value={result.value!r}, source={result.source}, fallback_used={result.fallback_used}"
            return f"Fallback chain length: {len(chain)}"

        if sub == "collect":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "test":
                tasks = {
                    "ok": lambda: 42,
                    "fail": lambda: (_ for _ in ()).throw(ValueError("boom")),
                }
                result = collector.collect(tasks)
                return (
                    f"succeeded={result.succeeded}, failed={result.failed}, "
                    f"partial={result.partial}, rate={collector.success_rate:.2f}"
                )
            if action == "rate":
                return f"Success rate: {collector.success_rate:.2f}"
            return f"Success rate: {collector.success_rate:.2f}"

        if sub == "boundary":
            sub_parts = rest.split(maxsplit=1)
            action = sub_parts[0].lower() if sub_parts else ""
            if action == "test":
                boundary.catch(lambda: (_ for _ in ()).throw(RuntimeError("test-err")))
                return f"Errors caught: {boundary.error_count}"
            if action == "log":
                entries = boundary.log
                if not entries:
                    return "No errors in log."
                lines = [f"Error log ({len(entries)} entries):"]
                for e in entries[-5:]:
                    lines.append(f"  [{e['error_type']}] {e['message']}")
                return "\n".join(lines)
            if action == "clear":
                boundary.clear_log()
                return "Error log cleared."
            if action == "count":
                return f"Errors caught: {boundary.error_count}"
            return f"Errors caught: {boundary.error_count}"

        return (
            "Usage: /resilience <sub>\n"
            "  retry stats|reset|test|config    -- retry executor\n"
            "  fallback count|clear|test        -- fallback chain\n"
            "  collect test|rate                 -- partial collector\n"
            "  boundary test|log|clear|count     -- error boundary"
        )

    registry.register(SlashCommand("resilience", "Error recovery & graceful degradation (Q138)", resilience_handler))
