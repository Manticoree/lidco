"""Hunk — represents a single diff hunk."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Hunk:
    index: int
    header: str
    lines: list[str]

    @property
    def added_lines(self) -> list[str]:
        return [l[1:] for l in self.lines if l.startswith("+")]

    @property
    def removed_lines(self) -> list[str]:
        return [l[1:] for l in self.lines if l.startswith("-")]

    def __str__(self) -> str:
        return self.header + "\n" + "\n".join(self.lines)
