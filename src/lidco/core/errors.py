"""Session error history — captures tool failures for debugger context."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace as dc_replace
from datetime import datetime, timezone
from typing import Any


def extract_file_hint(traceback_str: str | None) -> str | None:
    """Return the path of the first Python file mentioned in a traceback, or None."""
    if not traceback_str:
        return None
    m = re.search(r'File "([^"]+\.py)"', traceback_str)
    return m.group(1) if m else None


def _compact_args(args: dict[str, Any], max_val_len: int = 200) -> dict[str, Any]:
    """Return a copy of *args* with large string values truncated.

    Long strings are replaced by their first *max_val_len* characters followed
    by a ``"... (N chars)"`` suffix so the caller can see the value type without
    flooding the error context with file content.
    """
    result: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > max_val_len:
            result[k] = v[:max_val_len] + f"... ({len(v)} chars)"
        else:
            result[k] = v
    return result


def _extract_file_lines(path: str, line_no: int, lines_around: int = 20) -> str | None:
    """Read lines_around lines before/after line_no from path.

    Returns a formatted string with line numbers, or None if unreadable.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        start = max(0, line_no - 1 - lines_around)
        end = min(len(all_lines), line_no + lines_around)
        result_lines: list[str] = []
        for i, line in enumerate(all_lines[start:end], start=start + 1):
            marker = ">>>" if i == line_no else "   "
            result_lines.append(f"{i:4d} {marker} {line.rstrip()}")
        return "\n".join(result_lines)
    except OSError:
        return None


@dataclass(frozen=True)
class ErrorRecord:
    """An immutable record of a single tool failure during a session."""

    id: str                         # uuid4 hex
    timestamp: datetime             # UTC
    tool_name: str
    agent_name: str
    error_type: str                 # "tool_error" | "exception" | "timeout"
    message: str
    traceback_str: str | None
    file_hint: str | None           # first "File path.py" found in traceback
    tool_args: dict[str, Any] | None = None   # compacted tool arguments
    occurrence_count: int = 1                  # consecutive duplicate counter
    caused_by_id: str | None = None            # ID of the root-cause ErrorRecord
    is_root_cause: bool = True                 # False if this is a symptom


class ErrorHistory:
    """Ring buffer of recent ErrorRecords — thread-safe via immutable list swaps."""

    def __init__(self, max_size: int = 50) -> None:
        self._max_size = max_size
        self._records: list[ErrorRecord] = []

    def append(self, record: ErrorRecord) -> None:
        """Add *record*, deduplicating consecutive identical errors.

        If the last stored record has the same ``(error_type, tool_name,
        file_hint)`` signature as *record*, the last entry is replaced with a
        copy that has ``occurrence_count`` bumped by one.  This prevents the
        ring buffer filling up with identical retry failures.
        """
        if self._records:
            last = self._records[-1]
            if (
                last.error_type == record.error_type
                and last.tool_name == record.tool_name
                and last.file_hint == record.file_hint
            ):
                updated = dc_replace(last, occurrence_count=last.occurrence_count + 1)
                self._records = self._records[:-1] + [updated]
                return

        new_records = self._records + [record]
        if len(new_records) > self._max_size:
            new_records = new_records[-self._max_size:]
        self._records = new_records

    def get_recent(self, n: int = 5) -> list[ErrorRecord]:
        """Return the *n* most recent records (oldest first)."""
        return self._records[-n:]

    def clear(self) -> None:
        """Remove all records."""
        self._records = []

    def __len__(self) -> int:
        return len(self._records)

    def to_context_str(self, n: int = 5, *, extended: bool = False) -> str:
        """Render the *n* most recent errors as a Markdown section for agent context.

        Returns an empty string when there are no errors.

        Args:
            n: Number of most recent errors to include.
            extended: When True, show 15 traceback lines (vs 5) and use a debug
                header. Used when ``Session.debug_mode`` is active.
        """
        recent = self.get_recent(n)
        if not recent:
            return ""

        if extended:
            header = f"## Recent Errors (debug mode — last {n})\n"
            tb_lines_count = 15
        else:
            header = "## Recent Errors\n"
            tb_lines_count = 5

        lines: list[str] = [header]
        for rec in recent:
            ts = rec.timestamp.strftime("%H:%M:%S")
            msg_preview = rec.message[:120]
            repeat = f" ×{rec.occurrence_count}" if rec.occurrence_count > 1 else ""
            lines.append(
                f"- **{ts}** `{rec.tool_name}` ({rec.agent_name}) [{rec.error_type}]{repeat}: {msg_preview}"
            )
            if rec.file_hint:
                lines.append(f"  - File hint: `{rec.file_hint}`")
            if rec.tool_args:
                args_str = ", ".join(
                    f"{k}={v!r}" for k, v in rec.tool_args.items()
                )
                if len(args_str) > 300:
                    args_str = args_str[:300] + "..."
                lines.append(f"  - Args: `{args_str}`")
            if rec.traceback_str:
                tb_raw = [l for l in rec.traceback_str.splitlines() if l.strip()]
                last_n = tb_raw[-tb_lines_count:]
                tb_preview = "\n".join(f"    {l}" for l in last_n)
                lines.append(f"  - Traceback (last lines):\n```\n{tb_preview}\n```")

        return "\n".join(lines)

    def get_file_snippets(self, n: int = 5, lines_around: int = 20) -> str:
        """Return Markdown of file snippets from the *n* most-recent errors.

        Only errors that have both a ``file_hint`` and a resolvable line number
        in their traceback are included.  Returns an empty string when nothing
        can be shown.

        Format::

            ## Failure-Site Snippets

            ### path/to/file.py:42
            ```python
            ...code around line 42...
            ```
        """
        recent = self.get_recent(n)
        snippets: list[str] = []

        for rec in recent:
            if not rec.file_hint:
                continue
            # Extract the last line-number reference for this file in the traceback
            line_no: int | None = None
            if rec.traceback_str:
                for m in re.finditer(
                    rf'File "{re.escape(rec.file_hint)}", line (\d+)',
                    rec.traceback_str,
                ):
                    line_no = int(m.group(1))

            if line_no is None:
                continue

            code = _extract_file_lines(rec.file_hint, line_no, lines_around)
            if code is None:
                continue

            snippets.append(f"### {rec.file_hint}:{line_no}\n```python\n{code}\n```")

        if not snippets:
            return ""

        return "## Failure-Site Snippets\n\n" + "\n\n".join(snippets)

    def infer_causality(self) -> None:
        """Build causality graph — link symptom errors to their root cause.

        Two errors are considered causally linked if:
        1. They occurred within 10 seconds of each other
        2. They share the same file_hint OR the later one is NoneType/AttributeError
           suggesting it was caused by an earlier failure
        3. The later error is a likely symptom: contains "NoneType", "AttributeError",
           "has no attribute", or "object is not"

        Updates records in-place (creates new frozen copies via dc_replace).
        Marks non-root-cause records with is_root_cause=False and caused_by_id set.
        """
        records = list(self._records)
        if len(records) < 2:
            return

        _SYMPTOM_PATTERNS = ("NoneType", "AttributeError", "has no attribute", "object is not")

        # Find causal links: for each record, look back 10 seconds for a potential cause
        new_records = list(records)  # mutable copy (of references)

        for i in range(1, len(records)):
            rec = records[i]
            # Only consider symptom-like errors
            is_symptom = any(p in rec.message for p in _SYMPTOM_PATTERNS)
            if not is_symptom:
                continue

            rec_time = rec.timestamp
            for j in range(i - 1, -1, -1):
                candidate = records[j]
                # Check time window: within 10 seconds
                time_diff = abs((rec_time - candidate.timestamp).total_seconds())
                if time_diff > 10.0:
                    continue
                # Check file overlap OR candidate is not already a symptom
                same_file = (rec.file_hint and candidate.file_hint
                             and rec.file_hint == candidate.file_hint)
                candidate_is_root = new_records[j].is_root_cause
                if same_file or candidate_is_root:
                    # Mark rec as caused by candidate
                    new_records[i] = dc_replace(
                        new_records[i],
                        caused_by_id=candidate.id,
                        is_root_cause=False,
                    )
                    break

        self._records = new_records

    def get_root_causes(self) -> list[ErrorRecord]:
        """Return only root-cause errors (not symptoms)."""
        return [r for r in self._records if r.is_root_cause]

    def to_causal_chain_str(self) -> str:
        """Render a causal chain tree as Markdown.

        Format:
            ROOT: AttributeError in session.py:45 (×3)
              └─ SYMPTOM: NoneType in graph.py:112
        """
        if not self._records:
            return ""

        # First run causality inference
        self.infer_causality()

        # Build tree: root_id -> [symptom records]
        roots = [r for r in self._records if r.is_root_cause]
        symptoms_by_cause: dict[str, list[ErrorRecord]] = {}
        for r in self._records:
            if not r.is_root_cause and r.caused_by_id:
                symptoms_by_cause.setdefault(r.caused_by_id, []).append(r)

        if not roots:
            return ""

        lines = ["## Causal Error Chain"]
        for root in roots:
            file_info = f" in {root.file_hint}" if root.file_hint else ""
            repeat = f" (×{root.occurrence_count})" if root.occurrence_count > 1 else ""
            lines.append(f"ROOT: {root.error_type}{file_info}{repeat}")
            for symptom in symptoms_by_cause.get(root.id, []):
                sym_file = f" in {symptom.file_hint}" if symptom.file_hint else ""
                sym_rep = f" (×{symptom.occurrence_count})" if symptom.occurrence_count > 1 else ""
                lines.append(f"  └─ SYMPTOM: {symptom.error_type}{sym_file}{sym_rep}")
        return "\n".join(lines)
