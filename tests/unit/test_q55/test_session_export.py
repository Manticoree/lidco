"""Q55/373 — Session export to MD, HTML, JSON."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


SAMPLE_HISTORY = [
    {"role": "user", "content": "Привет, как дела?"},
    {"role": "assistant", "content": "Отлично! Чем могу помочь?"},
    {"role": "user", "content": "Объясни `async def`"},
    {"role": "assistant", "content": "```python\nasync def foo():\n    pass\n```"},
]


class TestSessionExporter:
    def test_export_markdown(self, tmp_path):
        from lidco.cli.session_exporter import SessionExporter
        exp = SessionExporter(SAMPLE_HISTORY, session_id="test")
        path = exp.export(format="md", output_dir=tmp_path)
        assert path.suffix == ".md"
        content = path.read_text(encoding="utf-8")
        assert "Привет" in content
        assert "Отлично" in content
        assert "async def" in content

    def test_export_json(self, tmp_path):
        from lidco.cli.session_exporter import SessionExporter
        exp = SessionExporter(SAMPLE_HISTORY, session_id="test", metadata={"model": "claude-sonnet"})
        path = exp.export(format="json", output_dir=tmp_path)
        assert path.suffix == ".json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "messages" in data
        assert data["session_id"] == "test"
        assert data["metadata"]["model"] == "claude-sonnet"
        assert len(data["messages"]) == len(SAMPLE_HISTORY)

    def test_export_html(self, tmp_path):
        from lidco.cli.session_exporter import SessionExporter
        exp = SessionExporter(SAMPLE_HISTORY, session_id="html-test")
        path = exp.export(format="html", output_dir=tmp_path)
        assert path.suffix == ".html"
        html = path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html
        assert "html-test" in html
        # user/assistant classes present
        assert 'class="turn user"' in html
        assert 'class="turn assistant"' in html

    def test_export_default_format_is_md(self, tmp_path):
        from lidco.cli.session_exporter import SessionExporter
        exp = SessionExporter(SAMPLE_HISTORY, session_id="default")
        path = exp.export(output_dir=tmp_path)
        assert path.suffix == ".md"

    def test_export_creates_output_dir(self, tmp_path):
        from lidco.cli.session_exporter import SessionExporter
        out = tmp_path / "deep" / "nested"
        exp = SessionExporter(SAMPLE_HISTORY)
        path = exp.export(format="json", output_dir=out)
        assert path.exists()

    def test_export_html_escapes_xss(self, tmp_path):
        from lidco.cli.session_exporter import SessionExporter
        xss_history = [{"role": "user", "content": '<script>alert("xss")</script>'}]
        exp = SessionExporter(xss_history)
        path = exp.export(format="html", output_dir=tmp_path)
        html = path.read_text(encoding="utf-8")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
