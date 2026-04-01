"""Tests for lidco.transcript.export."""
from __future__ import annotations

import json

from lidco.transcript.export import ExportFormat, TranscriptExporter
from lidco.transcript.store import TranscriptStore


def _populated_store() -> TranscriptStore:
    store = TranscriptStore()
    store.append("user", "Hello assistant")
    store.append("assistant", "Hello! How can I help?")
    store.append("tool", "output", tool_name="bash")
    return store


class TestTranscriptExporter:
    def test_export_markdown(self):
        store = _populated_store()
        exporter = TranscriptExporter(store)
        md = exporter.export_markdown()
        assert "# Transcript" in md
        assert "[user]" in md
        assert "[assistant]" in md
        assert "(tool: bash)" in md

    def test_export_json(self):
        store = _populated_store()
        exporter = TranscriptExporter(store)
        raw = exporter.export_json()
        data = json.loads(raw)
        assert len(data) == 3
        assert data[0]["role"] == "user"
        assert data[2]["tool_name"] == "bash"

    def test_export_text(self):
        store = _populated_store()
        exporter = TranscriptExporter(store)
        text = exporter.export_text()
        assert "user:" in text
        assert "assistant:" in text
        assert "(bash)" in text

    def test_export_dispatch(self):
        store = _populated_store()
        exporter = TranscriptExporter(store)
        md = exporter.export(ExportFormat.MARKDOWN)
        assert "# Transcript" in md
        js = exporter.export(ExportFormat.JSON)
        assert json.loads(js)
        txt = exporter.export(ExportFormat.TEXT)
        assert "user:" in txt

    def test_export_with_subset(self):
        store = _populated_store()
        exporter = TranscriptExporter(store)
        entries = store.list_entries(role="user")
        md = exporter.export_markdown(entries=entries)
        assert "[user]" in md
        assert "[assistant]" not in md

    def test_save_to_file(self, tmp_path):
        store = _populated_store()
        exporter = TranscriptExporter(store)
        path = tmp_path / "out.md"
        result = exporter.save_to_file(path, ExportFormat.MARKDOWN)
        assert result == str(path)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# Transcript" in content

    def test_redact_default_patterns(self):
        store = TranscriptStore()
        exporter = TranscriptExporter(store)
        text = "key: sk-abc12345678901234567890 email: user@example.com"
        redacted = exporter.redact(text)
        assert "sk-abc" not in redacted
        assert "user@example.com" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_custom_patterns(self):
        store = TranscriptStore()
        exporter = TranscriptExporter(store)
        text = "password=secret123"
        redacted = exporter.redact(text, patterns=[r"secret\d+"])
        assert "secret123" not in redacted
        assert "[REDACTED]" in redacted
