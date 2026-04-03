"""Q245 CLI commands: /model-pool, /cascade, /ensemble, /benchmark."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q245 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /model-pool
    # ------------------------------------------------------------------

    async def model_pool_handler(args: str) -> str:
        from lidco.llm.model_pool import ModelPool

        pool = ModelPool()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /model-pool add <name>"
            ok = pool.add(rest)
            return f"Added {rest}." if ok else f"{rest} already in pool."

        if sub == "select":
            strategy = rest if rest else "round_robin"
            result = pool.select(strategy)
            return f"Selected: {result}" if result else "No healthy models available."

        if sub == "stats":
            s = pool.stats()
            return (
                f"Total: {s['total']}  Healthy: {s['healthy']}  "
                f"Unhealthy: {s['unhealthy']}  Requests: {s['total_requests']}"
            )

        return (
            "Usage: /model-pool <subcommand>\n"
            "  add <name>            — add a model\n"
            "  select [strategy]     — select a model (round_robin|least_loaded)\n"
            "  stats                 — show pool statistics"
        )

    # ------------------------------------------------------------------
    # /cascade
    # ------------------------------------------------------------------

    async def cascade_handler(args: str) -> str:
        from lidco.llm.cascade_router import CascadeRouter, CascadeRule

        router = CascadeRouter()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /cascade add <model> [timeout]"
            tokens = rest.split()
            model = tokens[0]
            timeout = float(tokens[1]) if len(tokens) > 1 else 30.0
            router.add_rule(CascadeRule(model=model, timeout=timeout))
            return f"Rule added: {model} (timeout={timeout}s)."

        if sub == "simulate":
            if not rest:
                return "Usage: /cascade simulate <request>"
            models = router.simulate(rest)
            if not models:
                return "No cascade rules configured."
            return "Cascade order: " + " -> ".join(models)

        if sub == "route":
            if not rest:
                return "Usage: /cascade route <request>"
            result = router.route(rest)
            status = "success" if result.success else "failed"
            return f"Routed to {result.model_used} ({status}, {len(result.attempts)} attempt(s))."

        return (
            "Usage: /cascade <subcommand>\n"
            "  add <model> [timeout] — add a cascade rule\n"
            "  simulate <request>    — show cascade order\n"
            "  route <request>       — route a request through cascade"
        )

    # ------------------------------------------------------------------
    # /ensemble
    # ------------------------------------------------------------------

    async def ensemble_handler(args: str) -> str:
        from lidco.llm.ensemble_runner import EnsembleRunner

        runner = EnsembleRunner()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "run":
            if not rest:
                return "Usage: /ensemble run <prompt>"
            result = runner.run(rest)
            lines = [f"Winner: {result.winner} (method={result.method})"]
            for r in result.responses:
                lines.append(f"  {r['model']}: {r['text']}")
            return "\n".join(lines)

        if sub == "add":
            if not rest:
                return "Usage: /ensemble add <model> [weight]"
            tokens = rest.split()
            name = tokens[0]
            weight = float(tokens[1]) if len(tokens) > 1 else 1.0
            runner.add_model(name, weight)
            return f"Added {name} (weight={weight})."

        if sub == "list":
            models = runner.list_models()
            if not models:
                return "No models in ensemble."
            return "\n".join(f"  {m['name']} (weight={m['weight']})" for m in models)

        return (
            "Usage: /ensemble <subcommand>\n"
            "  add <model> [weight] — add a model to ensemble\n"
            "  run <prompt>         — run ensemble on prompt\n"
            "  list                 — list ensemble models"
        )

    # ------------------------------------------------------------------
    # /benchmark
    # ------------------------------------------------------------------

    async def benchmark_handler(args: str) -> str:
        from lidco.llm.model_benchmark import BenchmarkResult, ModelBenchmark

        bench = ModelBenchmark()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "add":
            if not rest:
                return "Usage: /benchmark add <model> <latency> <quality> <cost>"
            tokens = rest.split()
            if len(tokens) < 4:
                return "Usage: /benchmark add <model> <latency> <quality> <cost>"
            bench.add_result(
                BenchmarkResult(
                    model=tokens[0],
                    latency_ms=float(tokens[1]),
                    quality_score=float(tokens[2]),
                    cost_estimate=float(tokens[3]),
                )
            )
            return f"Result added for {tokens[0]}."

        if sub == "ranking":
            return bench.summary()

        if sub == "compare":
            tokens = rest.split()
            if len(tokens) < 2:
                return "Usage: /benchmark compare <model_a> <model_b>"
            cmp = bench.compare(tokens[0], tokens[1])
            return (
                f"{cmp['model_a']} vs {cmp['model_b']}: "
                f"quality_diff={cmp['quality_diff']:.1f} "
                f"latency_diff={cmp['latency_diff_ms']:.0f}ms "
                f"winner={cmp['winner']}"
            )

        return (
            "Usage: /benchmark <subcommand>\n"
            "  add <model> <lat> <qual> <cost> — add result\n"
            "  ranking                          — show rankings\n"
            "  compare <a> <b>                  — compare two models"
        )

    registry.register(SlashCommand("model-pool", "Multi-model pool management", model_pool_handler))
    registry.register(SlashCommand("cascade", "Cascade routing across models", cascade_handler))
    registry.register(SlashCommand("ensemble", "Ensemble model execution", ensemble_handler))
    registry.register(SlashCommand("benchmark", "Model benchmarking", benchmark_handler))
