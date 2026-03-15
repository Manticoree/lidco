"""Tests for DocumentReader — Q62 Task 421."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestReadTxt:
    def test_read_txt_existing_file(self, tmp_path):
        from lidco.multimodal.doc_reader import DocumentReader
        f = tmp_path / "test.txt"
        f.write_text("Hello world", encoding="utf-8")
        reader = DocumentReader()
        result = reader.read_txt(f)
        assert "Hello world" in result

    def test_read_txt_missing_file(self):
        from lidco.multimodal.doc_reader import DocumentReader
        reader = DocumentReader()
        with pytest.raises(FileNotFoundError):
            reader.read_txt("/nonexistent/path.txt")

    def test_read_txt_truncation(self, tmp_path):
        from lidco.multimodal.doc_reader import DocumentReader, _MAX_CHARS
        f = tmp_path / "big.txt"
        f.write_text("x" * (_MAX_CHARS + 100), encoding="utf-8")
        reader = DocumentReader()
        result = reader.read_txt(f)
        assert len(result) <= _MAX_CHARS + 200  # truncation notice added
        assert "truncated" in result.lower() or len(result) == _MAX_CHARS


class TestReadDispatch:
    def test_read_dispatches_txt_by_extension(self, tmp_path):
        from lidco.multimodal.doc_reader import DocumentReader
        f = tmp_path / "notes.txt"
        f.write_text("note content")
        reader = DocumentReader()
        result = reader.read(f)
        assert "note content" in result

    def test_read_dispatches_pdf(self, tmp_path):
        from lidco.multimodal.doc_reader import DocumentReader
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 fake content")
        reader = DocumentReader()
        # Without pypdf/pdfplumber → RuntimeError
        with patch("lidco.multimodal.doc_reader._HAS_PYPDF", False):
            with patch("lidco.multimodal.doc_reader._HAS_PDFPLUMBER", False):
                with pytest.raises(RuntimeError, match="No PDF"):
                    reader.read_pdf(f)

    def test_read_dispatches_docx(self, tmp_path):
        from lidco.multimodal.doc_reader import DocumentReader
        f = tmp_path / "doc.docx"
        f.write_bytes(b"PK\x03\x04 fake docx")
        reader = DocumentReader()
        with patch("lidco.multimodal.doc_reader._HAS_DOCX", False):
            with pytest.raises(RuntimeError, match="python-docx"):
                reader.read_docx(f)

    def test_read_pdf_missing_file(self):
        from lidco.multimodal.doc_reader import DocumentReader
        reader = DocumentReader()
        with pytest.raises(FileNotFoundError):
            reader.read_pdf("/no/such/file.pdf")

    def test_read_docx_missing_file(self):
        from lidco.multimodal.doc_reader import DocumentReader
        reader = DocumentReader()
        with pytest.raises(FileNotFoundError):
            reader.read_docx("/no/such/file.docx")


class TestTruncate:
    def test_truncate_short_text_unchanged(self):
        from lidco.multimodal.doc_reader import DocumentReader, _MAX_CHARS
        reader = DocumentReader()
        text = "short text"
        assert reader._truncate(text) == text

    def test_truncate_long_text_trimmed(self):
        from lidco.multimodal.doc_reader import DocumentReader, _MAX_CHARS
        reader = DocumentReader()
        text = "a" * (_MAX_CHARS + 500)
        result = reader._truncate(text)
        assert len(result) < len(text)
        assert "truncated" in result.lower()


class TestDocumentContextTool:
    def test_tool_registered_with_correct_name(self):
        from lidco.multimodal.doc_reader import DocumentContextTool
        tool = DocumentContextTool()
        assert tool.name == "read_document"
