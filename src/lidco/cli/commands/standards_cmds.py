"""Slash commands for coding standards enforcement."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

# Module-level lazy-init enforcer
_enforcer: Any = None


def _get_enforcer() -> Any:
    global _enforcer
    if _enforcer is None:
        try:
            from lidco.standards.enforcer import StandardsEnforcer
            _enforcer = StandardsEnforcer()
            _enforcer.load_defaults()
        except Exception:
            _enforcer = None
    return _enforcer


# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------

async def standards_check_handler(args: str = "") -> str:
    """/standards check — run standards check on staged files."""
    result = pre_commit_check()
    if not result:
        return "Standards check passed. No violations found."
    return f"Standards violations found:\n{result}"


async def standards_rules_handler(args: str = "") -> str:
    """/standards rules — list loaded rules."""
    enforcer = _get_enforcer()
    if enforcer is None:
        return "Standards enforcer unavailable."
    rules = enforcer.list_rules()
    if not rules:
        return "No rules loaded."
    lines = [f"Loaded rules ({len(rules)}):"]
    for r in rules:
        lines.append(f"  [{r.severity.upper()}] {r.id}: {r.name}")
    return "\n".join(lines)


async def standards_add_handler(args: str = "") -> str:
    """/standards add <yaml_path> — load additional rules from a YAML file."""
    yaml_path = args.strip()
    if not yaml_path:
        return "Usage: /standards add <yaml_path>"
    enforcer = _get_enforcer()
    if enforcer is None:
        return "Standards enforcer unavailable."
    added = enforcer.load_yaml(yaml_path)
    if added == 0:
        return f"No rules loaded from '{yaml_path}'. Check path and file format."
    return f"Loaded {added} rule(s) from '{yaml_path}'."


async def standards_init_handler(args: str = "") -> str:
    """/standards init — create .lidco/standards.yaml with defaults."""
    try:
        from lidco.standards.enforcer import StandardsEnforcer
        output_path = Path(".lidco") / "standards.yaml"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = StandardsEnforcer.default_yaml_content()
        output_path.write_text(content, encoding="utf-8")
        return f"Created {output_path} with default rules."
    except Exception as exc:
        return f"Failed to create standards.yaml: {exc}"


# ------------------------------------------------------------------
# Pre-commit helper
# ------------------------------------------------------------------

def pre_commit_check(project_dir: str | Path | None = None) -> str:
    """Check staged files against standards rules. Returns violation text or ''."""
    try:
        cwd = str(project_dir) if project_dir else None
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        staged_files = [f for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        staged_files = []

    if not staged_files:
        return ""

    enforcer = _get_enforcer()
    if enforcer is None:
        return ""

    files_content: dict[str, str] = {}
    for path_str in staged_files:
        p = Path(path_str)
        if p.is_file():
            try:
                files_content[path_str] = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    if not files_content:
        return ""

    violations = enforcer.check_diff(files_content)
    if not violations:
        return ""

    lines = []
    for v in violations:
        lines.append(f"{v.file}:{v.line} [{v.severity.upper()}] {v.rule_id}: {v.message}")
    return "\n".join(lines)


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_standards_commands(registry: Any) -> None:
    """Register /standards slash commands."""
    from lidco.cli.commands.registry import SlashCommand

    registry.register(SlashCommand(
        "standards check",
        "Run standards check on staged files",
        standards_check_handler,
    ))
    registry.register(SlashCommand(
        "standards rules",
        "List loaded coding standards rules",
        standards_rules_handler,
    ))
    registry.register(SlashCommand(
        "standards add",
        "Load additional rules from a YAML file",
        standards_add_handler,
    ))
    registry.register(SlashCommand(
        "standards init",
        "Create .lidco/standards.yaml with default rules",
        standards_init_handler,
    ))
