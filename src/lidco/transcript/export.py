"""Export transcripts to multiple formats."""
from __future__ import annotations

import enum
import json
import re
import time
from dataclasses import asdict
from pathlib import Path

from lidco.transcript.store import TranscriptEntry, TranscriptStore


class ExportFormat(str, enum.Enum):
    """Supported export formats."""

    MARKDOWN = "markdown"
    JSON = "json"
    TEXT = "text"


_DEFAULT_REDACT_PATTERNS: list[str] = [
    r"sk-[A-Za-z0-9]{20,}",
    r"ghp_[A-Za-z0-9]{36}",
    r"AKIA[A-Z0-9]{16}",
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}",
]


class TranscriptExporter:
    """Export transcript entries to various formats."""

    def __init__(self, store: TranscriptStore) -> None:
        self._store = store

    def _resolve_entries(
        self, entries: list[TranscriptEntry] | None
    ) -> list[TranscriptEntry]:
        if entries is not None:
            return entries
        return self._store.list_entries()

    def export_markdown(
        self, entries: list[TranscriptEntry] | None = None
    ) -> str:
        """Export entries as Markdown."""
        resolved = self._resolve_entries(entries)
        lines: list[str] = ["# Transcript", ""]
        for entry in resolved:
            ts = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(entry.timestamp)
            )
            header = f"## [{entry.role}] {ts}"
            if entry.tool_name:
                header += f" (tool: {entry.tool_name})"
            lines.append(header)
            lines.append("")
            lines.append(entry.content)
            lines.append("")
        return "\n".join(lines)

    def export_json(
        self, entries: list[TranscriptEntry] | None = None
    ) -> str:
        """Export entries as JSON array."""
        resolved = self._resolve_entries(entries)
        return json.dumps(
            [asdict(e) for e in resolved], indent=2, ensure_ascii=False
        )

    def export_text(
        self, entries: list[TranscriptEntry] | None = None
    ) -> str:
        """Export entries as plain text."""
        resolved = self._resolve_entries(entries)
        lines: list[str] = []
        for entry in resolved:
            ts = time.strftime(
                "%H:%M:%S", time.localtime(entry.timestamp)
            )
            prefix = f"[{ts}] {entry.role}"
            if entry.tool_name:
                prefix += f" ({entry.tool_name})"
            lines.append(f"{prefix}: {entry.content}")
        return "\n".join(lines)

    def export(
        self,
        format: ExportFormat,
        entries: list[TranscriptEntry] | None = None,
    ) -> str:
        """Export entries in the specified format."""
        dispatch = {
            ExportFormat.MARKDOWN: self.export_markdown,
            ExportFormat.JSON: self.export_json,
            ExportFormat.TEXT: self.export_text,
        }
        handler = dispatch.get(format)
        if handler is None:
            raise ValueError(f"Unsupported format: {format}")
        return handler(entries)

    def save_to_file(self, path: str | Path, format: ExportFormat) -> str:
        """Export all entries and save to file. Returns path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        content = self.export(format)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def redact(
        self, text: str, patterns: list[str] | None = None
    ) -> str:
        """Redact sensitive data from text."""
        pats = patterns if patterns is not None else _DEFAULT_REDACT_PATTERNS
        result = text
        for pat in pats:
            result = re.sub(pat, "[REDACTED]", result)
        return result
