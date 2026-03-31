"""Q171 CLI commands: /bare-mode, /batch, /ci-report."""
from __future__ import annotations

import json

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q171 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /bare-mode [on|off|status]
    # ------------------------------------------------------------------

    async def bare_mode_handler(args: str) -> str:
        from lidco.modes.bare_mode import BareMode, BareConfig

        if "bare" not in _state:
            _state["bare"] = BareMode()

        bare: BareMode = _state["bare"]  # type: ignore[assignment]
        sub = args.strip().lower()

        if sub == "on":
            bare.activate(BareConfig())
            return "Bare mode activated. Hooks, plugins, skills, MCP skipped."
        if sub == "off":
            summary = bare.perf_summary()
            bare.deactivate()
            return f"Bare mode deactivated. Was active for {summary['elapsed']}s."
        if sub in ("status", ""):
            summary = bare.perf_summary()
            return json.dumps(summary, indent=2)
        return "Usage: /bare-mode [on|off|status]"

    # ------------------------------------------------------------------
    # /batch <file>
    # ------------------------------------------------------------------

    async def batch_handler(args: str) -> str:
        from lidco.api.batch_runner import BatchRunner
        from lidco.api.library import LidcoResult

        path = args.strip()
        if not path:
            return "Usage: /batch <file>"

        def _noop_exec(prompt: str) -> LidcoResult:
            return LidcoResult(success=True, output=f"[dry-run] {prompt}", tokens_used=0, duration=0.0)

        runner = BatchRunner(execute_fn=_noop_exec)
        try:
            prompts = runner.load_prompts(path)
        except FileNotFoundError:
            return f"File not found: {path}"
        except Exception as exc:
            return f"Error loading prompts: {exc}"

        if not prompts:
            return "No prompts found in file."

        jobs = runner.run_all(prompts)
        summary = runner.summary(jobs)
        return json.dumps(summary, indent=2)

    # ------------------------------------------------------------------
    # /ci-report
    # ------------------------------------------------------------------

    async def ci_report_handler(args: str) -> str:
        from lidco.api.ci_helpers import detect_ci, format_ci_output
        from lidco.api.library import LidcoResult

        env = detect_ci()
        # Build a placeholder result summarising the session
        result = LidcoResult(
            success=True,
            output="Session report",
            tokens_used=0,
            duration=0.0,
        )
        return format_ci_output(result, env)

    # ------------------------------------------------------------------

    registry.register(SlashCommand("bare-mode", "Toggle bare mode (skip hooks/plugins/skills/mcp)", bare_mode_handler))
    registry.register(SlashCommand("batch", "Run batch prompts from file", batch_handler))
    registry.register(SlashCommand("ci-report", "Generate CI-formatted report", ci_report_handler))
