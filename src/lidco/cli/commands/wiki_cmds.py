"""Q69 — /wiki and /ask commands: codebase documentation + Q&A."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def register(registry: Any) -> None:
    from lidco.cli.commands.registry import SlashCommand

    # ── /wiki ─────────────────────────────────────────────────────────────────

    async def wiki_handler(arg: str = "", **_: Any) -> str:
        parts = arg.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1] if len(parts) > 1 else ""
        project_dir = Path.cwd()

        if sub == "generate":
            return _wiki_generate(rest or ".", project_dir)
        if sub == "show":
            return _wiki_show(rest, project_dir)
        if sub == "status":
            return _wiki_status(project_dir)
        if sub == "refresh":
            return _wiki_refresh(project_dir)
        if sub == "export":
            return _wiki_export(rest, project_dir)

        return (
            "**Wiki commands:**\n"
            "- `/wiki generate [path]` — generate wiki for module or project\n"
            "- `/wiki show <module>` — display wiki page\n"
            "- `/wiki status` — modules with/without wiki\n"
            "- `/wiki refresh` — regenerate stale pages\n"
            "- `/wiki export [dir]` — export to directory\n"
        )

    registry.register(SlashCommand(
        "wiki",
        "Codebase wiki: /wiki generate|show|status|refresh|export",
        wiki_handler,
    ))

    # ── /ask ──────────────────────────────────────────────────────────────────

    async def ask_handler(arg: str = "", **_: Any) -> str:
        question = arg.strip()
        if not question:
            return (
                "**Usage:** `/ask <question>`\n\n"
                "Examples:\n"
                "- `/ask what does the auth flow do?`\n"
                "- `/ask how is the session managed?`\n"
                "- `/ask where are tools registered?`\n"
            )
        return _ask_question(question, Path.cwd())

    registry.register(SlashCommand(
        "ask",
        "Ask a question about the codebase",
        ask_handler,
    ))


# ---------------------------------------------------------------------------
# Wiki handlers
# ---------------------------------------------------------------------------

def _wiki_generate(path: str, project_dir: Path) -> str:
    from lidco.wiki.generator import WikiGenerator
    gen = WikiGenerator()

    if path in (".", ""):
        # Generate for all Python source files
        count = 0
        for p in (project_dir / "src").rglob("*.py") if (project_dir / "src").exists() else project_dir.rglob("*.py"):
            if "__pycache__" in str(p):
                continue
            try:
                rel = str(p.relative_to(project_dir))
                gen.generate_module(rel, project_dir)
                count += 1
            except Exception:
                pass
        return f"Generated wiki for {count} modules → `.lidco/wiki/`"

    try:
        page = gen.generate_module(path, project_dir)
        return f"**Wiki: {page.module_path}**\n\n{page.summary}"
    except Exception as exc:
        return f"Failed to generate wiki for `{path}`: {exc}"


def _wiki_show(module: str, project_dir: Path) -> str:
    if not module:
        return "Usage: `/wiki show <module_path>`"
    from lidco.wiki.generator import WikiGenerator
    gen = WikiGenerator()
    page = gen.load(module, project_dir)
    if page is None:
        return f"No wiki page for `{module}`. Run `/wiki generate {module}` first."
    return page.to_markdown()[:3000]


def _wiki_status(project_dir: Path) -> str:
    wiki_dir = project_dir / ".lidco" / "wiki"
    existing = {p.stem for p in wiki_dir.glob("*.md")} if wiki_dir.exists() else set()
    src_dir = project_dir / "src"
    if not src_dir.exists():
        src_dir = project_dir

    all_modules = [
        str(p.relative_to(project_dir))
        for p in src_dir.rglob("*.py")
        if "__pycache__" not in str(p) and not p.name.startswith("_")
    ]

    lines = [f"**Wiki status** ({len(existing)}/{len(all_modules)} modules documented)\n"]
    documented = []
    missing = []
    for m in all_modules[:20]:
        safe = m.replace("/", "_").replace("\\", "_").replace(".py", "")
        if safe in existing:
            documented.append(m)
        else:
            missing.append(m)

    if documented:
        lines.append(f"Documented ({len(documented)}):")
        for m in documented[:5]:
            lines.append(f"  [ok] {m}")
        if len(documented) > 5:
            lines.append(f"  ... +{len(documented)-5} more")

    if missing:
        lines.append(f"\nMissing ({len(missing)}):")
        for m in missing[:5]:
            lines.append(f"  [ ] {m}")
        if len(missing) > 5:
            lines.append(f"  ... +{len(missing)-5} more")

    return "\n".join(lines)


def _wiki_refresh(project_dir: Path) -> str:
    wiki_dir = project_dir / ".lidco" / "wiki"
    if not wiki_dir.exists():
        return "No wiki directory found. Run `/wiki generate` first."

    from lidco.wiki.updater import WikiUpdater
    updater = WikiUpdater()
    # Find all .py files older than their wiki page
    changed = []
    for wiki_page in wiki_dir.glob("*.md"):
        # Recover module path from wiki filename
        module_path = wiki_page.stem.replace("_", "/") + ".py"
        candidate = project_dir / module_path
        if candidate.exists():
            wiki_mtime = wiki_page.stat().st_mtime
            src_mtime = candidate.stat().st_mtime
            if src_mtime > wiki_mtime:
                changed.append(str(candidate.relative_to(project_dir)))

    if not changed:
        return "All wiki pages are up to date."

    # Force update (bypass debounce)
    from lidco.wiki.generator import WikiGenerator
    gen = WikiGenerator()
    updated = []
    for f in changed:
        try:
            gen.generate_module(f, project_dir)
            updated.append(f)
        except Exception:
            pass
    return f"Refreshed {len(updated)} wiki pages: {', '.join(updated[:5])}"


def _wiki_export(output_dir_str: str, project_dir: Path) -> str:
    from lidco.wiki.exporter import WikiExporter
    output_dir = Path(output_dir_str) if output_dir_str else project_dir / "docs" / "wiki"
    exporter = WikiExporter()
    count = exporter.export(project_dir, output_dir)
    if count == 0:
        return "No wiki pages to export. Run `/wiki generate` first."
    return f"Exported {count} wiki pages to `{output_dir}`"


# ---------------------------------------------------------------------------
# Ask handler
# ---------------------------------------------------------------------------

def _ask_question(question: str, project_dir: Path) -> str:
    from lidco.wiki.qa import CodebaseQA
    qa = CodebaseQA()
    answer = qa.ask(question, project_dir)
    lines = [f"**Answer:** {answer.answer}"]
    if answer.sources:
        lines += ["", f"**Sources** (confidence: {answer.confidence:.0%}):"]
        for src in answer.sources[:5]:
            lines.append(f"  - `{src}`")
    return "\n".join(lines)
