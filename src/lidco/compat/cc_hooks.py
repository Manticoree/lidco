"""Claude Code hooks adapter (Task 955)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CCHook:
    """Parsed Claude Code hook entry."""

    event: str = ""
    command: str = ""
    matcher: str | None = None
    timeout: int = 30


# Event name mapping from Claude Code to LIDCO
_CC_EVENT_MAP: dict[str, str] = {
    "PreToolUse": "pre_tool_use",
    "pretooluse": "pre_tool_use",
    "PostToolUse": "post_tool_use",
    "posttooluse": "post_tool_use",
    "Stop": "session_end",
    "stop": "session_end",
    "Notification": "notification",
    "notification": "notification",
}


def parse_cc_hooks(settings: dict[str, Any]) -> list[CCHook]:
    """Parse the ``hooks`` section from Claude Code settings.

    Parameters
    ----------
    settings:
        The full settings dict (or just the hooks sub-dict).  Accepts either
        ``{"hooks": {...}}`` or ``{"PreToolUse": [...], ...}`` directly.
    """
    if not isinstance(settings, dict):
        raise TypeError("settings must be a dict")

    hooks_section = settings.get("hooks", settings)
    if not isinstance(hooks_section, dict):
        return []

    # If the dict has a "hooks" key that is itself a dict, use that
    # Otherwise treat the entire dict as the hooks section
    # But avoid re-dereferencing if we already extracted it
    if "hooks" in hooks_section and isinstance(hooks_section["hooks"], dict):
        hooks_section = hooks_section["hooks"]

    result: list[CCHook] = []
    for event_name, hook_list in hooks_section.items():
        if not isinstance(hook_list, list):
            continue
        for entry in hook_list:
            if isinstance(entry, str):
                result.append(CCHook(
                    event=event_name,
                    command=entry,
                ))
            elif isinstance(entry, dict):
                result.append(CCHook(
                    event=event_name,
                    command=str(entry.get("command", "")),
                    matcher=entry.get("matcher") if entry.get("matcher") else None,
                    timeout=int(entry.get("timeout", 30)),
                ))
    return result


def to_lidco_hooks(hooks: list[CCHook]) -> list[dict[str, Any]]:
    """Convert parsed Claude Code hooks to LIDCO hook format."""
    result: list[dict[str, Any]] = []
    for h in hooks:
        lidco_event = _CC_EVENT_MAP.get(h.event, h.event.lower())
        entry: dict[str, Any] = {
            "event": lidco_event,
            "command": h.command,
        }
        if h.matcher is not None:
            entry["matcher"] = h.matcher
        if h.timeout != 30:
            entry["timeout"] = h.timeout
        result.append(entry)
    return result
