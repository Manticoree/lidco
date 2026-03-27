"""Q107 CLI commands: /compose /ctx-optimize /workflow /action."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q107 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------ #
    # /compose — multi-file composer mode                                  #
    # ------------------------------------------------------------------ #

    async def compose_handler(args: str) -> str:
        from lidco.composer.session import ComposerSession, FileChange, ComposerError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "demo":
            session = ComposerSession()
            changes = [
                FileChange(
                    path="src/hello.py",
                    old_content='def greet():\n    return "hi"\n',
                    new_content='def greet(name: str = "world") -> str:\n    return f"Hello, {name}!"\n',
                    description="Add typed parameter",
                ),
                FileChange(
                    path="src/new_module.py",
                    old_content="",
                    new_content='"""New module."""\nVERSION = "1.0.0"\n',
                    description="Create new module",
                ),
            ]
            plan = session.create_plan("Add typed greet + new module", changes)
            return plan.preview()

        if sub == "plan":
            if not rest:
                return "Usage: /compose plan <goal>"
            if "session" not in _state:
                _state["session"] = ComposerSession()
            session: ComposerSession = _state["session"]  # type: ignore[assignment]
            plan = session.create_plan(rest, [])
            return f"Plan created: {plan.goal}\nUse '/compose add <path> <description>' to add changes."

        if sub == "add":
            session = _state.get("session")
            if session is None:
                return "No active session. Run '/compose plan <goal>' first."
            tokens = rest.split(maxsplit=1)
            path = tokens[0] if tokens else ""
            desc = tokens[1] if len(tokens) > 1 else ""
            if not path:
                return "Usage: /compose add <path> [description]"
            try:
                session.add_change(  # type: ignore[union-attr]
                    FileChange(path=path, old_content="", new_content="# placeholder\n", description=desc)
                )
                return f"Change added: {path}"
            except ComposerError as exc:
                return f"Error: {exc}"

        if sub == "preview":
            session = _state.get("session")
            if session is None:
                return "No active session."
            return session.preview()  # type: ignore[union-attr]

        if sub == "summary":
            session = _state.get("session")
            if session is None:
                return "No active session."
            return session.summary()  # type: ignore[union-attr]

        if sub == "apply":
            session = _state.get("session")
            if session is None:
                return "No active session."
            try:
                written = session.apply(dry_run=True)  # type: ignore[union-attr]
                return f"[dry-run] Would write: {', '.join(written)}"
            except ComposerError as exc:
                return f"Error: {exc}"

        if sub == "rollback":
            session = _state.get("session")
            if session is None:
                return "No active session."
            try:
                restored = session.rollback()  # type: ignore[union-attr]
                return f"Rolled back: {', '.join(restored)}"
            except ComposerError as exc:
                return f"Error: {exc}"

        if sub == "reset":
            _state.pop("session", None)
            return "Composer session cleared."

        return (
            "Usage: /compose <sub>\n"
            "  demo               — show diff preview example\n"
            "  plan <goal>        — start new composer session\n"
            "  add <path> [desc]  — stage a file change\n"
            "  preview            — show unified diff\n"
            "  summary            — show change summary\n"
            "  apply              — apply changes (dry-run here)\n"
            "  rollback           — undo last applied plan\n"
            "  reset              — clear session"
        )

    # ------------------------------------------------------------------ #
    # /ctx-optimize — context window optimizer                             #
    # ------------------------------------------------------------------ #

    async def ctx_optimize_handler(args: str) -> str:
        from lidco.context.optimizer import ContextOptimizer, ContextEntry, ContextSource

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_opt() -> ContextOptimizer:
            if "optimizer" not in _state:
                _state["optimizer"] = ContextOptimizer(token_budget=4096)
            return _state["optimizer"]  # type: ignore[return-value]

        if sub == "demo":
            opt = ContextOptimizer(token_budget=200)
            opt.add_text("def foo(): pass\ndef bar(): pass", source=ContextSource.FILE,
                         priority=2.0, label="main.py")
            opt.add_text("User asked about foo", source=ContextSource.HISTORY,
                         priority=1.0, label="history")
            opt.add_text("x" * 300, source=ContextSource.DOCS,
                         priority=0.5, label="large-doc")
            result = opt.optimize()
            lines = [
                f"Budget: {result.budget} tokens",
                f"Included: {len(result.included)} entries ({result.total_tokens} tokens)",
                f"Excluded: {len(result.excluded)} entries",
                f"Utilization: {result.utilization:.0%}",
            ]
            for e in result.included:
                lines.append(f"  ✓ [{e.label}] prio={e.priority} ~{e.token_count()}tok")
            for e in result.excluded:
                lines.append(f"  ✗ [{e.label}] prio={e.priority} ~{e.token_count()}tok (excluded)")
            return "\n".join(lines)

        if sub == "add":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /ctx-optimize add <label> <content>"
            label, content = tokens[0], tokens[1]
            opt = _get_opt()
            opt.add_text(content, label=label, priority=1.0)
            return f"Added '{label}' ({opt.total_tokens()} total tokens)"

        if sub == "stats":
            opt = _get_opt()
            s = opt.stats()
            return (
                f"Entries: {s['entries']} | Tokens: {s['total_tokens']}/{s['budget']} "
                f"({s['utilization']}%) | Included: {s['included']} | Excluded: {s['excluded']}"
            )

        if sub == "optimize":
            opt = _get_opt()
            result = opt.optimize()
            lines = [f"Optimization result ({result.total_tokens}/{result.budget} tokens):"]
            for e in result.included:
                lines.append(f"  ✓ {e.label or '(unnamed)'}")
            for e in result.excluded:
                lines.append(f"  ✗ {e.label or '(unnamed)'} — excluded")
            return "\n".join(lines)

        if sub == "budget":
            if not rest:
                opt = _get_opt()
                return f"Current budget: {opt.token_budget} tokens"
            opt = _get_opt()
            opt.set_budget(int(rest))
            return f"Budget set to {rest} tokens"

        if sub == "score":
            tokens = rest.split(maxsplit=1)
            if len(tokens) < 2:
                return "Usage: /ctx-optimize score <file_path> <query>"
            score = ContextOptimizer.score_file_relevance(tokens[0], tokens[1])
            return f"Relevance score for '{tokens[0]}' vs '{tokens[1]}': {score:.2f}"

        if sub == "clear":
            opt = _get_opt()
            opt.clear()
            return "Context cleared."

        return (
            "Usage: /ctx-optimize <sub>\n"
            "  demo                      — run optimizer demo\n"
            "  add <label> <text> [prio] — add context entry\n"
            "  stats                     — show pool stats\n"
            "  optimize                  — show optimization result\n"
            "  budget [N]                — get/set token budget\n"
            "  score <path> <query>      — score file relevance\n"
            "  clear                     — clear all entries"
        )

    # ------------------------------------------------------------------ #
    # /workflow — workflow engine                                          #
    # ------------------------------------------------------------------ #

    async def workflow_handler(args: str) -> str:
        from lidco.workflow.engine import WorkflowEngine, WorkflowStep, WorkflowError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""

        def _get_engine() -> WorkflowEngine:
            if "engine" not in _state:
                _state["engine"] = WorkflowEngine()
            return _state["engine"]  # type: ignore[return-value]

        if sub == "demo":
            engine = WorkflowEngine()

            def step_validate(ctx, **_):
                src = ctx.get("source", "")
                if not src:
                    raise ValueError("source is empty")
                return f"validated:{src}"

            def step_transform(ctx, validated=None, **_):
                return (validated or "").upper()

            def step_output(ctx, result=None, **_):
                return f"Final: {result}"

            engine.define("demo-pipeline", [
                WorkflowStep("validate", step_validate, output_key="validated"),
                WorkflowStep("transform", step_transform,
                             inputs={"validated": "validated"}, output_key="result"),
                WorkflowStep("output", step_output,
                             inputs={"result": "result"}, output_key="final"),
            ])
            wf_result = engine.run("demo-pipeline", initial_context={"source": "hello"})
            lines = [wf_result.summary()]
            for s in wf_result.steps:
                icon = "✓" if s.success else ("↷" if s.skipped else "✗")
                lines.append(f"  {icon} {s.name}: {s.output}")
            return "\n".join(lines)

        if sub == "list":
            engine = _get_engine()
            wfs = engine.list_workflows()
            if not wfs:
                return "No workflows defined."
            return "Workflows:\n" + "\n".join(f"  - {w}" for w in wfs)

        if sub == "run":
            engine = _get_engine()
            wf_name = parts[1] if len(parts) > 1 else "__default__"
            try:
                wf_result = engine.run(wf_name)
                lines = [wf_result.summary()]
                for s in wf_result.steps:
                    icon = "✓" if s.success else ("↷" if s.skipped else "✗")
                    err = f" — {s.error}" if s.error else ""
                    lines.append(f"  {icon} {s.name}{err}")
                return "\n".join(lines)
            except WorkflowError as exc:
                return f"Error: {exc}"

        if sub == "reset":
            _state.pop("engine", None)
            return "Workflow engine reset."

        return (
            "Usage: /workflow <sub>\n"
            "  demo          — run built-in pipeline demo\n"
            "  list          — list defined workflows\n"
            "  run [name]    — run a workflow\n"
            "  reset         — reset engine state"
        )

    # ------------------------------------------------------------------ #
    # /action — code actions quick-fix registry                           #
    # ------------------------------------------------------------------ #

    async def action_handler(args: str) -> str:
        from lidco.code_actions.registry import CodeActionsRegistry, CodeAction, CodeActionError

        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""

        def _get_reg() -> CodeActionsRegistry:
            if "action_reg" not in _state:
                _state["action_reg"] = CodeActionsRegistry.with_defaults()
            return _state["action_reg"]  # type: ignore[return-value]

        if sub == "demo":
            reg = CodeActionsRegistry.with_defaults()
            samples = [
                "NameError: name 'requests' is not defined",
                "TypeError: 'NoneType' object is not subscriptable",
                "console.log('debug')",
                "api_key = 'sk-proj-abc123secret'",
            ]
            lines = ["Code Actions Demo:", ""]
            for sample in samples:
                matches = reg.find_actions(sample)
                lines.append(f"  Input: {sample!r}")
                if matches:
                    for m in matches:
                        lines.append(f"    [{m.action.severity.upper()}] {m.title}")
                        lines.append(f"    Fix: {m.fix}")
                else:
                    lines.append("    (no actions)")
                lines.append("")
            return "\n".join(lines)

        if sub == "find":
            if not rest:
                return "Usage: /action find <error text>"
            reg = _get_reg()
            matches = reg.find_actions(rest)
            if not matches:
                return f"No actions match: {rest!r}"
            lines = [f"Actions for: {rest!r}", ""]
            for m in matches:
                lines.append(f"  [{m.action.severity.upper()}] {m.title}")
                lines.append(f"  Fix: {m.fix}")
            return "\n".join(lines)

        if sub == "list":
            reg = _get_reg()
            actions = reg.list_actions()
            if not actions:
                return "No actions registered."
            lines = [f"Registered actions ({len(actions)}):"]
            for a in actions:
                tags = f" [{', '.join(a.tags)}]" if a.tags else ""
                lines.append(f"  {a.id} — {a.title}{tags}")
            return "\n".join(lines)

        if sub == "analyze":
            if not rest:
                return "Usage: /action analyze <code or error text>"
            reg = _get_reg()
            grouped = reg.analyze(rest)
            if not grouped:
                return "No issues found."
            lines = []
            for severity in ("error", "warning", "info", "hint"):
                if severity in grouped:
                    lines.append(f"{severity.upper()}:")
                    for m in grouped[severity]:
                        lines.append(f"  {m.title}: {m.fix}")
            return "\n".join(lines)

        if sub == "reset":
            _state.pop("action_reg", None)
            return "Action registry reset to defaults on next use."

        return (
            "Usage: /action <sub>\n"
            "  demo              — show quick-fix demo\n"
            "  find <text>       — find actions matching text\n"
            "  list              — list all registered actions\n"
            "  analyze <text>    — group matches by severity\n"
            "  reset             — reset to default actions"
        )

    registry.register(SlashCommand("compose", "Multi-file composer mode", compose_handler))
    registry.register(SlashCommand("ctx-optimize", "Context window optimizer", ctx_optimize_handler))
    registry.register(SlashCommand("workflow", "Multi-step workflow engine", workflow_handler))
    registry.register(SlashCommand("action", "Code actions quick-fix registry", action_handler))
