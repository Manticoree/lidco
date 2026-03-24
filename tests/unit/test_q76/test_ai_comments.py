"""Tests for AICommentScanner — T503."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lidco.watch.ai_comments import AIComment, AICommentScanner


class TestScanFile:
    def test_finds_execute_comment(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n# AI! do something\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        results = scanner.scan_file(f)
        assert len(results) == 1
        assert results[0].mode == "execute"
        assert results[0].instruction == "do something"

    def test_finds_ask_comment(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("y = 2\n# AI? what is this\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        results = scanner.scan_file(f)
        assert len(results) == 1
        assert results[0].mode == "ask"
        assert results[0].instruction == "what is this"

    def test_finds_both_types(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("a = 1\n# AI! fix this\nb = 2\n# AI? explain this\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        results = scanner.scan_file(f)
        assert len(results) == 2
        modes = {r.mode for r in results}
        assert modes == {"execute", "ask"}

    def test_mode_values_correct(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("# AI! action\n# AI? question\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        results = scanner.scan_file(f)
        execute = next(r for r in results if r.mode == "execute")
        ask = next(r for r in results if r.mode == "ask")
        assert execute.mode == "execute"
        assert ask.mode == "ask"

    def test_context_lines_populated(self, tmp_path):
        f = tmp_path / "test.py"
        lines = ["line1\n", "line2\n", "line3\n", "# AI! do it\n"]
        f.write_text("".join(lines))
        scanner = AICommentScanner(watch_path=tmp_path)
        results = scanner.scan_file(f)
        assert len(results) == 1
        # context_lines should be 3 lines before the comment
        assert len(results[0].context_lines) == 3
        assert "line1" in results[0].context_lines[0]

    def test_line_number_correct(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("a = 1\nb = 2\n# AI! fix\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        results = scanner.scan_file(f)
        assert results[0].line_number == 3


class TestScanDirectory:
    def test_finds_across_multiple_files(self, tmp_path):
        (tmp_path / "a.py").write_text("# AI! do a\n")
        (tmp_path / "b.py").write_text("# AI? explain b\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        results = scanner.scan_directory(tmp_path)
        assert len(results) == 2

    def test_skips_pycache(self, tmp_path):
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("# AI! should skip\n")
        (tmp_path / "real.py").write_text("# AI! real\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        results = scanner.scan_directory(tmp_path)
        files = [r.file_path for r in results]
        assert not any("__pycache__" in f for f in files)


class TestRemoveComments:
    def test_removes_ai_lines(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1\n# AI! fix this\ny = 2\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        count = scanner.remove_comments(f)
        assert count == 1
        content = f.read_text()
        assert "AI!" not in content

    def test_preserves_other_lines(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1\n# AI! remove me\ny = 2\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        scanner.remove_comments(f)
        content = f.read_text()
        assert "x = 1" in content
        assert "y = 2" in content

    def test_returns_count_of_removed(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("# AI! one\n# AI? two\n# AI! three\nkeep = True\n")
        scanner = AICommentScanner(watch_path=tmp_path)
        count = scanner.remove_comments(f)
        assert count == 3


class TestIntegrateWithWatcher:
    def test_registers_callback_on_change(self, tmp_path):
        scanner = AICommentScanner(watch_path=tmp_path)
        watcher = MagicMock()
        watcher.on_change = MagicMock()
        scanner.integrate_with_watcher(watcher)
        watcher.on_change.assert_called_once()

    def test_callback_registered_with_set_annotation_handler(self, tmp_path):
        scanner = AICommentScanner(watch_path=tmp_path)
        watcher = MagicMock(spec=["set_annotation_handler"])
        watcher.set_annotation_handler = MagicMock()
        scanner.integrate_with_watcher(watcher)
        watcher.set_annotation_handler.assert_called_once()
