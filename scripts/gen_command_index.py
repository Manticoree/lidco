#!/usr/bin/env python3
"""Generate docs/COMMANDS.md index from commands.py SlashCommand registrations.

Usage: python scripts/gen_command_index.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMMANDS_PY = ROOT / "src/lidco/cli/commands.py"
OUTPUT = ROOT / "docs/COMMANDS.md"

PATTERN = re.compile(r'SlashCommand\("([^"]+)",\s*"([^"]+)"')

CATEGORIES = {
    "core": ["help", "debug", "errors", "health", "status", "clear", "exit", "retry", "undo", "config", "run", "todos"],
    "session": ["session", "fork", "back", "replay", "export", "import", "checkpoint", "profile", "workprofile", "repos"],
    "agents": ["agents", "lock", "unlock", "as", "tdd", "batch", "spec", "best-of", "tdd-mode", "simplify"],
    "git": ["commit", "pr", "conflict", "bisect", "branch", "stash", "checkout", "pr-create", "pr-review", "diff"],
    "context": ["context", "mention", "add-dir", "compact", "model", "theme", "memory", "index", "index-status"],
    "tools": ["note", "alias", "recent", "focus", "pin", "vars", "timing", "snapshot", "watch", "tag", "bookmark", "template", "autosave", "remind"],
    "analysis": ["lint", "search", "arch", "plan", "grep", "summary", "perf-hints", "refactor-suggest", "fix", "bugbot"],
    "skills": ["skills", "snippet", "pipe", "mode"],
    "integrations": ["http", "mcp", "dashboard", "analytics", "cost", "compare-models", "websearch", "webfetch", "image", "voice", "diagram", "screenshot"],
    "permissions": ["permissions", "rules", "decisions", "init", "sandbox"],
}


def categorize(name: str) -> str:
    for cat, names in CATEGORIES.items():
        if name in names:
            return cat
    return "other"


def main():
    text = COMMANDS_PY.read_text(encoding="utf-8")
    # Collect commands, deduplicating by name (last registration wins, matching runtime behaviour)
    seen: dict[str, str] = {}
    for m in PATTERN.finditer(text):
        seen[m.group(1)] = m.group(2)

    commands = list(seen.items())

    by_cat: dict[str, list] = {}
    for name, desc in commands:
        cat = categorize(name)
        by_cat.setdefault(cat, []).append((name, desc))

    lines = ["# LIDCO Slash Commands Index", "", f"Total: {len(commands)} commands", ""]

    cat_order = list(CATEGORIES.keys()) + ["other"]
    for cat in cat_order:
        if cat not in by_cat:
            continue
        lines.append(f"## {cat.capitalize()}")
        lines.append("")
        lines.append("| Command | Description |")
        lines.append("|---------|-------------|")
        for name, desc in sorted(by_cat[cat]):
            lines.append(f"| `/{name}` | {desc} |")
        lines.append("")

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {OUTPUT} with {len(commands)} commands")


if __name__ == "__main__":
    main()
