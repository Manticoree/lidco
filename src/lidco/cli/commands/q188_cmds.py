"""Q188 CLI commands: /loop-run, /loop-status, /loop-cancel, /loop-history."""

from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:  # noqa: C901
    """Register Q188 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /loop-run
    # ------------------------------------------------------------------

    async def loop_run_handler(args: str) -> str:
        from lidco.autonomous.loop_config import LoopConfig
        from lidco.autonomous.loop_runner import AutonomousLoopRunner

        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: /loop-run <prompt> [--max N] [--promise TEXT]"

        prompt = args.strip()
        max_iter = 10
        promise = None

        # Simple flag parsing
        tokens = args.strip().split()
        clean_tokens: list[str] = []
        i = 0
        while i < len(tokens):
            if tokens[i] == "--max" and i + 1 < len(tokens):
                try:
                    max_iter = int(tokens[i + 1])
                except ValueError:
                    pass
                i += 2
                continue
            if tokens[i] == "--promise" and i + 1 < len(tokens):
                promise = tokens[i + 1]
                i += 2
                continue
            clean_tokens.append(tokens[i])
            i += 1

        prompt = " ".join(clean_tokens) if clean_tokens else prompt

        config = LoopConfig(
            prompt=prompt,
            max_iterations=max_iter,
            completion_promise=promise,
            cooldown_s=0.0,
        )
        runner = AutonomousLoopRunner(config)
        _state["runner"] = runner

        def echo_executor(p: str, iteration: int) -> str:
            return f"[iter {iteration}] Executed: {p}"

        result = runner.run(echo_executor)
        _state["last_result"] = result

        lines = [
            f"Loop finished: {result.state.value}",
            f"Iterations: {len(result.iterations)}",
            f"Duration: {result.total_duration_ms}ms",
            f"Completed naturally: {result.completed_naturally}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # /loop-status
    # ------------------------------------------------------------------

    async def loop_status_handler(args: str) -> str:
        from lidco.autonomous.loop_runner import AutonomousLoopRunner

        runner = _state.get("runner")
        if runner is None:
            return "No loop runner active. Use /loop-run first."
        if not isinstance(runner, AutonomousLoopRunner):
            return "No loop runner active."
        return f"Loop state: {runner.state.value}"

    # ------------------------------------------------------------------
    # /loop-cancel
    # ------------------------------------------------------------------

    async def loop_cancel_handler(args: str) -> str:
        from lidco.autonomous.loop_runner import AutonomousLoopRunner

        runner = _state.get("runner")
        if runner is None:
            return "No loop runner active."
        if not isinstance(runner, AutonomousLoopRunner):
            return "No loop runner active."
        runner.cancel()
        return "Loop cancellation requested."

    # ------------------------------------------------------------------
    # /loop-history
    # ------------------------------------------------------------------

    async def loop_history_handler(args: str) -> str:
        from lidco.autonomous.loop_runner import LoopResult

        last = _state.get("last_result")
        if last is None:
            return "No loop history available. Run /loop-run first."
        if not isinstance(last, LoopResult):
            return "No loop history available."

        lines = [f"Loop history ({len(last.iterations)} iterations):"]
        for it in last.iterations:
            flag = " [CLAIMED COMPLETE]" if it.claimed_complete else ""
            lines.append(f"  #{it.iteration} ({it.duration_ms}ms){flag}: {it.output[:80]}")
        return "\n".join(lines)

    # -- register ---------------------------------------------------------

    registry.register(SlashCommand("loop-run", "Run an autonomous loop with completion promises", loop_run_handler))
    registry.register(SlashCommand("loop-status", "Show autonomous loop status", loop_status_handler))
    registry.register(SlashCommand("loop-cancel", "Cancel a running autonomous loop", loop_cancel_handler))
    registry.register(SlashCommand("loop-history", "Show iteration history of last loop run", loop_history_handler))
