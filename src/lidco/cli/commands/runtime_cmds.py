"""Commands: runtime, execution and integrations."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def register(registry: Any) -> None:
    """Register runtime, execution and integrations commands."""
    from lidco.cli.commands.registry import SlashCommand

    # ── Q59 — Code Execution & Runtime (Tasks 396–402) ───────────────────

    # Task 396: /run [python|bash|js] <code> — execute code snippet
    async def repl_run_handler(arg: str = "", **_: Any) -> str:
        """/run [python|bash|js] <code|```block>  — execute a code snippet."""
        import re as _re
        from lidco.tools.code_runner import CodeRunner, RunResult

        if not arg.strip():
            return (
                "**Usage:** `/run [python|bash|js] <code>`\n\n"
                "Executes a code snippet and shows output.\n\n"
                "**Examples:**\n"
                "- `/run python print('hello')`\n"
                "- `/run bash ls -la`\n"
                "- `/run js console.log(1+1)`"
            )

        # Detect language from fenced code block
        block_match = _re.match(r"```(\w+)?\n?(.*?)```", arg.strip(), _re.DOTALL)
        if block_match:
            lang_hint = (block_match.group(1) or "").lower()
            code = block_match.group(2)
        else:
            # Split language token from rest
            parts_arg = arg.strip().split(None, 1)
            if len(parts_arg) >= 2 and parts_arg[0].lower() in ("python", "bash", "js", "javascript"):
                lang_hint = parts_arg[0].lower()
                code = parts_arg[1]
            else:
                lang_hint = "python"
                code = arg.strip()

        if lang_hint == "javascript":
            lang_hint = "js"
        if lang_hint not in ("python", "bash", "js"):
            lang_hint = "python"

        runner = CodeRunner()
        if lang_hint == "python":
            result: RunResult = runner.run_python(code)
        elif lang_hint == "bash":
            result = runner.run_bash(code)
        else:
            result = runner.run_js(code)

        rc_label = "OK" if result.returncode == 0 else f"exit {result.returncode}"
        header = f"**[{lang_hint}]** `{rc_label}` — {result.elapsed:.2f}s\n\n"
        parts_out: list[str] = []
        if result.stdout.strip():
            parts_out.append(f"```\n{result.stdout.rstrip()}\n```")
        if result.stderr.strip():
            parts_out.append(f"**stderr:**\n```\n{result.stderr.rstrip()}\n```")
        if not parts_out:
            parts_out.append("_(no output)_")
        return header + "\n".join(parts_out)

    registry.register(SlashCommand("run", "Execute code snippet in REPL [python|bash|js]", repl_run_handler))

    # Task 397: /debug run <file> [args...]  — extend existing /debug handler
    _orig_debug_cmd = registry.get("debug")

    async def debug_extended_handler(arg: str = "", **kw: Any) -> str:
        """/debug — extends original debug with `run <file>` subcommand."""
        import asyncio as _asyncio
        import subprocess as _subprocess

        if arg.startswith("run ") or arg == "run":
            rest = arg[4:].strip()
            if not rest:
                return "**Usage:** `/debug run <file.py> [args...]`"

            file_parts = rest.split()
            file_path = file_parts[0]
            extra_args = file_parts[1:]

            # Syntax check first
            try:
                syntax_proc = _subprocess.run(
                    ["python", "-m", "py_compile", file_path],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except Exception as exc:
                return f"Syntax check failed: {exc}"

            if syntax_proc.returncode != 0:
                err = syntax_proc.stderr or syntax_proc.stdout
                return f"**Syntax error in `{file_path}`:**\n\n```\n{err.strip()}\n```"

            # Run the file
            cmd_dbg = ["python", file_path] + extra_args
            try:
                run_proc = await _asyncio.create_subprocess_exec(
                    *cmd_dbg,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.PIPE,
                )
                stdout_b, stderr_b = await _asyncio.wait_for(run_proc.communicate(), timeout=60)
            except _asyncio.TimeoutError:
                return "Execution timed out after 60s."
            except Exception as exc:
                return f"Execution error: {exc}"

            stdout_dbg = stdout_b.decode("utf-8", errors="replace")
            stderr_dbg = stderr_b.decode("utf-8", errors="replace")
            rc_dbg = run_proc.returncode or 0

            dbg_lines: list[str] = []
            dbg_lines.append(f"**`python {' '.join([file_path] + extra_args)}`** — exit {rc_dbg}")
            if stdout_dbg.strip():
                dbg_lines.append(f"\n**stdout:**\n```\n{stdout_dbg.strip()}\n```")
            if stderr_dbg.strip():
                dbg_lines.append(f"\n**stderr:**\n```\n{stderr_dbg.strip()}\n```")

            if rc_dbg != 0 and registry._session:
                session = registry._session
                analysis_prompt = (
                    f"The script `{file_path}` exited with code {rc_dbg}.\n\n"
                    f"stderr:\n```\n{stderr_dbg.strip()}\n```\n\n"
                    "Briefly explain what went wrong and suggest a fix."
                )
                try:
                    resp = await session.orchestrator.handle(analysis_prompt, agent_name="debugger")
                    suggestion = resp.content if hasattr(resp, "content") else str(resp)
                    dbg_lines.append(f"\n**AI suggestion:**\n{suggestion}")
                except Exception:
                    pass

            return "\n".join(dbg_lines)

        # Delegate to original handler
        if _orig_debug_cmd:
            return await _orig_debug_cmd.handler(arg=arg, **kw)
        return "debug handler not found"

    registry.register(SlashCommand("debug", "Toggle debug mode / run file: /debug [on|off|run <file>|kb|stats|preset]", debug_extended_handler))

    # Task 398: /test [path] [-k filter] [--watch]
    async def test_handler(arg: str = "", **_: Any) -> str:
        """/test [path] [-k filter] [--watch] — run pytest from REPL."""
        import asyncio as _asyncio
        import re as _re
        import time as _time

        if not arg.strip():
            return (
                "**Usage:** `/test [path] [-k filter] [--watch]`\n\n"
                "Runs pytest and shows results.\n\n"
                "**Examples:**\n"
                "- `/test tests/unit/`\n"
                "- `/test tests/ -k test_auth`\n"
                "- `/test --watch`"
            )

        watch_mode = "--watch" in arg
        arg_clean = arg.replace("--watch", "").strip()

        cmd_parts = ["python", "-m", "pytest"]
        if arg_clean:
            cmd_parts += arg_clean.split()
        cmd_parts += ["-v", "--tb=short", "-q"]

        project_dir = None
        if registry._session:
            project_dir = str(registry._session.project_dir)

        async def _run_once() -> str:
            try:
                proc = await _asyncio.create_subprocess_exec(
                    *cmd_parts,
                    stdout=_asyncio.subprocess.PIPE,
                    stderr=_asyncio.subprocess.STDOUT,
                    cwd=project_dir,
                )
                output_b, _ = await _asyncio.wait_for(proc.communicate(), timeout=300)
            except _asyncio.TimeoutError:
                return "Tests timed out after 300s."
            except Exception as exc:
                return f"Test run failed: {exc}"

            output_t = output_b.decode("utf-8", errors="replace")
            rc_t = proc.returncode or 0

            passed = 0
            failed = 0
            errors_count = 0
            summary_match = _re.search(r"(\d+) passed", output_t)
            if summary_match:
                passed = int(summary_match.group(1))
            fail_match = _re.search(r"(\d+) failed", output_t)
            if fail_match:
                failed = int(fail_match.group(1))
            err_match = _re.search(r"(\d+) error", output_t)
            if err_match:
                errors_count = int(err_match.group(1))

            status_t = "PASSED" if rc_t == 0 else "FAILED"
            header_t = f"**pytest {status_t}** — {passed} passed, {failed} failed, {errors_count} errors\n\n"

            lines_all = output_t.splitlines()
            display_t = "\n".join(lines_all[-80:]) if len(lines_all) > 80 else output_t
            result_str = header_t + f"```\n{display_t}\n```"

            if rc_t != 0 and registry._session:
                try:
                    session = registry._session
                    prompt_t = (
                        f"pytest run failed:\n\n```\n{output_t[-2000:]}\n```\n\n"
                        "Briefly summarize the failures and suggest fixes."
                    )
                    resp_t = await session.orchestrator.handle(prompt_t, agent_name="tester")
                    suggestion_t = resp_t.content if hasattr(resp_t, "content") else str(resp_t)
                    result_str += f"\n\n**AI analysis:**\n{suggestion_t}"
                except Exception:
                    pass

            return result_str

        if not watch_mode:
            return await _run_once()

        # Watch mode: re-run on file changes (poll 3s, max 60s)
        results_list: list[str] = [await _run_once()]
        deadline = _time.monotonic() + 60

        def _snapshot_files() -> dict[str, float]:
            snap: dict[str, float] = {}
            base = Path(project_dir) if project_dir else Path(".")
            try:
                for p in base.rglob("*.py"):
                    try:
                        snap[str(p)] = p.stat().st_mtime
                    except OSError:
                        pass
            except Exception:
                pass
            return snap

        baseline_snap = _snapshot_files()
        while _time.monotonic() < deadline:
            await _asyncio.sleep(3)
            current_snap = _snapshot_files()
            if current_snap != baseline_snap:
                baseline_snap = current_snap
                results_list.append(await _run_once())

        return f"**Watch mode (ran {len(results_list)} time(s)):**\n\n" + "\n\n---\n\n".join(results_list[-3:])

    registry.register(SlashCommand("test", "Run pytest from REPL: /test [path] [-k filter] [--watch]", test_handler))

    # Task 400: /venv — virtual environment manager
    async def venv_handler(arg: str = "", **_: Any) -> str:
        """/venv [create <name>|list|delete <name>|activate <name>]"""
        from lidco.tools.venv_manager import VenvManager

        base_dir = Path(".lidco") / "venvs"
        if registry._session:
            base_dir = Path(str(registry._session.project_dir)) / ".lidco" / "venvs"

        mgr = VenvManager()
        parts_v = arg.strip().split(None, 1)
        sub_v = parts_v[0].lower() if parts_v else "list"
        rest_v = parts_v[1].strip() if len(parts_v) > 1 else ""

        if sub_v == "create":
            if not rest_v:
                return "**Usage:** `/venv create <name>`"
            try:
                info = mgr.create(rest_v, base_dir)
                activate = mgr.get_activate_path(info)
                return (
                    f"**Venv `{rest_v}` created** at `{info.path}`\n\n"
                    f"Python: `{info.python_version}` | Size: `{info.size_mb} MB`\n\n"
                    f"Activate with: `source {activate}`"
                )
            except Exception as exc:
                return f"Failed to create venv: {exc}"

        elif sub_v == "list":
            venvs = mgr.list_venvs(base_dir)
            if not venvs:
                return f"No virtual environments found in `{base_dir}`."
            lines_v = ["**Virtual environments:**\n"]
            for v in venvs:
                lines_v.append(f"- `{v.name}` — Python {v.python_version}, {v.size_mb} MB")
            return "\n".join(lines_v)

        elif sub_v == "delete":
            if not rest_v:
                return "**Usage:** `/venv delete <name>`"
            if mgr.delete(rest_v, base_dir):
                return f"Venv `{rest_v}` deleted."
            return f"Venv `{rest_v}` not found."

        elif sub_v == "activate":
            if not rest_v:
                return "**Usage:** `/venv activate <name>`"
            venvs = mgr.list_venvs(base_dir)
            target_v = next((v for v in venvs if v.name == rest_v), None)
            if not target_v:
                return f"Venv `{rest_v}` not found. Run `/venv list` to see available venvs."
            activate = mgr.get_activate_path(target_v)
            return (
                f"**Activation hint for `{rest_v}`:**\n\n"
                f"```bash\nsource {activate}\n```"
            )

        return (
            "**Usage:** `/venv [create <name>|list|delete <name>|activate <name>]`\n\n"
            f"Venvs stored in `{base_dir}`"
        )

    registry.register(SlashCommand("venv", "Manage Python virtual environments", venv_handler))

    # Task 401: /install <package> [--explain] [--no-confirm]
    async def install_handler(arg: str = "", **_: Any) -> str:
        """/install <package> [--explain] [--no-confirm]"""
        import asyncio as _asyncio
        import subprocess as _subprocess

        if not arg.strip():
            return (
                "**Usage:** `/install <package> [--explain] [--no-confirm]`\n\n"
                "Installs a Python package with optional AI guidance.\n\n"
                "**Examples:**\n"
                "- `/install requests`\n"
                "- `/install numpy --explain`\n"
                "- `/install pytest --no-confirm`"
            )

        explain = "--explain" in arg
        no_confirm = "--no-confirm" in arg
        pkg_tokens = arg.replace("--explain", "").replace("--no-confirm", "").strip().split()
        if not pkg_tokens:
            return "Please specify a package name."
        package = pkg_tokens[0]

        result_lines_i: list[str] = []

        # Check if already in requirements
        already_listed = False
        for req_file in ("requirements.txt", "pyproject.toml"):
            req_path = Path(req_file)
            if registry._session:
                req_path = Path(str(registry._session.project_dir)) / req_file
            if req_path.exists():
                content = req_path.read_text()
                if package.lower() in content.lower():
                    already_listed = True
                    result_lines_i.append(f"**Note:** `{package}` is already listed in `{req_file}`.")
                    break

        # AI explanation
        if explain and registry._session:
            try:
                session = registry._session
                prompt_i = (
                    f"The user wants to install Python package `{package}`. "
                    "Briefly explain: 1) what it's used for, 2) any notable alternatives, "
                    "3) any known security or compatibility concerns (2-3 sentences total)."
                )
                resp_i = await session.orchestrator.handle(prompt_i, agent_name="architect")
                explanation = resp_i.content if hasattr(resp_i, "content") else str(resp_i)
                result_lines_i.append(f"**About `{package}`:**\n{explanation}")
            except Exception:
                pass

        # Confirm unless --no-confirm
        if not no_confirm:
            result_lines_i.append(
                f"\nWill run: `pip install {package}`\n\n"
                "_Pass `--no-confirm` to skip this prompt, or confirm by running:_\n"
                f"`/install {package} --no-confirm`"
            )
            return "\n".join(result_lines_i)

        # Run pip install
        result_lines_i.append(f"**Installing `{package}`...**")
        try:
            proc_i = await _asyncio.create_subprocess_exec(
                "pip", "install", package,
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.STDOUT,
            )
            output_i_b, _ = await _asyncio.wait_for(proc_i.communicate(), timeout=120)
            output_i = output_i_b.decode("utf-8", errors="replace")
            rc_i = proc_i.returncode or 0
        except _asyncio.TimeoutError:
            return "pip install timed out after 120s."
        except Exception as exc:
            return f"pip install failed: {exc}"

        status_i = "succeeded" if rc_i == 0 else f"failed (exit {rc_i})"
        result_lines_i.append(f"**pip install {status_i}:**\n```\n{output_i[-1000:].strip()}\n```")

        if rc_i == 0 and not already_listed:
            result_lines_i.append(
                f"\n_Run `/install {package} --no-confirm` added. "
                "Consider adding it manually to `requirements.txt`._"
            )

        return "\n".join(result_lines_i)

    registry.register(SlashCommand("install", "Install Python package with AI guidance", install_handler))

    # Task 402: /diff-output <command>
    registry._output_differ_baseline: dict[str, str] = {}  # type: ignore[attr-defined]

    async def diff_output_handler(arg: str = "", **_: Any) -> str:
        """/diff-output <command> — capture output and diff before/after."""
        from lidco.tools.output_differ import OutputDiffer

        if not arg.strip():
            return (
                "**Usage:** `/diff-output <command>`\n\n"
                "First call captures the **before** baseline.\n"
                "Second call runs the command again and shows the diff.\n\n"
                "**Example:**\n"
                "- `/diff-output python --version`"
            )

        command_d = arg.strip()
        differ = OutputDiffer()

        if command_d not in registry._output_differ_baseline:
            baseline_d = differ.capture(command_d)
            registry._output_differ_baseline[command_d] = baseline_d
            preview = baseline_d[:300] + ("..." if len(baseline_d) > 300 else "")
            return (
                f"**Baseline captured** for `{command_d}`\n\n"
                f"```\n{preview}\n```\n\n"
                "_Run the same command again after making changes to see the diff._"
            )

        before_d = registry._output_differ_baseline.pop(command_d)
        after_d = differ.capture(command_d)
        result_d = differ.diff(before_d, after_d)

        if not result_d.changed:
            return f"**No changes** in output of `{command_d}`."

        summary_d = f"+{result_d.added_lines} lines / -{result_d.removed_lines} lines"
        diff_display = result_d.diff_text[:2000]
        if len(result_d.diff_text) > 2000:
            diff_display += "\n... (truncated)"
        return (
            f"**Output diff for `{command_d}`** — {summary_d}\n\n"
            f"```diff\n{diff_display}\n```"
        )

    registry.register(SlashCommand("diff-output", "Compare command output before/after changes", diff_output_handler))

    # ── Q63 Task 423: /think ───────────────────────────────────────────────

    async def think_handler(arg: str = "", **_: Any) -> str:
        """/think [on|off|budget N] — toggle extended thinking or set token budget."""
        if not registry._session:
            return "Session not initialized."

        cfg = registry._session.config.agents
        text = arg.strip().lower()

        if not text or text == "status":
            state = "on" if cfg.extended_thinking else "off"
            return (
                f"**Extended thinking:** {state}\n"
                f"**Budget:** {cfg.thinking_budget} tokens\n\n"
                "Usage: `/think on|off` or `/think budget <N>`"
            )

        parts = text.split()

        if parts[0] == "on":
            registry._session.config = registry._session.config.model_copy(
                update={"agents": cfg.model_copy(update={"extended_thinking": True})}
            )
            return f"Extended thinking **enabled** (budget: {cfg.thinking_budget} tokens)."

        if parts[0] == "off":
            registry._session.config = registry._session.config.model_copy(
                update={"agents": cfg.model_copy(update={"extended_thinking": False})}
            )
            return "Extended thinking **disabled**."

        if parts[0] == "budget" and len(parts) >= 2:
            try:
                budget = int(parts[1].replace("k", "000").replace("K", "000"))
                registry._session.config = registry._session.config.model_copy(
                    update={"agents": cfg.model_copy(update={"thinking_budget": budget})}
                )
                return f"Thinking budget set to **{budget:,}** tokens."
            except ValueError:
                return f"Invalid budget value: `{parts[1]}`."

        return (
            "**Usage:** `/think [on|off|budget N]`\n\n"
            "  `on`        — enable extended thinking\n"
            "  `off`       — disable extended thinking\n"
            "  `budget N`  — set thinking token budget (e.g. `budget 8000`)\n"
            "  `status`    — show current settings"
        )

    registry.register(SlashCommand(
        "think",
        "Toggle extended thinking: /think [on|off|budget N]",
        think_handler,
    ))

    # ── Q63 Task 425: /warm ────────────────────────────────────────────────

    async def warm_handler(arg: str = "", **_: Any) -> str:
        """/warm [all|<agent>] — pre-warm Anthropic prompt cache."""
        if not registry._session:
            return "Session not initialized."

        from lidco.ai.cache_warm import CacheWarmer
        warmer = CacheWarmer(registry._session)

        text = arg.strip()
        if not text or text == "all":
            results = await warmer.warm_all()
        else:
            results = await warmer.warm_all(agent_names=[text])

        if not results:
            return "No agents to warm."

        lines = ["**Cache Warm Results**\n"]
        for r in results:
            if r.success:
                lines.append(
                    f"  ✓ **{r.agent_name}** — {r.tokens_cached} tokens cached "
                    f"({r.duration_ms:.0f}ms)"
                )
            else:
                lines.append(f"  ✗ **{r.agent_name}** — {r.error}")

        total_cached = sum(r.tokens_cached for r in results if r.success)
        lines.append(f"\nTotal tokens cached: **{total_cached}**")
        return "\n".join(lines)

    registry.register(SlashCommand(
        "warm",
        "Pre-warm prompt cache: /warm [all|<agent>]",
        warm_handler,
    ))

    # ── Q63 Task 426: /compare-models ──────────────────────────────────────

    async def compare_models_handler(arg: str = "", **_: Any) -> str:
        """/compare-models <m1> <m2> [--prompt "..."] — compare models side by side."""
        import re as _re
        if not registry._session:
            return "Session not initialized."

        if not arg.strip():
            return (
                "**Usage:** `/compare-models <model1> <model2> [--prompt \"...\"]`\n\n"
                "Example: `/compare-models gpt-4o claude-3-5-sonnet --prompt \"Explain recursion\"`"
            )

        # Extract --prompt flag
        prompt = "Explain the concept of recursion in programming."
        m = _re.search(r'--prompt\s+"([^"]+)"', arg)
        if not m:
            m = _re.search(r"--prompt\s+'([^']+)'", arg)
        if not m:
            m = _re.search(r"--prompt\s+(\S.*?)(?:\s+--|$)", arg)
        if m:
            prompt = m.group(1).strip()
            arg = arg[:m.start()].strip() + arg[m.end():].strip()

        models = [m2.strip() for m2 in arg.split() if m2.strip()]
        if len(models) < 1:
            return "Please provide at least one model name."

        from lidco.ai.cost_compare import ModelComparator
        comparator = ModelComparator(registry._session)
        results = await comparator.compare(prompt, models)

        lines = [f"**Model Comparison**", f"Prompt: *{prompt[:80]}{'…' if len(prompt) > 80 else ''}*", ""]
        lines.append(comparator.format_table(results))
        return "\n".join(lines)

    registry.register(SlashCommand(
        "compare-models",
        "Compare LLM models side-by-side: /compare-models <m1> <m2> [--prompt \"...\"]",
        compare_models_handler,
    ))

    # ── Q63 Task 427: /ollama ──────────────────────────────────────────────

    async def ollama_handler(arg: str = "", **_: Any) -> str:
        """/ollama [list|pull <model>|run <model>] — manage local Ollama models."""
        from lidco.ai.ollama_provider import OllamaProvider

        base_url = "http://localhost:11434"
        if registry._session:
            base_url = getattr(
                registry._session.config.llm, "ollama_base_url", base_url
            )

        provider = OllamaProvider(base_url)
        text = arg.strip()

        if not text or text == "list":
            if not provider.is_available():
                return (
                    "Ollama is not running at `{}`.\n\n"
                    "Start Ollama with: `ollama serve`".format(base_url)
                )
            models = provider.list_models()
            if not models:
                return "No models installed. Use `ollama pull <model>` to install one."
            lines = [f"**Ollama models** ({len(models)} installed)\n"]
            for m in models:
                lines.append(f"  · {m}")
            return "\n".join(lines)

        parts = text.split(None, 1)
        subcmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "pull":
            if not rest:
                return "Usage: `/ollama pull <model-name>`"
            return (
                f"To pull **{rest}**, run in your terminal:\n\n"
                f"```\nollama pull {rest}\n```"
            )

        if subcmd == "run":
            if not rest:
                return "Usage: `/ollama run <model-name>`"
            if not provider.is_available():
                return "Ollama is not running. Start with: `ollama serve`"
            try:
                response = await provider.chat(
                    messages=[{"role": "user", "content": "Hello"}],
                    model=rest,
                )
                return f"**{rest}** responded:\n\n{response}"
            except Exception as e:
                return f"Error running `{rest}`: {e}"

        return (
            "**Usage:** `/ollama <subcommand>`\n\n"
            "  `list`        — list installed models\n"
            "  `pull <name>` — show pull command\n"
            "  `run <name>`  — test model with a ping"
        )

    registry.register(SlashCommand(
        "ollama",
        "Manage local Ollama models: /ollama [list|pull <model>|run <model>]",
        ollama_handler,
    ))

    # ── Q63 Task 429: /cost-budget ─────────────────────────────────────────

    # Shared BudgetTracker instance persisted on CommandRegistry
    registry._cost_budget_tracker: Any = None

    async def cost_budget_handler(arg: str = "", **_: Any) -> str:
        """/cost-budget [status|reset|set daily N|set monthly N] — manage cost budget."""
        from lidco.ai.budget_alerts import BudgetTracker

        if registry._cost_budget_tracker is None:
            daily = 5.0
            monthly = 50.0
            if registry._session:
                cfg = registry._session.config
                budget_cfg = getattr(cfg, "budget", None)
                if budget_cfg:
                    daily = getattr(budget_cfg, "daily_usd", daily)
                    monthly = getattr(budget_cfg, "monthly_usd", monthly)
            registry._cost_budget_tracker = BudgetTracker(
                daily_limit_usd=daily,
                monthly_limit_usd=monthly,
            )

        tracker: BudgetTracker = registry._cost_budget_tracker
        text = arg.strip().lower()
        parts = text.split()

        if not text or text == "status":
            st = tracker.status()
            lines = ["**Cost Budget Status**\n"]
            lines.append(
                f"  Daily:   ${st['daily_spend']:.4f} / ${st['daily_limit']:.2f}"
                f"  ({st['daily_pct']:.1f}%)"
            )
            lines.append(
                f"  Monthly: ${st['monthly_spend']:.4f} / ${st['monthly_limit']:.2f}"
                f"  ({st['monthly_pct']:.1f}%)"
            )
            alerts = tracker.check_limits()
            if alerts:
                lines.append("")
                for a in alerts:
                    lines.append(f"  ⚠ {a}")
            return "\n".join(lines)

        if text == "reset":
            tracker.reset_all()
            return "Budget counters reset."

        if len(parts) >= 3 and parts[0] == "set":
            period = parts[1]
            try:
                amount = float(parts[2])
            except ValueError:
                return f"Invalid amount: `{parts[2]}`."
            if period == "daily":
                tracker.daily_limit_usd = amount
                return f"Daily budget set to **${amount:.2f}**."
            if period == "monthly":
                tracker.monthly_limit_usd = amount
                return f"Monthly budget set to **${amount:.2f}**."
            return f"Unknown period `{period}`. Use `daily` or `monthly`."

        return (
            "**Usage:** `/cost-budget [subcommand]`\n\n"
            "  `status`           — show current spend vs limits\n"
            "  `reset`            — clear all counters\n"
            "  `set daily N`      — set daily limit in USD\n"
            "  `set monthly N`    — set monthly limit in USD"
        )

    registry.register(SlashCommand(
        "cost-budget",
        "Manage LLM cost budget alerts: /cost-budget [status|reset|set daily N|set monthly N]",
        cost_budget_handler,
    ))

    # ── Q60: External Integrations ─────────────────────────────────────

    # Task 403: /issue — GitHub Issues integration
    async def issue_handler(arg: str = "", **_: Any) -> str:
        """/issue list|view N|create|close N — GitHub Issues integration."""
        from lidco.integrations.github_issues import IssueClient

        client = IssueClient()
        parts = (arg or "").split(None, 1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1].strip() if len(parts) > 1 else ""

        try:
            if sub == "list" or not sub:
                issues = client.list_issues()
                if not issues:
                    return "No open issues found."
                lines = [f"**Open Issues ({len(issues)})**\n"]
                for iss in issues:
                    label_str = f" [{', '.join(iss.labels)}]" if iss.labels else ""
                    lines.append(f"- #{iss.number} **{iss.title}**{label_str}")
                return "\n".join(lines)

            if sub == "view":
                if not rest.isdigit():
                    return "Usage: `/issue view <number>`"
                iss = client.get_issue(int(rest))
                lines = [
                    f"## Issue #{iss.number}: {iss.title}",
                    f"**State:** {iss.state}  |  **URL:** {iss.url}",
                ]
                if iss.labels:
                    lines.append(f"**Labels:** {', '.join(iss.labels)}")
                if iss.body:
                    lines.append(f"\n{iss.body[:2000]}")
                return "\n".join(lines)

            if sub == "create":
                if not rest:
                    return "Usage: `/issue create <title>`"
                iss = client.create_issue(title=rest)
                return f"Created issue #{iss.number}: **{iss.title}**\n{iss.url}"

            if sub == "close":
                if not rest.isdigit():
                    return "Usage: `/issue close <number>`"
                client.close_issue(int(rest))
                return f"Closed issue #{rest}."

            return (
                "**GitHub Issues commands:**\n\n"
                "- `/issue list` — list open issues\n"
                "- `/issue view N` — view issue #N\n"
                "- `/issue create <title>` — create new issue\n"
                "- `/issue close N` — close issue #N"
            )
        except RuntimeError as exc:
            return f"GitHub Issues error: {exc}"

    registry.register(SlashCommand("issue", "GitHub Issues integration", issue_handler))

    # Task 404: /ci — CI/CD pipeline status
    async def ci_handler(arg: str = "", **_: Any) -> str:
        """/ci [--watch] — Show latest CI/CD workflow runs for current branch."""
        from lidco.integrations.ci_status import CIClient

        client = CIClient()
        watch = "--watch" in (arg or "")

        try:
            runs = client.get_current_branch_status(limit=5)
        except RuntimeError as exc:
            return f"CI status error: {exc}"

        if not runs:
            return "No workflow runs found for current branch."

        _STATUS_ICONS: dict = {
            "completed": {"success": "✅", "failure": "❌", "cancelled": "⊘", "skipped": "⏭"},
            "in_progress": "⟳",
            "queued": "⏳",
            "waiting": "⏳",
        }

        def _format_runs(ci_runs: list) -> str:
            lines = [f"**CI Runs** (branch: {ci_runs[0].branch})\n"]
            for run in ci_runs:
                if run.status == "completed":
                    icon = _STATUS_ICONS["completed"].get(run.conclusion, "?")
                else:
                    icon = _STATUS_ICONS.get(run.status, "?")
                lines.append(
                    f"- {icon} **{run.name}** — {run.status}"
                    + (f" / {run.conclusion}" if run.conclusion else "")
                    + f"\n  `{run.url}`"
                )
            return "\n".join(lines)

        if not watch:
            return _format_runs(runs)

        return _format_runs(runs) + "\n\n_--watch mode: re-run `/ci --watch` to refresh_"

    registry.register(SlashCommand("ci", "Show CI/CD workflow run status for current branch", ci_handler))

    # Task 405: /slack — Send Slack notification
    async def slack_handler(arg: str = "", **_: Any) -> str:
        """/slack <message> — Send message to configured Slack webhook."""
        from lidco.integrations.slack import SlackNotifier

        msg = (arg or "").strip()
        if not msg:
            return (
                "**Usage:** `/slack <message>`\n\n"
                "Sends a message to the configured Slack webhook.\n\n"
                "**Configuration:**\n"
                "- Set `LIDCO_SLACK_WEBHOOK` environment variable, or\n"
                "- Add `slack.webhook_url` to `~/.lidco/config.yaml`"
            )

        try:
            notifier = SlackNotifier()
            notifier.send(msg)
            return f"Message sent to Slack: `{msg[:100]}`"
        except ValueError as exc:
            return f"Slack not configured: {exc}"
        except RuntimeError as exc:
            return f"Slack error: {exc}"

    registry.register(SlashCommand("slack", "Send Slack notification to configured webhook", slack_handler))

    # Task 406: /ticket — Linear/Jira ticket integration
    async def ticket_handler(arg: str = "", **_: Any) -> str:
        """/ticket list|view ID|update ID [--status STATUS] [--comment TEXT]"""
        import os as _os

        parts = (arg or "").split(None, 1)
        sub = parts[0].lower() if parts else "list"
        rest = parts[1] if len(parts) > 1 else ""

        has_linear = bool(_os.environ.get("LINEAR_API_KEY"))
        has_jira = bool(_os.environ.get("JIRA_URL") and _os.environ.get("JIRA_TOKEN"))

        if not has_linear and not has_jira:
            return (
                "**Ticket client not configured.**\n\n"
                "Set one of:\n"
                "- `LINEAR_API_KEY` for Linear\n"
                "- `JIRA_URL` + `JIRA_TOKEN` for Jira"
            )

        if has_linear:
            from lidco.integrations.ticket_client import LinearClient
            client_t = LinearClient()
        else:
            from lidco.integrations.ticket_client import JiraClient
            client_t = JiraClient()

        try:
            if sub == "list":
                tickets = client_t.list_tickets()
                if not tickets:
                    return "No tickets found."
                lines = [f"**Tickets ({len(tickets)})**\n"]
                for t in tickets:
                    lines.append(f"- **{t.ticket_id}** [{t.status}] {t.title}")
                return "\n".join(lines)

            if sub == "view":
                if not rest.strip():
                    return "Usage: `/ticket view <id>`"
                ticket = client_t.get_ticket(rest.strip())
                lines = [
                    f"## {ticket.ticket_id}: {ticket.title}",
                    f"**Status:** {ticket.status}",
                ]
                if ticket.assignee:
                    lines.append(f"**Assignee:** {ticket.assignee}")
                if ticket.url:
                    lines.append(f"**URL:** {ticket.url}")
                if ticket.description:
                    lines.append(f"\n{ticket.description[:1000]}")
                return "\n".join(lines)

            if sub == "update":
                rest_parts = rest.split()
                if not rest_parts:
                    return "Usage: `/ticket update <id> [--status STATUS] [--comment TEXT]`"
                ticket_id = rest_parts[0]
                status = None
                comment = None
                i = 1
                while i < len(rest_parts):
                    if rest_parts[i] == "--status" and i + 1 < len(rest_parts):
                        status = rest_parts[i + 1]
                        i += 2
                    elif rest_parts[i] == "--comment" and i + 1 < len(rest_parts):
                        comment = " ".join(rest_parts[i + 1:])
                        break
                    else:
                        i += 1
                updated = client_t.update_ticket(ticket_id, status=status, comment=comment)
                return f"Updated **{updated.ticket_id}**: status={updated.status}"

            return (
                "**Ticket commands:**\n\n"
                "- `/ticket list` — list tickets\n"
                "- `/ticket view <id>` — view ticket\n"
                "- `/ticket update <id> [--status STATUS] [--comment TEXT]` — update ticket"
            )
        except (ValueError, RuntimeError) as exc:
            return f"Ticket error: {exc}"

    registry.register(SlashCommand("ticket", "Linear/Jira ticket integration", ticket_handler))

    # Task 407: /openapi — OpenAPI client generator
    async def openapi_handler(arg: str = "", **_: Any) -> str:
        """/openapi import path/to/spec.yaml [--output client.py]"""
        from lidco.integrations.openapi_gen import OpenAPIParser, PythonClientGenerator

        tokens = (arg or "").split()
        if not tokens or tokens[0].lower() != "import":
            return (
                "**Usage:** `/openapi import path/to/spec.yaml [--output client.py]`\n\n"
                "Generates a typed Python requests-based API client."
            )

        spec_parts = [p for p in tokens[1:] if not p.startswith("--")]
        output_file = None
        if "--output" in tokens:
            idx = tokens.index("--output")
            if idx + 1 < len(tokens):
                output_file = tokens[idx + 1]
                spec_parts = [p for p in spec_parts if p != output_file]

        if not spec_parts:
            return "No spec file provided. Usage: `/openapi import path/to/spec.yaml`"

        spec_path = spec_parts[0]
        try:
            parser = OpenAPIParser(spec_path)
            parser.load()
            gen = PythonClientGenerator()
            source = gen.generate(parser, output_file=output_file)
            endpoints = parser.extract_endpoints()
            msg_lines = [
                f"**OpenAPI Client Generated** from `{spec_path}`",
                f"- Title: {parser.title}",
                f"- Endpoints: {len(endpoints)}",
            ]
            if output_file:
                msg_lines.append(f"- Output: `{output_file}`")
            else:
                preview = source[:1500]
                if len(source) > 1500:
                    preview += "\n... (truncated)"
                msg_lines.append(f"\n```python\n{preview}\n```")
            return "\n".join(msg_lines)
        except (ValueError, RuntimeError) as exc:
            return f"OpenAPI error: {exc}"

    registry.register(SlashCommand("openapi", "Generate Python API client from OpenAPI spec", openapi_handler))

    # Task 408: /api — API test runner
    async def api_handler(arg: str = "", **_: Any) -> str:
        """/api [--base URL] [--header KEY:VAL] METHOD /path [--body JSON]"""
        from lidco.integrations.api_runner import APIRunner

        tokens = (arg or "").split()
        if not tokens:
            return (
                "**Usage:** `/api [--base URL] [--header KEY:VAL] METHOD /path [--body JSON]`\n\n"
                "**Examples:**\n"
                "- `/api GET /users`\n"
                "- `/api POST /users --body '{\"name\":\"Alice\"}'`\n"
                "- `/api --base https://api.example.com GET /me`"
            )

        base_url = ""
        headers_api: dict[str, str] = {}
        body_json = None
        method = ""
        path = ""

        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t == "--base" and i + 1 < len(tokens):
                base_url = tokens[i + 1]
                i += 2
            elif t == "--header" and i + 1 < len(tokens):
                kv = tokens[i + 1]
                if ":" in kv:
                    k, v = kv.split(":", 1)
                    headers_api[k.strip()] = v.strip()
                i += 2
            elif t == "--body" and i + 1 < len(tokens):
                body_str = " ".join(tokens[i + 1:])
                try:
                    import json as _json_api
                    body_json = _json_api.loads(body_str)
                except Exception:
                    body_json = body_str
                break
            elif not method and t.upper() in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
                method = t.upper()
                i += 1
            elif method and not path:
                path = t
                i += 1
            else:
                i += 1

        if not method:
            return "No HTTP method found. Use GET, POST, PUT, PATCH, or DELETE."
        if not path:
            return "No path provided."

        try:
            runner = APIRunner(base_url=base_url, headers=headers_api)
            resp = runner.request(method, path, body=body_json)
            return resp.format()
        except RuntimeError as exc:
            return f"API request failed: {exc}"

    registry.register(SlashCommand("http", "Make HTTP API requests (METHOD-first format)", api_handler))

    # Task 409: /browser — Browser automation
    async def browser_handler(arg: str = "", **_: Any) -> str:
        """/browser <url> — Open browser and take screenshot via Playwright."""
        import shutil as _shutil

        url = (arg or "").strip()
        if not url:
            return (
                "**Usage:** `/browser <url>`\n\n"
                "Takes a screenshot of the given URL.\n\n"
                "**Requires:** Playwright installed\n"
                "  `pip install playwright && playwright install chromium`"
            )

        if not _shutil.which("playwright"):
            return (
                "Playwright is not installed.\n\n"
                "Install it with:\n"
                "  `pip install playwright`\n"
                "  `playwright install chromium`"
            )

        from lidco.integrations.browser import BrowserSession

        session_br = BrowserSession()
        screenshot_path = "lidco_screenshot.png"
        try:
            saved = session_br.screenshot(screenshot_path, url=url)
            return f"Screenshot of `{url}` saved to `{saved}`"
        except RuntimeError as exc:
            return f"Browser error: {exc}"

    registry.register(SlashCommand("browser", "Open browser and take screenshot via Playwright", browser_handler))

    # ------------------------------------------------------------------ #
    # Q61 — Smart Proactive Assistance                                    #
    # ------------------------------------------------------------------ #

    import asyncio as _asyncio_q61

    # Task 410: /bugbot
    registry._bugbot_enabled: bool = False  # type: ignore[attr-defined]

    async def bugbot_handler(arg: str = "", **_: Any) -> str:
        """/bugbot on|off|status [file] — proactive bug detection."""
        from lidco.proactive.bugbot import BugbotAnalyzer

        raw = (arg or "").strip()

        if raw in ("on", "off"):
            registry._bugbot_enabled = raw == "on"
            state = "enabled" if registry._bugbot_enabled else "disabled"
            return f"Bugbot {state}."

        if raw == "status":
            state = "enabled" if registry._bugbot_enabled else "disabled"
            return f"Bugbot is **{state}**."

        # /bugbot <file> — analyze a specific file
        if raw:
            file_path = raw
            analyzer = BugbotAnalyzer()
            try:
                from pathlib import Path as _Path
                source = _Path(file_path).read_text(encoding="utf-8")
            except OSError as exc:
                return f"Cannot read `{file_path}`: {exc}"
            reports = analyzer.analyze(source, file_path)
            if not reports:
                return f"No bugs detected in `{file_path}`."
            lines = [f"**Bugs found in `{file_path}`:** ({len(reports)} issue(s))\n"]
            for r in reports:
                icon = {"error": "✖", "warning": "⚠", "info": "ℹ"}.get(r.severity, "•")
                lines.append(f"  {icon} Line {r.line} `{r.kind}` — {r.message}")
            return "\n".join(lines)

        return (
            "**Usage:** `/bugbot on|off|status [file]`\n\n"
            "- `on` / `off` — enable/disable automatic file watching\n"
            "- `status` — show current state\n"
            "- `<file>` — analyze a specific file now"
        )

    registry.register(SlashCommand("bugbot", "Proactive AST-based bug detector", bugbot_handler))

    # Task 411: /regcheck
    async def regcheck_handler(arg: str = "", **_: Any) -> str:
        """/regcheck <file> — run related tests to detect regressions."""
        from lidco.proactive.regression_detector import RegressionDetector

        file_path = (arg or "").strip()
        if not file_path:
            return "**Usage:** `/regcheck <file>`\n\nRun related tests to detect regressions after editing a file."

        detector = RegressionDetector()
        result = await detector.detect(file_path)

        if not result.test_files_run:
            return f"No related test files found for `{file_path}`."

        status = "✓ All passed" if result.failed == 0 else f"✖ {result.failed} failed"
        lines = [
            f"**Regression check for `{file_path}`**",
            f"Tests run: {len(result.test_files_run)} file(s) | "
            f"Passed: {result.passed} | Failed: {result.failed} | "
            f"Time: {result.duration_ms:.0f}ms",
            f"Status: {status}",
        ]
        if result.test_files_run:
            lines.append("\nTest files:")
            for tf in result.test_files_run[:5]:
                lines.append(f"  - `{tf}`")
        return "\n".join(lines)

    registry.register(SlashCommand("regcheck", "Run related tests to detect regressions", regcheck_handler))

    # Task 412: /fix
    async def fix_handler(arg: str = "", **_: Any) -> str:
        """/fix [file|all] [--lint] [--imports] [--preview] — auto-fix code issues."""
        from lidco.proactive.auto_fix import AutoFixer

        parts = (arg or "").split()
        preview = "--preview" in parts
        do_lint = "--lint" in parts or (not any(p.startswith("--") for p in parts[1:]))
        do_imports = "--imports" in parts or (not any(p.startswith("--") for p in parts[1:]))

        # Extract file path (first non-flag token)
        file_path = next((p for p in parts if not p.startswith("--")), "")
        if not file_path:
            return (
                "**Usage:** `/fix <file> [--lint] [--imports] [--preview]`\n\n"
                "- `--lint` — run ruff auto-fix\n"
                "- `--imports` — sort imports with isort\n"
                "- `--preview` — show diff without applying\n\n"
                "If no flags given, both lint and imports are run."
            )

        fixer = AutoFixer()
        results = []

        if do_lint:
            r = await fixer.fix_lint(file_path, preview=preview)
            results.append(r)

        if do_imports:
            r = await fixer.fix_imports(file_path, preview=preview)
            results.append(r)

        if not results:
            return "No fix operations performed."

        lines = [f"**Auto-fix results for `{file_path}`:**\n"]
        for r in results:
            icon = "✓" if r.changes_made else "−"
            action = "would change" if preview else "changed"
            lines.append(f"  {icon} **{r.tool}** — {action} {r.lines_changed} line(s)")
            if preview and r.diff:
                lines.append(f"```diff\n{r.diff[:800]}\n```")
        return "\n".join(lines)

    registry.register(SlashCommand("fix", "Auto-fix lint and import issues", fix_handler))

    # Task 413: /suggest
    registry._suggestions_enabled: bool = False  # type: ignore[attr-defined]

    async def suggest_handler(arg: str = "", **_: Any) -> str:
        """/suggest on|off — toggle next-action suggestions after agent responses."""
        raw = (arg or "").strip()
        if raw in ("on", "off"):
            registry._suggestions_enabled = raw == "on"
            if registry._session:
                registry._session.config.agents.suggestions_enabled = registry._suggestions_enabled
            state = "enabled" if registry._suggestions_enabled else "disabled"
            return f"Next-action suggestions {state}."
        state = "enabled" if registry._suggestions_enabled else "disabled"
        return f"Suggestions are **{state}**. Use `/suggest on|off` to toggle."

    registry.register(SlashCommand("suggest", "Toggle next-action suggestions after responses", suggest_handler))

    # Task 414: /secscan
    async def secscan_handler(arg: str = "", **_: Any) -> str:
        """/secscan [file|all] — scan for security issues."""
        from lidco.proactive.security_scanner import SecurityScanner
        import glob as _glob

        raw = (arg or "").strip()
        scanner = SecurityScanner()

        if not raw or raw == "all":
            # Scan all Python files in src/
            pattern = "src/**/*.py"
            files = _glob.glob(pattern, recursive=True)
            if not files:
                return "No Python files found to scan."
            all_issues = []
            for f in files[:50]:  # cap to avoid huge output
                all_issues.extend(scanner.scan_file(f))
            if not all_issues:
                return f"No security issues found in {len(files)} file(s)."
            lines = [f"**Security scan** — {len(all_issues)} issue(s) in {len(files)} file(s)\n"]
            for issue in all_issues[:20]:
                sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue.severity, "•")
                lines.append(f"  {sev_icon} `{issue.file}:{issue.line}` [{issue.rule_id}] {issue.message}")
            if len(all_issues) > 20:
                lines.append(f"\n  ... and {len(all_issues) - 20} more issues.")
            return "\n".join(lines)

        # Specific file
        issues = scanner.scan_file(raw)
        if not issues:
            return f"No security issues found in `{raw}`."
        lines = [f"**Security scan of `{raw}`** — {len(issues)} issue(s)\n"]
        for issue in issues:
            sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue.severity, "•")
            lines.append(
                f"  {sev_icon} Line {issue.line} [{issue.rule_id}] **{issue.severity.upper()}** — {issue.message}"
            )
            if issue.snippet:
                lines.append(f"    `{issue.snippet}`")
        return "\n".join(lines)

    registry.register(SlashCommand("secscan", "Scan for security issues (hardcoded secrets, SQL injection, eval)", secscan_handler))

    # Task 415: /perf
    async def perf_handler(arg: str = "", **_: Any) -> str:
        """/perf [file] — show performance hints for a file."""
        from lidco.proactive.perf_hints import PerformanceAnalyzer

        file_path = (arg or "").strip()
        if not file_path:
            return (
                "**Usage:** `/perf <file>`\n\n"
                "Analyze a Python file for performance anti-patterns:\n"
                "- String concatenation in loops\n"
                "- `len(x) == 0` instead of `not x`\n"
                "- `sorted()` called multiple times\n"
                "- `list.append()` in loops (use comprehensions)\n"
                "- Nested loops with list subscript access"
            )

        analyzer = PerformanceAnalyzer()
        hints = analyzer.analyze_file(file_path)

        if not hints:
            return f"No performance issues found in `{file_path}`."

        lines = [f"**Performance hints for `{file_path}`** — {len(hints)} hint(s)\n"]
        for h in hints:
            lines.append(f"  ⚡ Line {h.line} `{h.kind}` — {h.message}")
            lines.append(f"    💡 {h.suggestion}")
        return "\n".join(lines)

    registry.register(SlashCommand("perf-hints", "Show AST-based performance hints for a Python file", perf_handler))

    # Task 416: /refactor suggest|apply
    async def refactor_suggest_apply_handler(arg: str = "", **_: Any) -> str:
        """/refactor suggest [file] | apply N — code smell refactoring."""
        from lidco.proactive.smell_refactor import SmellRefactorer

        parts = (arg or "").strip().split(None, 1)
        if not parts:
            return (
                "**Usage:**\n"
                "- `/refactor suggest [file]` — list code smells with refactoring preview\n"
                "- `/refactor apply N` — apply suggestion N"
            )

        sub = parts[0]
        rest = parts[1].strip() if len(parts) > 1 else ""

        session = registry._session
        refactorer = SmellRefactorer(session=session)

        if sub == "suggest":
            file_path = rest
            if not file_path:
                return "**Usage:** `/refactor suggest <file>`"

            suggestions = await refactorer.suggest_refactors(file_path)
            if not suggestions:
                candidates = refactorer.find_smells(file_path)
                if not candidates:
                    return f"No code smells found in `{file_path}`."
                lines = [f"**Code smells in `{file_path}`** (LLM session not available for suggestions)\n"]
                for i, c in enumerate(candidates, 1):
                    lines.append(f"  {i}. Line {c.line} `{c.kind.value}` in `{c.name}` — {c.detail}")
                return "\n".join(lines)

            # Store suggestions for /refactor apply N
            registry._last_refactor_suggestions = suggestions  # type: ignore[attr-defined]
            lines = [f"**Refactoring suggestions for `{file_path}`** ({len(suggestions)} smell(s))\n"]
            for i, s in enumerate(suggestions, 1):
                lines.append(f"**{i}.** Line {s.candidate.line} `{s.candidate.kind.value}` — {s.candidate.detail}")
                if s.explanation:
                    lines.append(f"   _{s.explanation}_")
                if s.before_snippet:
                    lines.append(f"   **Before:**\n```python\n{s.before_snippet[:300]}\n```")
                if s.after_snippet:
                    lines.append(f"   **After:**\n```python\n{s.after_snippet[:300]}\n```")
                lines.append("")
            lines.append("Use `/refactor apply N` to apply a suggestion.")
            return "\n".join(lines)

        if sub == "apply":
            suggestions = getattr(registry, "_last_refactor_suggestions", [])
            if not suggestions:
                return "No suggestions available. Run `/refactor suggest <file>` first."
            try:
                n = int(rest) - 1
            except (ValueError, TypeError):
                return "**Usage:** `/refactor apply N` — where N is the suggestion number."
            if n < 0 or n >= len(suggestions):
                return f"Suggestion {n+1} out of range (1–{len(suggestions)})."
            suggestion = suggestions[n]
            file_path = suggestion.candidate.file
            applied = refactorer.apply_suggestion(file_path, suggestion)
            if applied:
                return f"✓ Applied suggestion {n+1} to `{file_path}`."
            return f"Could not apply suggestion {n+1} — snippet may have changed."

        return (
            "**Usage:**\n"
            "- `/refactor suggest [file]` — list code smells with refactoring preview\n"
            "- `/refactor apply N` — apply suggestion N"
        )

    registry.register(SlashCommand("refactor-suggest", "Code smell detection and LLM-assisted refactoring", refactor_suggest_apply_handler))

