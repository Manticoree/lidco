"""HookComposer — compose multiple hooks into a single shell script.

Allows ordering, conditional execution, and skip-patterns so that
several HookDefinitions can be merged into one hook file per type.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from lidco.githooks.library import HookDefinition
from lidco.githooks.manager import HookType


@dataclass
class _Entry:
    hook_def: HookDefinition
    order: int = 0
    condition: Optional[str] = None
    skip_patterns: list[str] = field(default_factory=list)


class HookComposer:
    """Build a composite hook script from multiple HookDefinitions."""

    def __init__(self) -> None:
        # keyed by hook_type, then by hook name
        self._entries: Dict[HookType, Dict[str, _Entry]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, hook_def: HookDefinition, order: int = 0) -> None:
        """Add a hook definition with execution order (lower runs first)."""
        bucket = self._entries.setdefault(hook_def.type, {})
        bucket[hook_def.name] = _Entry(hook_def=hook_def, order=order)

    def set_condition(self, hook_name: str, condition: str) -> None:
        """Set a shell condition guard for *hook_name*. Raises KeyError if not found."""
        entry = self._find(hook_name)
        entry.condition = condition

    def skip_pattern(self, hook_name: str, pattern: str) -> None:
        """Add a file-glob skip pattern for *hook_name*. Raises KeyError if not found."""
        entry = self._find(hook_name)
        entry.skip_patterns.append(pattern)

    def composed_hooks(self, hook_type: HookType) -> List[HookDefinition]:
        """Return hook definitions for *hook_type*, sorted by order."""
        bucket = self._entries.get(hook_type, {})
        return [e.hook_def for e in sorted(bucket.values(), key=lambda e: e.order)]

    def compose(self, hook_type: HookType) -> str:
        """Generate a single shell script for *hook_type*."""
        bucket = self._entries.get(hook_type, {})
        if not bucket:
            return "#!/bin/sh\n# No hooks configured.\nexit 0\n"

        lines: list[str] = ["#!/bin/sh", "set -e", ""]
        sorted_entries = sorted(bucket.values(), key=lambda e: e.order)

        for entry in sorted_entries:
            lines.append(f"# --- {entry.hook_def.name} ---")
            # Strip shebang from individual script body
            body = entry.hook_def.script
            body_lines = body.splitlines()
            if body_lines and body_lines[0].startswith("#!"):
                body_lines = body_lines[1:]
            body_text = "\n".join(body_lines).strip()

            if entry.skip_patterns:
                skip_cond = " || ".join(
                    f'echo "$f" | grep -q "{p}"' for p in entry.skip_patterns
                )
                # Wrap in a function that checks skip patterns
                lines.append(f"_skip_{entry.hook_def.name.replace('-', '_')}() {{")
                lines.append("  for f in $(git diff --cached --name-only); do")
                lines.append(f"    if {skip_cond}; then return 0; fi")
                lines.append("  done")
                lines.append("  return 1")
                lines.append("}")

            if entry.condition:
                lines.append(f"if {entry.condition}; then")
                lines.append(f"  {body_text}")
                lines.append("fi")
            elif entry.skip_patterns:
                fn_name = f"_skip_{entry.hook_def.name.replace('-', '_')}"
                lines.append(f"if ! {fn_name}; then")
                lines.append(f"  {body_text}")
                lines.append("fi")
            else:
                lines.append(body_text)

            lines.append("")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find(self, hook_name: str) -> _Entry:
        for bucket in self._entries.values():
            if hook_name in bucket:
                return bucket[hook_name]
        raise KeyError(f"Hook '{hook_name}' not found in composer.")
