"""Change Explainer — semantic change description (Q177)."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChangeDetail:
    """A single semantic change."""

    kind: str  # "add", "remove", "modify", "rename"
    description: str
    line_range: tuple[int, int]  # (start, end) 1-based


@dataclass
class ChangeExplanation:
    """Overall explanation of changes between two texts."""

    summary: str
    changes: list[ChangeDetail] = field(default_factory=list)
    intent: str = "unknown"  # "refactor", "bugfix", "feature", "cleanup"


def _classify_intent(changes: list[ChangeDetail]) -> str:
    """Heuristic intent classification from change details."""
    kinds = [c.kind for c in changes]
    descs = " ".join(c.description.lower() for c in changes)

    # Check for rename patterns
    if all(k == "rename" for k in kinds):
        return "refactor"

    # Bug-fix signals
    fix_signals = ["fix", "bug", "error", "exception", "handle", "check", "guard"]
    if any(sig in descs for sig in fix_signals):
        return "bugfix"

    # Purely additive → feature
    if all(k == "add" for k in kinds):
        return "feature"

    # Purely removals → cleanup
    if all(k == "remove" for k in kinds):
        return "cleanup"

    # Mixed adds and modifies → feature
    add_count = kinds.count("add")
    if add_count > len(kinds) // 2:
        return "feature"

    return "refactor"


def _detect_rename(removed_lines: list[str], added_lines: list[str]) -> str | None:
    """Detect simple renames (identical structure, different name)."""
    if len(removed_lines) != len(added_lines):
        return None

    for old, new in zip(removed_lines, added_lines):
        ratio = difflib.SequenceMatcher(None, old.strip(), new.strip()).ratio()
        if ratio < 0.5:
            return None

    # Find what changed
    old_words = set(" ".join(removed_lines).split())
    new_words = set(" ".join(added_lines).split())
    removed_words = old_words - new_words
    added_words = new_words - old_words

    if len(removed_words) <= 3 and len(added_words) <= 3 and removed_words and added_words:
        return f"Renamed {', '.join(sorted(removed_words))} -> {', '.join(sorted(added_words))}"
    return None


class ChangeExplainer:
    """Explains what changed between two texts."""

    def explain(self, old_text: str, new_text: str) -> ChangeExplanation:
        """Analyze changes and produce an explanation."""
        if old_text == new_text:
            return ChangeExplanation(summary="No changes detected.", changes=[], intent="unknown")

        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()

        if not old_text.strip():
            return ChangeExplanation(
                summary=f"New content added ({len(new_lines)} lines).",
                changes=[
                    ChangeDetail("add", f"Added {len(new_lines)} lines of new content", (1, max(len(new_lines), 1)))
                ],
                intent="feature",
            )

        if not new_text.strip():
            return ChangeExplanation(
                summary=f"All content removed ({len(old_lines)} lines).",
                changes=[
                    ChangeDetail("remove", f"Removed {len(old_lines)} lines", (1, max(len(old_lines), 1)))
                ],
                intent="cleanup",
            )

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        changes: list[ChangeDetail] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue

            if tag == "replace":
                removed = old_lines[i1:i2]
                added = new_lines[j1:j2]

                rename = _detect_rename(removed, added)
                if rename:
                    changes.append(ChangeDetail("rename", rename, (j1 + 1, j2)))
                else:
                    changes.append(
                        ChangeDetail(
                            "modify",
                            f"Modified {i2 - i1} line(s) at old lines {i1 + 1}-{i2}",
                            (j1 + 1, j2),
                        )
                    )
            elif tag == "delete":
                changes.append(
                    ChangeDetail(
                        "remove",
                        f"Removed {i2 - i1} line(s) at old lines {i1 + 1}-{i2}",
                        (i1 + 1, i2),
                    )
                )
            elif tag == "insert":
                changes.append(
                    ChangeDetail(
                        "add",
                        f"Added {j2 - j1} line(s) at new lines {j1 + 1}-{j2}",
                        (j1 + 1, j2),
                    )
                )

        intent = _classify_intent(changes) if changes else "unknown"

        adds = sum(1 for c in changes if c.kind == "add")
        removes = sum(1 for c in changes if c.kind == "remove")
        modifies = sum(1 for c in changes if c.kind == "modify")
        renames = sum(1 for c in changes if c.kind == "rename")

        parts: list[str] = []
        if adds:
            parts.append(f"{adds} addition(s)")
        if removes:
            parts.append(f"{removes} removal(s)")
        if modifies:
            parts.append(f"{modifies} modification(s)")
        if renames:
            parts.append(f"{renames} rename(s)")

        summary = f"{len(changes)} change(s): {', '.join(parts)}. Intent: {intent}."

        return ChangeExplanation(summary=summary, changes=changes, intent=intent)
