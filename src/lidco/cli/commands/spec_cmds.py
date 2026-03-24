"""Q68 — /spec command: spec-driven development pipeline (Kiro parity).

Subcommands:
  /spec new <description>   — NL → requirements.md → design.md → tasks.md
  /spec show                — print requirements.md + open tasks
  /spec tasks               — list tasks with done/todo status
  /spec done <task_id>      — mark a task as done
  /spec check               — run drift detection
  /spec reset               — delete all spec files (with confirmation)
  /spec list                — list saved Q42 specs (legacy compatibility)
  /spec load <name>         — show a saved Q42 spec (legacy compatibility)
  /spec <free text>         — generate a Q42-style spec (legacy)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def register(registry: Any) -> None:
    """Register /spec command (overrides Q42 registration)."""
    from lidco.cli.commands.registry import SlashCommand

    async def spec_handler(arg: str = "", **_: Any) -> str:
        parts = arg.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""
        project_dir = Path.cwd()

        # ── new: NL → full pipeline ───────────────────────────────────────
        if sub == "new":
            if not rest:
                return "Usage: `/spec new <description>`"
            return await _spec_new(rest, project_dir)

        # ── show: print requirements + open tasks ─────────────────────────
        if sub == "show":
            return _spec_show(project_dir)

        # ── tasks: list with status ───────────────────────────────────────
        if sub == "tasks":
            return _spec_tasks(project_dir)

        # ── done: mark task complete ──────────────────────────────────────
        if sub == "done":
            if not rest:
                return "Usage: `/spec done <task_id>` (e.g. `/spec done T2`)"
            return _spec_done(rest.strip(), project_dir)

        # ── check: drift detection ────────────────────────────────────────
        if sub == "check":
            return _spec_check(project_dir)

        # ── reset: clear spec files ───────────────────────────────────────
        if sub == "reset":
            return _spec_reset(project_dir, confirmed=rest.strip() == "--yes")

        # ── legacy Q42 compatibility ──────────────────────────────────────
        if sub == "list":
            return await _legacy_list(registry)

        if sub == "load":
            return await _legacy_load(rest, registry)

        # Bare /spec or /spec <free text> → legacy generate
        task = arg.strip()
        if not task:
            return _spec_help()
        return await _legacy_generate(task, registry)

    registry.register(SlashCommand(
        "spec",
        "Spec-driven development: /spec new|show|tasks|done|check|reset",
        spec_handler,
    ))


# ---------------------------------------------------------------------------
# Q68 handlers
# ---------------------------------------------------------------------------

async def _spec_new(description: str, project_dir: Path) -> str:
    if not description.strip():
        return "Usage: `/spec new <description>`"
    from lidco.spec.writer import SpecWriter
    from lidco.spec.design_doc import DesignDocGenerator
    from lidco.spec.task_decomposer import TaskDecomposer

    writer = SpecWriter()
    spec_doc = writer.generate(description, project_dir)

    gen = DesignDocGenerator()
    design = gen.generate(spec_doc, project_dir)

    td = TaskDecomposer()
    tasks = td.decompose(design, project_dir)

    lines = [
        f"**Spec created:** {spec_doc.title}",
        "",
        f"Requirements → `.lidco/spec/requirements.md`",
        f"Design       → `.lidco/spec/design.md`",
        f"Tasks        → `.lidco/spec/tasks.md`",
        "",
        f"**{len(tasks)} tasks generated:**",
    ]
    for t in tasks:
        status = "[x]" if t.done else "[ ]"
        lines.append(f"  {status} {t.id}: {t.title}")
    return "\n".join(lines)


def _spec_show(project_dir: Path) -> str:
    from lidco.spec.writer import SpecWriter
    from lidco.spec.task_decomposer import TaskDecomposer

    writer = SpecWriter()
    spec = writer.load(project_dir)
    if spec is None:
        return "No spec found. Run `/spec new <description>` to create one."

    td = TaskDecomposer()
    tasks = td.load(project_dir)
    open_tasks = [t for t in tasks if not t.done]
    done_tasks = [t for t in tasks if t.done]

    lines = [
        f"# {spec.title}",
        "",
        spec.overview,
        "",
        f"**Acceptance Criteria ({len(spec.acceptance_criteria)}):**",
    ]
    for i, ac in enumerate(spec.acceptance_criteria, 1):
        lines.append(f"  {i}. {ac}")
    if tasks:
        lines += [
            "",
            f"**Tasks: {len(done_tasks)}/{len(tasks)} done**",
        ]
        for t in open_tasks:
            lines.append(f"  [ ] {t.id}: {t.title}")
        for t in done_tasks:
            lines.append(f"  [x] {t.id}: {t.title}")
    return "\n".join(lines)


def _spec_tasks(project_dir: Path) -> str:
    from lidco.spec.task_decomposer import TaskDecomposer
    td = TaskDecomposer()
    tasks = td.load(project_dir)
    if not tasks:
        return "No tasks found. Run `/spec new <description>` first."
    lines = [f"**Tasks ({len(tasks)}):**", ""]
    for t in tasks:
        status = "[x]" if t.done else "[ ]"
        deps = f" ← {', '.join(t.depends_on)}" if t.depends_on else ""
        lines.append(f"  {status} **{t.id}**: {t.title}{deps}")
        if t.description:
            lines.append(f"       {t.description}")
    return "\n".join(lines)


def _spec_done(task_id: str, project_dir: Path) -> str:
    from lidco.spec.task_decomposer import TaskDecomposer
    td = TaskDecomposer()
    if td.mark_done(task_id, project_dir):
        return f"Task `{task_id}` marked as done."
    return f"Task `{task_id}` not found. Use `/spec tasks` to list IDs."


def _spec_check(project_dir: Path) -> str:
    from lidco.spec.drift_detector import DriftDetector
    det = DriftDetector()
    report = det.check(project_dir)
    return report.to_markdown()


def _spec_reset(project_dir: Path, confirmed: bool) -> str:
    if not confirmed:
        return (
            "This will delete `.lidco/spec/requirements.md`, `design.md`, and `tasks.md`.\n"
            "Run `/spec reset --yes` to confirm."
        )
    spec_dir = project_dir / ".lidco" / "spec"
    deleted = []
    for fname in ("requirements.md", "design.md", "tasks.md"):
        p = spec_dir / fname
        if p.exists():
            p.unlink()
            deleted.append(fname)
    if deleted:
        return f"Deleted: {', '.join(deleted)}"
    return "No spec files found."


def _spec_help() -> str:
    return (
        "**Spec-driven development pipeline**\n\n"
        "- `/spec new <description>` — generate requirements + design + tasks\n"
        "- `/spec show` — print current spec and task status\n"
        "- `/spec tasks` — list tasks with done/todo\n"
        "- `/spec done <id>` — mark task done (e.g. `/spec done T2`)\n"
        "- `/spec check` — detect spec drift\n"
        "- `/spec reset --yes` — delete all spec files\n"
    )


# ---------------------------------------------------------------------------
# Legacy Q42 compatibility
# ---------------------------------------------------------------------------

async def _legacy_list(registry: Any) -> str:
    try:
        session = registry._session
        from lidco.tdd.spec_writer import SpecWriter as Q42Writer
        writer = Q42Writer(session)
        specs = writer.list_specs()
        if not specs:
            return "No specs saved yet. Use `/spec new <description>` to generate one."
        lines = ["**Saved specifications:**\n"]
        for s in specs:
            lines.append(f"  · `{s['name']}` — {s['goal'][:60]}")
        return "\n".join(lines)
    except Exception as exc:
        return f"(legacy spec list unavailable: {exc})"


async def _legacy_load(name: str, registry: Any) -> str:
    if not name:
        return "Usage: `/spec load <name>`"
    try:
        session = registry._session
        from lidco.tdd.spec_writer import SpecWriter as Q42Writer
        writer = Q42Writer(session)
        spec = writer.load(name)
        if spec is None:
            return f"Spec `{name}` not found."
        return f"**Spec: {spec.goal}**\n\n{spec.content[:2000]}"
    except Exception as exc:
        return f"(legacy spec load unavailable: {exc})"


async def _legacy_generate(task: str, registry: Any) -> str:
    try:
        session = registry._session
        from lidco.tdd.spec_writer import SpecWriter as Q42Writer
        writer = Q42Writer(session)
        spec = await writer.generate(task)
        path = writer.save(spec)
        return f"**Specification generated** → saved to `{path}`\n\n{spec.content[:3000]}"
    except Exception as exc:
        return f"(legacy spec generate unavailable: {exc})\n\nTip: use `/spec new <description>` instead."
