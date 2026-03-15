"""Q55/371 — Hunk-level diff approval.

Parses a unified diff into individual hunks and lets the user accept,
skip, or view each one interactively.

Usage::

    hunks = parse_hunks(unified_diff_text)
    approved = approve_hunks_interactive(hunks, console)
    # approved is a subset of hunks the user accepted
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class DiffHunk:
    """A single hunk from a unified diff."""

    file_a: str
    file_b: str
    header: str          # e.g. "@@ -10,6 +10,8 @@"
    lines: list[str]     # context/add/remove lines
    start_a: int = 0
    start_b: int = 0

    def as_text(self) -> str:
        return "\n".join([self.header] + self.lines)


_DIFF_FILE_RE = re.compile(r"^--- (.+)$")
_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def parse_hunks(diff_text: str) -> list[DiffHunk]:
    """Parse a unified diff string into a list of :class:`DiffHunk` objects."""
    hunks: list[DiffHunk] = []
    file_a = file_b = ""
    current_header = ""
    current_lines: list[str] = []
    start_a = start_b = 0

    def _flush() -> None:
        if current_header:
            hunks.append(DiffHunk(
                file_a=file_a,
                file_b=file_b,
                header=current_header,
                lines=list(current_lines),
                start_a=start_a,
                start_b=start_b,
            ))

    for line in diff_text.splitlines():
        if line.startswith("--- "):
            _flush()
            current_header = ""
            current_lines = []
            file_a = line[4:]
        elif line.startswith("+++ "):
            file_b = line[4:]
        elif line.startswith("@@"):
            _flush()
            current_lines = []
            m = _HUNK_HEADER_RE.match(line)
            current_header = line
            if m:
                start_a = int(m.group(1))
                start_b = int(m.group(2))
        elif current_header:
            current_lines.append(line)

    _flush()
    return hunks


def approve_hunks_interactive(
    hunks: Sequence[DiffHunk],
    console: object | None = None,
) -> list[DiffHunk]:
    """Interactively ask the user to accept or skip each hunk.

    Returns only the accepted hunks.

    If *console* is a Rich Console, uses it for coloured output.
    Falls back to plain ``print``/``input`` otherwise.
    """
    if not hunks:
        return []

    def _print(msg: str, style: str = "") -> None:
        if console is not None:
            try:
                console.print(msg, style=style)  # type: ignore[union-attr]
                return
            except Exception:
                pass
        print(msg)

    def _prompt(msg: str) -> str:
        try:
            return input(msg).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "s"

    approved: list[DiffHunk] = []
    total = len(hunks)

    _print(f"\n[bold]Просмотр {total} хук(ов) для одобрения[/bold]")

    for i, hunk in enumerate(hunks, 1):
        _print(f"\n── Хук {i}/{total}: {hunk.file_b} {hunk.header} ──", style="cyan")
        for line in hunk.lines[:40]:  # cap display at 40 lines
            if line.startswith("+"):
                _print(line, style="green")
            elif line.startswith("-"):
                _print(line, style="red")
            else:
                _print(line, style="dim")
        if len(hunk.lines) > 40:
            _print(f"  ... ({len(hunk.lines) - 40} строк скрыто)")

        while True:
            answer = _prompt("[a]ccept / [s]kip / [q]uit: ")
            if answer in ("a", "y", "accept", "да"):
                approved.append(hunk)
                _print("  ✓ Принято", style="bold green")
                break
            elif answer in ("s", "n", "skip", "нет"):
                _print("  ✗ Пропущено", style="dim")
                break
            elif answer in ("q", "quit", "выход"):
                _print("Прерывание одобрения хуков.")
                return approved
            else:
                _print("Введите 'a' (принять), 's' (пропустить) или 'q' (выйти).")

    accepted = len(approved)
    skipped = total - accepted
    _print(f"\n✓ Принято: {accepted}  ✗ Пропущено: {skipped}", style="bold")
    return approved
