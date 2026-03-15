"""Headless (non-interactive) execution mode — Task 261.

Runs a single task through the LIDCO agent pipeline without a REPL,
suitable for CI/CD, pre-commit hooks, and shell pipelines.

Usage::

    lidco exec "fix all failing tests"
    lidco exec --json "add docstrings to src/api/"
    lidco exec --max-turns 20 --permission-mode bypass "refactor utils.py"
    echo "task" | lidco exec
    lidco exec --agent coder --model openai/gpt-4o "explain auth.py"
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

from lidco.cli.exit_codes import (
    CONFIG_ERROR,
    INPUT_ERROR,
    PERMISSION_DENIED,
    SUCCESS,
    TASK_FAILED,
    TIMEOUT,
)
from lidco.cli.json_reporter import ExecResult, ExecStats
from lidco.core.config import load_config
from lidco.core.session import Session

logger = logging.getLogger(__name__)

_PERMISSION_DENIED_MARKER = "__PERMISSION_DENIED__"
_TIMEOUT_MARKER = "__TIMEOUT__"


async def run_exec(flags: "ExecFlags") -> int:
    """Run headless exec mode. Returns exit code."""
    # ── Resolve task ──────────────────────────────────────────────────────────
    task = flags.task
    if not task:
        if not sys.stdin.isatty():
            task = sys.stdin.read().strip()
        if not task:
            _emit(flags, "error: no task provided. Pass it as an argument or via stdin.\n")
            _emit(flags, "Usage: lidco exec <task>\n")
            _emit(flags, "       echo '<task>' | lidco exec\n")
            return INPUT_ERROR

    # ── Init session ──────────────────────────────────────────────────────────
    try:
        project_dir = Path(flags.project_dir) if flags.project_dir else Path.cwd()
        config = load_config(project_dir)
    except Exception as exc:
        _emit(flags, f"error: failed to load config: {exc}\n")
        return CONFIG_ERROR

    # Apply flag overrides
    if flags.model:
        config.llm.default_model = flags.model
    if flags.permission_mode:
        config.permissions.mode = flags.permission_mode
    config.agents.auto_plan = not flags.no_plan
    config.agents.auto_review = not flags.no_review
    config.llm.streaming = False  # headless: no streaming output

    try:
        session = Session(config=config, project_dir=project_dir)
    except Exception as exc:
        _emit(flags, f"error: failed to init session: {exc}\n")
        return CONFIG_ERROR

    # ── Wire stats collector ──────────────────────────────────────────────────
    stats = ExecStats()
    session_id = uuid.uuid4().hex[:12]

    orch = session.orchestrator
    orch.set_token_callback(stats.on_tokens)
    orch.set_tool_event_callback(stats.on_tool_event)

    # Permission denied tracking
    permission_denied = [False]

    def _permission_check(tool_name: str, params: dict) -> bool:
        # In bypass mode everything is allowed; otherwise deny and signal
        mode = config.permissions.mode
        if mode == "bypass":
            return True
        # Let the engine decide — but intercept denials
        from lidco.core.permission_engine import PermissionEngine
        engine = session.permission_engine
        decision = engine.check(tool_name, params)
        from lidco.core.permission_engine import Decision
        if decision == Decision.DENY:
            permission_denied[0] = True
            return False
        # AUTO and ASK both proceed (no interactive prompt in headless)
        return True

    orch.set_permission_handler(_permission_check)

    # Max-turns / timeout
    turn_count = [0]
    max_turns = flags.max_turns

    def _continue_check(iteration: int, max_iter: int) -> bool:
        if max_turns and iteration >= max_turns:
            return False
        return True

    orch.set_continue_handler(_continue_check)

    # Collect plain-text output chunks (used in non-JSON mode and JSON output field)
    output_chunks: list[str] = []

    def _on_status(status: str) -> None:
        if not flags.json and not flags.quiet:
            _emit(flags, f"[{status}]\n")

    orch.set_status_callback(_on_status)

    # ── Execute ───────────────────────────────────────────────────────────────
    exit_code = SUCCESS
    response = ""
    error_str: str | None = None

    try:
        context = session.get_full_context()
        agent_response = await orch.handle(
            task,
            agent_name=flags.agent,
            context=context,
        )
        # AgentResponse has .content; plain str also accepted
        if hasattr(agent_response, "content"):
            response = agent_response.content or ""
            # Update token stats from AgentResponse if available
            usage = getattr(agent_response, "token_usage", None)
            if usage is not None:
                stats.prompt_tokens = getattr(usage, "prompt_tokens", 0)
                stats.completion_tokens = getattr(usage, "completion_tokens", 0)
                if not stats.total_tokens:
                    stats.total_tokens = getattr(usage, "total_tokens", 0)
        else:
            response = str(agent_response) if agent_response else ""

    except asyncio.CancelledError:
        exit_code = TIMEOUT
        error_str = "Execution cancelled (SIGTERM)"

    except Exception as exc:
        exit_code = TASK_FAILED
        error_str = str(exc)
        logger.debug("exec error", exc_info=True)

    else:
        if permission_denied[0]:
            exit_code = PERMISSION_DENIED
            error_str = "Tool call blocked by permission policy"
        elif not response.strip() and error_str is None:
            exit_code = TASK_FAILED
            error_str = "Agent returned empty response"

    # ── Output ────────────────────────────────────────────────────────────────
    duration = stats.elapsed()
    status_str = {
        SUCCESS: "success",
        TASK_FAILED: "failed",
        PERMISSION_DENIED: "permission_denied",
        TIMEOUT: "timeout",
        CONFIG_ERROR: "config_error",
        INPUT_ERROR: "input_error",
    }.get(exit_code, "failed")

    result = ExecResult(
        session_id=session_id,
        task=task,
        status=status_str,
        exit_code=exit_code,
        duration_s=round(duration, 3),
        cost_usd=round(stats.cost_usd, 6),
        prompt_tokens=stats.prompt_tokens,
        completion_tokens=stats.completion_tokens,
        total_tokens=stats.total_tokens,
        tool_calls=stats.tool_calls,
        changes=stats.changes,
        output=response,
        error=error_str,
    )

    if flags.json:
        result.print_json()
    else:
        if response and not flags.quiet:
            print(response, flush=True)
        if error_str and not flags.quiet:
            print(f"\nerror: {error_str}", file=sys.stderr, flush=True)

    # ── Cleanup ───────────────────────────────────────────────────────────────
    try:
        session._config_reloader.stop()
    except Exception:
        pass

    return exit_code


def _emit(flags: "ExecFlags", text: str) -> None:
    """Write text to stderr (to keep stdout clean for JSON output)."""
    if not flags.quiet:
        sys.stderr.write(text)
        sys.stderr.flush()


# ── Pre-commit hook mode (Task 265) ──────────────────────────────────────────

async def run_precommit(flags: "PrecommitFlags") -> int:
    """Run a pre-commit security/review check on staged files."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=10,
        )
        staged_files = [f for f in result.stdout.strip().splitlines() if f]
    except Exception as exc:
        sys.stderr.write(f"error: could not get staged files: {exc}\n")
        return CONFIG_ERROR

    if not staged_files:
        if not flags.quiet:
            print("No staged files — nothing to check.")
        return SUCCESS

    files_str = "\n".join(f"  - {f}" for f in staged_files[:20])
    task = (
        f"Perform a security and code quality review of these staged files:\n"
        f"{files_str}\n\n"
        "Check for: security vulnerabilities, obvious bugs, missing input validation.\n"
        "If critical issues are found, describe them clearly. "
        "Output only findings — skip files with no issues."
    )

    exec_flags = ExecFlags(
        task=task,
        agent=flags.agent or "security",
        permission_mode="plan",
        no_plan=True,
        no_review=True,
        json=flags.json,
        quiet=flags.quiet,
        max_turns=flags.max_turns or 10,
        model=flags.model,
        project_dir=flags.project_dir,
    )
    return await run_exec(exec_flags)


# ── Flag dataclasses ──────────────────────────────────────────────────────────

from dataclasses import dataclass, field as dc_field


@dataclass
class ExecFlags:
    """Parsed flags for `lidco exec`."""
    task: str = ""
    agent: str | None = None
    model: str | None = None
    permission_mode: str | None = None
    no_plan: bool = False
    no_review: bool = False
    json: bool = False
    quiet: bool = False
    max_turns: int | None = None
    project_dir: str | None = None


@dataclass
class PrecommitFlags:
    """Parsed flags for `lidco precommit`."""
    agent: str | None = None
    model: str | None = None
    json: bool = False
    quiet: bool = False
    max_turns: int | None = None
    project_dir: str | None = None
