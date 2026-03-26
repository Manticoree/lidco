"""
AI Git Blame — CodeSee-style LLM-enhanced git history analysis.

Combines `git log` + `git blame` output with an LLM explanation to answer:
  "Why does this code exist and how did it evolve?"

The LLM callback is injected at construction time (no hard dependency on any
particular model provider), keeping this module stdlib-only in tests.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BlameEntry:
    """One annotated block from `git blame`."""
    file: str
    line_start: int
    line_end: int
    author: str
    commit: str
    date: str
    message: str
    code_lines: list[str] = field(default_factory=list)
    ai_explanation: str = ""


@dataclass
class FileHistory:
    """Summarised history for a single file."""
    file: str
    commits: list[dict[str, str]]  # [{hash, author, date, message}, ...]
    ai_summary: str = ""


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run_git(args: list[str], cwd: str) -> str:
    try:
        proc = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=15,
        )
        return proc.stdout
    except Exception:
        return ""


def _parse_blame(raw: str, filepath: str) -> list[BlameEntry]:
    """
    Parse `git blame --porcelain` output into BlameEntry objects.

    Groups consecutive lines with the same commit hash.
    """
    entries: list[BlameEntry] = []
    current_hash = ""
    current_meta: dict[str, str] = {}
    current_lines: list[str] = []
    current_line_num = 0

    for line in raw.splitlines():
        # Header: "<40-char hash> <orig-line> <final-line> [<group-size>]"
        m = re.match(r"^([0-9a-f]{40})\s+\d+\s+(\d+)(?:\s+\d+)?$", line)
        if m:
            commit_hash = m.group(1)
            lineno = int(m.group(2))
            if commit_hash != current_hash:
                if current_hash and current_lines:
                    start = current_line_num - len(current_lines) + 1
                    entries.append(BlameEntry(
                        file=filepath,
                        line_start=start,
                        line_end=current_line_num,
                        author=current_meta.get("author", ""),
                        commit=current_hash,
                        date=current_meta.get("author-time", ""),
                        message=current_meta.get("summary", ""),
                        code_lines=current_lines[:],
                    ))
                current_hash = commit_hash
                current_meta = {}
                current_lines = []
            current_line_num = lineno
            continue

        # Meta lines
        if line.startswith("author "):
            current_meta["author"] = line[7:].strip()
        elif line.startswith("author-time "):
            current_meta["author-time"] = line[12:].strip()
        elif line.startswith("summary "):
            current_meta["summary"] = line[8:].strip()
        elif line.startswith("\t"):
            current_lines.append(line[1:])

    if current_hash and current_lines:
        start = current_line_num - len(current_lines) + 1
        entries.append(BlameEntry(
            file=filepath,
            line_start=start,
            line_end=current_line_num,
            author=current_meta.get("author", ""),
            commit=current_hash,
            date=current_meta.get("author-time", ""),
            message=current_meta.get("summary", ""),
            code_lines=current_lines[:],
        ))

    return entries


def _parse_log(raw: str) -> list[dict[str, str]]:
    """Parse `git log --format=...` output into list of commit dicts."""
    commits = []
    for block in raw.strip().split("\x1e"):
        block = block.strip()
        if not block:
            continue
        parts = block.split("\x1f")
        if len(parts) >= 4:
            commits.append({
                "hash": parts[0].strip(),
                "author": parts[1].strip(),
                "date": parts[2].strip(),
                "message": parts[3].strip(),
            })
    return commits


# ---------------------------------------------------------------------------
# AIBlameAnalyzer
# ---------------------------------------------------------------------------

class AIBlameAnalyzer:
    """
    Combines git blame + git log with optional LLM explanations.

    Parameters
    ----------
    project_root : str | None
        Root directory of the git repository.
    llm_callback : Callable[[str], str] | None
        Function that accepts a prompt and returns an LLM response.
        When None, ai_explanation fields are left empty.
    max_entries : int
        Cap on the number of blame entries to pass to LLM (avoids huge prompts).
    """

    _LOG_FORMAT = "%H%x1f%an%x1f%ai%x1f%s%x1e"

    def __init__(
        self,
        project_root: str | None = None,
        llm_callback: Callable[[str], str] | None = None,
        max_entries: int = 20,
    ) -> None:
        self._root = str(Path(project_root) if project_root else Path.cwd())
        self._llm = llm_callback
        self._max_entries = max_entries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_file(
        self,
        path: str,
        line_range: tuple[int, int] | None = None,
    ) -> list[BlameEntry]:
        """
        Return blame entries for *path*, optionally restricted to *line_range*
        (1-based inclusive tuple, e.g. (10, 25)).

        Each entry includes an AI explanation when an LLM callback is provided.
        """
        args = ["blame", "--porcelain", path]
        if line_range:
            args = ["blame", "--porcelain", f"-L{line_range[0]},{line_range[1]}", path]

        raw = _run_git(args, self._root)
        entries = _parse_blame(raw, path)

        if self._llm and entries:
            entries = self._explain_entries(entries[: self._max_entries])

        return entries

    def explain_history(self, path: str, max_commits: int = 20) -> str:
        """
        Return an LLM-generated narrative explaining how and why *path*
        evolved over time.  Falls back to a plain commit list when no LLM.
        """
        raw = _run_git(
            ["log", f"--format={self._LOG_FORMAT}", f"-{max_commits}", "--", path],
            self._root,
        )
        commits = _parse_log(raw)

        if not self._llm:
            lines = [f"{c['date'][:10]}  {c['author']}: {c['message']}" for c in commits]
            return "\n".join(lines) or "(no history)"

        prompt = self._build_history_prompt(path, commits)
        return self._llm(prompt)

    def find_introduction(self, symbol: str, path: str | None = None) -> BlameEntry | None:
        """
        Find the commit that first introduced *symbol* (function / class name).

        Searches git log for the commit where the symbol appears in the diff.
        Returns the first matching BlameEntry or None.
        """
        args = [
            "log",
            f"--format={self._LOG_FORMAT}",
            "-S", symbol,
            "--diff-filter=A",
        ]
        if path:
            args += ["--", path]

        raw = _run_git(args, self._root)
        commits = _parse_log(raw)
        if not commits:
            # Try without diff-filter restriction
            args2 = ["log", f"--format={self._LOG_FORMAT}", "-S", symbol]
            if path:
                args2 += ["--", path]
            raw = _run_git(args2, self._root)
            commits = _parse_log(raw)

        if not commits:
            return None

        c = commits[0]
        entry = BlameEntry(
            file=path or "",
            line_start=0,
            line_end=0,
            author=c["author"],
            commit=c["hash"],
            date=c["date"],
            message=c["message"],
        )

        if self._llm:
            prompt = (
                f"The symbol `{symbol}` was first introduced in commit "
                f"{c['hash'][:8]} by {c['author']} with message: \"{c['message']}\". "
                f"In 1–2 sentences, explain why this symbol was likely introduced."
            )
            entry.ai_explanation = self._llm(prompt)

        return entry

    def get_file_history(self, path: str, max_commits: int = 30) -> FileHistory:
        """Return a FileHistory dataclass with commits + AI summary."""
        raw = _run_git(
            ["log", f"--format={self._LOG_FORMAT}", f"-{max_commits}", "--", path],
            self._root,
        )
        commits = _parse_log(raw)
        ai_summary = ""
        if self._llm and commits:
            ai_summary = self._llm(self._build_history_prompt(path, commits))
        return FileHistory(file=path, commits=commits, ai_summary=ai_summary)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _explain_entries(self, entries: list[BlameEntry]) -> list[BlameEntry]:
        """Batch-explain blame entries using LLM."""
        if not self._llm:
            return entries

        result = []
        for entry in entries:
            snippet = "\n".join(entry.code_lines[:5])
            prompt = (
                f"The following code (lines {entry.line_start}–{entry.line_end} "
                f"of `{entry.file}`) was committed by {entry.author} "
                f"with message \"{entry.message}\":\n\n"
                f"```python\n{snippet}\n```\n\n"
                f"In one sentence, explain what this code does and why it exists."
            )
            entry = BlameEntry(
                file=entry.file,
                line_start=entry.line_start,
                line_end=entry.line_end,
                author=entry.author,
                commit=entry.commit,
                date=entry.date,
                message=entry.message,
                code_lines=entry.code_lines,
                ai_explanation=self._llm(prompt),
            )
            result.append(entry)
        return result

    def _build_history_prompt(
        self, path: str, commits: list[dict[str, str]]
    ) -> str:
        lines = [f"- {c['date'][:10]} {c['author']}: {c['message']}" for c in commits]
        history = "\n".join(lines)
        return (
            f"Here is the git history of `{path}`:\n\n{history}\n\n"
            f"In 3–5 sentences, describe how this file evolved, "
            f"what the main changes were, and why they were made."
        )
