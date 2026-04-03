"""CodeActionsProvider — context-aware code actions."""
from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULT_TYPES: list[str] = [
    "extract_function",
    "rename",
    "inline",
    "wrap_try",
    "add_import",
    "remove_unused",
    "toggle_comment",
]


@dataclass(frozen=True)
class CodeAction:
    """A code action definition."""

    name: str
    type: str
    description: str
    applicable_languages: list[str] = field(
        default_factory=lambda: ["python", "javascript"],
    )


class CodeActionsProvider:
    """Provide context-aware code actions."""

    def __init__(self) -> None:
        self._actions: list[CodeAction] = [
            CodeAction("Extract Function", "extract_function", "Extract selection into a new function"),
            CodeAction("Rename Symbol", "rename", "Rename a symbol across scope"),
            CodeAction("Inline Variable", "inline", "Inline a variable usage"),
            CodeAction("Wrap in try/except", "wrap_try", "Wrap lines in try/except block"),
            CodeAction("Add Import", "add_import", "Add an import statement"),
            CodeAction("Remove Unused", "remove_unused", "Remove unused imports/variables"),
            CodeAction("Toggle Comment", "toggle_comment", "Toggle comment on selected lines"),
        ]

    def available_actions(self, language: str = "python") -> list[CodeAction]:
        """Return actions applicable to *language*."""
        return [a for a in self._actions if language in a.applicable_languages]

    def extract_function(self, code: str, start: int, end: int, name: str) -> str:
        """Extract lines *start..end* into a function called *name*."""
        lines = code.splitlines(keepends=True)
        selected = lines[start:end]
        body = "".join(f"    {l}" if not l.startswith("    ") else l for l in selected)
        func = f"def {name}():\n{body}\n"
        remaining = lines[:start] + [f"{name}()\n"] + lines[end:]
        return func + "".join(remaining)

    def rename_symbol(self, code: str, old_name: str, new_name: str) -> str:
        """Replace all occurrences of *old_name* with *new_name*."""
        return code.replace(old_name, new_name)

    def wrap_try(self, code: str, start: int, end: int) -> str:
        """Wrap lines *start..end* in try/except."""
        lines = code.splitlines(keepends=True)
        selected = lines[start:end]
        indented = "".join(f"    {l}" if not l.startswith("    ") else f"    {l}" for l in selected)
        block = f"try:\n{indented}except Exception:\n    pass\n"
        remaining = lines[:start] + [block] + lines[end:]
        return "".join(remaining)

    def add_import(self, code: str, import_line: str) -> str:
        """Add *import_line* at the top of *code*."""
        return import_line.rstrip("\n") + "\n" + code

    def toggle_comment(self, code: str, start: int, end: int, comment_prefix: str = "#") -> str:
        """Toggle comment on lines *start..end*."""
        lines = code.splitlines(keepends=True)
        for i in range(start, min(end, len(lines))):
            stripped = lines[i].lstrip()
            if stripped.startswith(comment_prefix):
                # uncomment
                idx = lines[i].index(comment_prefix)
                after = lines[i][idx + len(comment_prefix):]
                if after.startswith(" "):
                    after = after[1:]
                lines[i] = lines[i][:idx] + after
            else:
                # comment
                idx = len(lines[i]) - len(lines[i].lstrip())
                lines[i] = lines[i][:idx] + comment_prefix + " " + lines[i][idx:]
        return "".join(lines)

    def summary(self) -> dict:
        """Return a summary dict."""
        return {
            "total_actions": len(self._actions),
            "types": [a.type for a in self._actions],
        }
