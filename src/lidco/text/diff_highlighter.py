"""Q137 — TextDiffHighlighter: character and word level diffs."""
from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class DiffSegment:
    """A segment of a diff."""

    text: str
    kind: str  # "equal", "insert", "delete", "replace"


class TextDiffHighlighter:
    """Highlight differences between two strings."""

    def highlight(self, old: str, new: str) -> list[DiffSegment]:
        """Character-level diff between *old* and *new*."""
        matcher = difflib.SequenceMatcher(None, old, new)
        segments: list[DiffSegment] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                segments.append(DiffSegment(text=old[i1:i2], kind="equal"))
            elif tag == "replace":
                segments.append(DiffSegment(text=old[i1:i2], kind="delete"))
                segments.append(DiffSegment(text=new[j1:j2], kind="insert"))
            elif tag == "delete":
                segments.append(DiffSegment(text=old[i1:i2], kind="delete"))
            elif tag == "insert":
                segments.append(DiffSegment(text=new[j1:j2], kind="insert"))
        return segments

    def word_diff(self, old: str, new: str) -> list[DiffSegment]:
        """Word-level diff between *old* and *new*."""
        old_words = old.split()
        new_words = new.split()
        matcher = difflib.SequenceMatcher(None, old_words, new_words)
        segments: list[DiffSegment] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                segments.append(DiffSegment(text=" ".join(old_words[i1:i2]), kind="equal"))
            elif tag == "replace":
                segments.append(DiffSegment(text=" ".join(old_words[i1:i2]), kind="delete"))
                segments.append(DiffSegment(text=" ".join(new_words[j1:j2]), kind="insert"))
            elif tag == "delete":
                segments.append(DiffSegment(text=" ".join(old_words[i1:i2]), kind="delete"))
            elif tag == "insert":
                segments.append(DiffSegment(text=" ".join(new_words[j1:j2]), kind="insert"))
        return segments

    def format_inline(self, segments: list[DiffSegment]) -> str:
        """Format segments as ``[-old-]{+new+}`` inline notation."""
        parts: list[str] = []
        for seg in segments:
            if seg.kind == "equal":
                parts.append(seg.text)
            elif seg.kind == "delete":
                parts.append(f"[-{seg.text}-]")
            elif seg.kind == "insert":
                parts.append(f"{{+{seg.text}+}}")
            elif seg.kind == "replace":
                parts.append(f"[-{seg.text}-]")
        return "".join(parts)

    def stats(self, segments: list[DiffSegment]) -> dict:
        """Count segment kinds."""
        counts = {"inserts": 0, "deletes": 0, "replaces": 0, "unchanged": 0}
        for seg in segments:
            if seg.kind == "equal":
                counts["unchanged"] += 1
            elif seg.kind == "insert":
                counts["inserts"] += 1
            elif seg.kind == "delete":
                counts["deletes"] += 1
            elif seg.kind == "replace":
                counts["replaces"] += 1
        return counts
