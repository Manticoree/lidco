"""WatchAgentTrigger — AI! / AI? comment-based agent triggers in source files."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


_COMMENT_PATTERNS = [
    # Python / Shell
    (re.compile(r"#\s*AI(!|\?)(.*)$"), "#"),
    # C / JS / Go / Rust / Java
    (re.compile(r"//\s*AI(!|\?)(.*)$"), "//"),
    # SQL / Lua / Haskell
    (re.compile(r"--\s*AI(!|\?)(.*)$"), "--"),
]


@dataclass
class AIComment:
    file_path: str
    line_number: int
    instruction: str
    mode: str  # "execute" | "ask"


class WatchAgentTrigger:
    """Scan source files for AI! / AI? comments and invoke agent_fn."""

    def __init__(
        self,
        project_dir: str | Path,
        agent_fn: Callable[[str], str] | None = None,
        patterns: list[str] | None = None,
    ) -> None:
        self._project_dir = Path(project_dir)
        self._agent_fn = agent_fn
        self._patterns = patterns  # reserved for future extension
        self._running = False
        self._last_answers: dict[str, str] = {}  # file -> last agent answer

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Scanning
    # ------------------------------------------------------------------

    def scan_file(self, path: str | Path) -> list[AIComment]:
        """Return all AI! / AI? comments found in *path*."""
        p = Path(path)
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

        comments: list[AIComment] = []
        for i, line in enumerate(lines, start=1):
            for regex, _prefix in _COMMENT_PATTERNS:
                m = regex.search(line)
                if m:
                    marker = m.group(1)  # "!" or "?"
                    instruction = m.group(2).strip()
                    mode = "execute" if marker == "!" else "ask"
                    comments.append(AIComment(
                        file_path=str(p),
                        line_number=i,
                        instruction=instruction,
                        mode=mode,
                    ))
                    break  # only one match per line
        return comments

    def collect_all_comments(
        self, changed_files: list[str | Path]
    ) -> list[AIComment]:
        """Aggregate AI comments from all changed files."""
        result: list[AIComment] = []
        for f in changed_files:
            result.extend(self.scan_file(f))
        return result

    def _build_task_string(self, comments: list[AIComment]) -> str:
        """Format a list of comments into a single task instruction string."""
        parts: list[str] = []
        for c in comments:
            prefix = "EXECUTE" if c.mode == "execute" else "ASK"
            parts.append(
                f"[{prefix}] {c.file_path}:{c.line_number}: {c.instruction}"
            )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process(self, changed_files: list[str | Path]) -> str:
        """Collect comments, invoke agent, patch files. Returns agent output."""
        comments = self.collect_all_comments(changed_files)
        if not comments:
            return ""

        task_str = self._build_task_string(comments)
        answer = ""
        if self._agent_fn is not None:
            try:
                answer = self._agent_fn(task_str)
            except Exception as exc:
                answer = f"[agent error: {exc}]"

        # Post-process files
        execute_files = {c.file_path for c in comments if c.mode == "execute"}
        ask_comments = [c for c in comments if c.mode == "ask"]

        for fp in execute_files:
            self._remove_ai_comments(fp, mode="execute")

        for c in ask_comments:
            self._append_answer(c.file_path, c.line_number, answer)

        return answer

    def _remove_ai_comments(self, file_path: str, mode: str) -> None:
        """Remove AI! (execute) comments from file."""
        p = Path(file_path)
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines(
                keepends=True
            )
        except OSError:
            return

        marker = "!" if mode == "execute" else "?"
        new_lines = []
        for line in lines:
            skip = False
            for regex, _prefix in _COMMENT_PATTERNS:
                m = regex.search(line)
                if m and m.group(1) == marker:
                    skip = True
                    break
            if not skip:
                new_lines.append(line)

        try:
            p.write_text("".join(new_lines), encoding="utf-8")
        except OSError:
            pass

    def _append_answer(self, file_path: str, line_number: int, answer: str) -> None:
        """Append the agent answer as a comment block after the AI? line."""
        p = Path(file_path)
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines(
                keepends=True
            )
        except OSError:
            return

        if line_number < 1 or line_number > len(lines):
            return

        answer_lines = [f"# AI Answer: {line}\n" for line in answer.splitlines()]
        answer_lines.append("# ---\n")

        new_lines = (
            lines[:line_number]
            + answer_lines
            + lines[line_number:]
        )
        try:
            p.write_text("".join(new_lines), encoding="utf-8")
        except OSError:
            pass
