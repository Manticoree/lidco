"""CLAUDE.md and .claude/ convention support (Task 954)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class CCProjectConfig:
    """Aggregated Claude Code project configuration."""

    instructions: str = ""
    settings: dict = field(default_factory=dict)
    commands: list[dict] = field(default_factory=list)
    hooks: list[dict] = field(default_factory=list)
    mcp_servers: list[dict] = field(default_factory=list)


def _default_read(path: str) -> str | None:
    """Read a file, returning *None* if it does not exist."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def scan_claude_dir(
    project_dir: str,
    read_fn: Callable[[str], str | None] | None = None,
) -> CCProjectConfig:
    """Scan a project directory for Claude Code conventions.

    Parameters
    ----------
    project_dir:
        Root of the project to scan.
    read_fn:
        Injectable file reader ``(path) -> str | None``.  Defaults to real
        filesystem read.
    """
    if read_fn is None:
        read_fn = _default_read

    config = CCProjectConfig()

    # --- Instructions: CLAUDE.md ---
    # Check root, then .claude/ subdirectory
    for candidate in [
        os.path.join(project_dir, "CLAUDE.md"),
        os.path.join(project_dir, ".claude", "CLAUDE.md"),
    ]:
        content = read_fn(candidate)
        if content is not None:
            config.instructions = content
            break

    # --- Settings: .claude/settings.json ---
    settings_path = os.path.join(project_dir, ".claude", "settings.json")
    settings_content = read_fn(settings_path)
    if settings_content is not None:
        try:
            config.settings = json.loads(settings_content)
        except (json.JSONDecodeError, ValueError):
            config.settings = {}

    # --- Local overrides: .claude/settings.local.json ---
    local_path = os.path.join(project_dir, ".claude", "settings.local.json")
    local_content = read_fn(local_path)
    if local_content is not None:
        try:
            local_data = json.loads(local_content)
            if isinstance(local_data, dict):
                config.settings = {**config.settings, **local_data}
        except (json.JSONDecodeError, ValueError):
            pass

    # --- MCP Servers from settings ---
    mcp_raw = config.settings.get("mcpServers", {})
    if isinstance(mcp_raw, dict):
        for name, srv_cfg in mcp_raw.items():
            entry = {"name": name}
            if isinstance(srv_cfg, dict):
                entry.update(srv_cfg)
            config.mcp_servers.append(entry)

    # --- Hooks from settings ---
    hooks_raw = config.settings.get("hooks", {})
    if isinstance(hooks_raw, dict):
        for event_name, hook_list in hooks_raw.items():
            if isinstance(hook_list, list):
                for h in hook_list:
                    entry = {"event": event_name}
                    if isinstance(h, dict):
                        entry.update(h)
                    elif isinstance(h, str):
                        entry["command"] = h
                    config.hooks.append(entry)

    # --- Custom commands: .claude/commands/ ---
    commands_dir = os.path.join(project_dir, ".claude", "commands")
    # List md files via read_fn by trying known patterns
    # Since we don't have a listdir injectable, try common approach:
    # We'll use os.listdir if real FS, or the caller should populate via read_fn
    try:
        if os.path.isdir(commands_dir):
            for fname in sorted(os.listdir(commands_dir)):
                if fname.endswith(".md"):
                    cmd_content = read_fn(os.path.join(commands_dir, fname))
                    cmd_name = fname[:-3]  # strip .md
                    config.commands.append({
                        "name": cmd_name,
                        "content": cmd_content or "",
                    })
    except OSError:
        pass

    return config
