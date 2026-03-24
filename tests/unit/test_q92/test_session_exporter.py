"""Tests for src/lidco/export/session_exporter.py."""

import pytest
from pathlib import Path
from lidco.export.session_exporter import ExportConfig, ExportResult, SessionExporter


def make_messages(n: int = 3) -> list[dict]:
    msgs = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"Message {i}"})
    return msgs


class TestExportConfigDataclass:
    def test_defaults(self):
        cfg = ExportConfig()
        assert cfg.format == "markdown"
        assert cfg.include_metadata is True
        assert cfg.max_messages is None
        assert cfg.title == "LIDCO Session Export"

    def test_custom(self):
        cfg = ExportConfig(format="html", max_messages=5, title="My Session")
        assert cfg.format == "html"
        assert cfg.max_messages == 5
        assert cfg.title == "My Session"


class TestExportResultDataclass:
    def test_fields(self):
        r = ExportResult(content="# Hello", format="markdown", message_count=2)
        assert r.content == "# Hello"
        assert r.format == "markdown"
        assert r.message_count == 2


class TestExportMarkdown:
    def test_basic_export(self):
        exp = SessionExporter()
        msgs = make_messages(2)
        md = exp.export_markdown(msgs)
        assert "## User" in md
        assert "## Assistant" in md
        assert "Message 0" in md

    def test_all_roles_labelled(self):
        exp = SessionExporter()
        msgs = [
            {"role": "system", "content": "sys prompt"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        md = exp.export_markdown(msgs)
        assert "## System" in md
        assert "## User" in md
        assert "## Assistant" in md

    def test_ends_with_newline(self):
        exp = SessionExporter()
        md = exp.export_markdown(make_messages(1))
        assert md.endswith("\n")

    def test_name_in_metadata(self):
        exp = SessionExporter()
        msgs = [{"role": "user", "content": "hi", "name": "alice"}]
        md = exp.export_markdown(msgs, include_metadata=True)
        assert "alice" in md

    def test_no_metadata_when_disabled(self):
        exp = SessionExporter()
        msgs = [{"role": "user", "content": "hi", "name": "alice"}]
        md = exp.export_markdown(msgs, include_metadata=False)
        assert "alice" not in md


class TestExportHTML:
    def test_valid_html_structure(self):
        exp = SessionExporter()
        html = exp.export_html(make_messages(2))
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_message_content_present(self):
        exp = SessionExporter()
        msgs = [{"role": "user", "content": "unique-phrase-xyz"}]
        html = exp.export_html(msgs)
        assert "unique-phrase-xyz" in html

    def test_role_css_class(self):
        exp = SessionExporter()
        msgs = [{"role": "assistant", "content": "hi"}]
        html = exp.export_html(msgs)
        assert 'class="msg assistant"' in html

    def test_custom_title(self):
        exp = SessionExporter()
        html = exp.export_html([], title="My Custom Title")
        assert "My Custom Title" in html

    def test_xss_escaped(self):
        exp = SessionExporter()
        msgs = [{"role": "user", "content": "<script>alert(1)</script>"}]
        html = exp.export_html(msgs)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_unterminated_code_fence(self):
        # B9: unterminated fences should still be handled without crash
        exp = SessionExporter()
        msgs = [{"role": "user", "content": "```python\nprint('hello')\n"}]
        html = exp.export_html(msgs)
        assert "<pre>" in html
        assert "print" in html

    def test_terminated_code_fence_preserved(self):
        exp = SessionExporter()
        msgs = [{"role": "user", "content": "```python\nfoo = 1\n```"}]
        html = exp.export_html(msgs)
        assert "<pre>" in html
        assert "foo = 1" in html


class TestExport:
    def test_markdown_format(self):
        exp = SessionExporter()
        result = exp.export(make_messages(2), ExportConfig(format="markdown"))
        assert result.format == "markdown"
        assert "## User" in result.content

    def test_html_format(self):
        exp = SessionExporter()
        result = exp.export(make_messages(2), ExportConfig(format="html"))
        assert result.format == "html"
        assert "<!DOCTYPE html>" in result.content

    def test_message_count(self):
        exp = SessionExporter()
        result = exp.export(make_messages(4))
        assert result.message_count == 4

    def test_max_messages_limit(self):
        exp = SessionExporter()
        result = exp.export(make_messages(10), ExportConfig(max_messages=3))
        assert result.message_count == 3

    def test_default_config(self):
        exp = SessionExporter()
        result = exp.export(make_messages(2))
        assert result.format == "markdown"


class TestSave:
    def test_saves_file(self, tmp_path):
        exp = SessionExporter()
        result = ExportResult(content="# Hello", format="markdown", message_count=1)
        out = exp.save(result, tmp_path / "out.md")
        assert out.exists()
        assert out.read_text() == "# Hello"

    def test_creates_parent_dirs(self, tmp_path):
        exp = SessionExporter()
        result = ExportResult(content="hi", format="markdown", message_count=1)
        out = exp.save(result, tmp_path / "subdir" / "nested" / "out.md")
        assert out.exists()

    def test_returns_resolved_path(self, tmp_path):
        exp = SessionExporter()
        result = ExportResult(content="x", format="markdown", message_count=0)
        out = exp.save(result, tmp_path / "out.md")
        assert out.is_absolute()
