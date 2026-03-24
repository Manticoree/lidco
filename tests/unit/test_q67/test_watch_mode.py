"""Tests for Task 455: File-watch annotation trigger."""
import pytest
from pathlib import Path
from lidco.watch.watcher import Annotation, FileWatcher


@pytest.fixture
def watcher(tmp_path):
    return FileWatcher(watch_path=tmp_path)


def write_file(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestScanForAnnotations:
    def test_single_hash_annotation(self, watcher, tmp_path):
        p = write_file(tmp_path, "foo.py", "x = 1\n# LIDCO: add type hint\ny = 2\n")
        anns = watcher.scan_for_annotations(p)
        assert len(anns) == 1
        assert anns[0].instruction == "add type hint"
        assert anns[0].line_number == 2

    def test_double_slash_annotation(self, watcher, tmp_path):
        p = write_file(tmp_path, "foo.js", "const x = 1;\n// LIDCO: refactor this\n")
        anns = watcher.scan_for_annotations(p)
        assert len(anns) == 1
        assert anns[0].instruction == "refactor this"

    def test_case_insensitive(self, watcher, tmp_path):
        p = write_file(tmp_path, "foo.py", "# lidco: lower case works\n")
        anns = watcher.scan_for_annotations(p)
        assert len(anns) == 1

    def test_no_annotations_returns_empty(self, watcher, tmp_path):
        p = write_file(tmp_path, "clean.py", "x = 1\n# normal comment\n")
        assert watcher.scan_for_annotations(p) == []

    def test_multiple_annotations(self, watcher, tmp_path):
        p = write_file(tmp_path, "multi.py", "# LIDCO: first\nx = 1\n# LIDCO: second\n")
        anns = watcher.scan_for_annotations(p)
        assert len(anns) == 2
        assert anns[0].instruction == "first"
        assert anns[1].instruction == "second"

    def test_context_lines_captured(self, watcher, tmp_path):
        p = write_file(tmp_path, "ctx.py", "def foo():\n    pass\n# LIDCO: add docstring\n    return 1\n")
        anns = watcher.scan_for_annotations(p)
        assert len(anns[0].context_lines) > 0

    def test_multiline_block_annotation(self, watcher, tmp_path):
        content = "# LIDCO: |\n# Add comprehensive\n# type hints\nx = 1\n"
        p = write_file(tmp_path, "block.py", content)
        anns = watcher.scan_for_annotations(p)
        assert len(anns) == 1
        assert "comprehensive" in anns[0].instruction
        assert "type hints" in anns[0].instruction

    def test_nonexistent_file_returns_empty(self, watcher, tmp_path):
        assert watcher.scan_for_annotations(tmp_path / "ghost.py") == []


class TestRemoveAnnotations:
    def test_removes_single_annotation(self, watcher, tmp_path):
        p = write_file(tmp_path, "r.py", "x = 1\n# LIDCO: fix this\ny = 2\n")
        count = watcher.remove_annotations(p)
        assert count == 1
        remaining = p.read_text()
        assert "LIDCO" not in remaining
        assert "x = 1" in remaining

    def test_removes_multiple_annotations(self, watcher, tmp_path):
        p = write_file(tmp_path, "r2.py", "# LIDCO: a\nx=1\n# LIDCO: b\n")
        count = watcher.remove_annotations(p)
        assert count == 2

    def test_removes_block_annotation(self, watcher, tmp_path):
        content = "# LIDCO: |\n# instruction line 1\n# instruction line 2\nreal_code = 1\n"
        p = write_file(tmp_path, "block.py", content)
        count = watcher.remove_annotations(p)
        assert count > 0
        assert "LIDCO" not in p.read_text()
        assert "real_code" in p.read_text()

    def test_no_annotations_unchanged(self, watcher, tmp_path):
        original = "x = 1\n# normal comment\n"
        p = write_file(tmp_path, "clean.py", original)
        count = watcher.remove_annotations(p)
        assert count == 0
        assert p.read_text() == original


class TestWatchOnce:
    def test_detects_new_file(self, watcher, tmp_path):
        p = write_file(tmp_path, "new.py", "# LIDCO: do something\n")
        annotations = watcher.watch_once()
        assert any(a.file_path == str(p) for a in annotations)

    def test_handler_called_on_annotation(self, watcher, tmp_path):
        found = []
        watcher.set_annotation_handler(lambda ann: found.append(ann))
        write_file(tmp_path, "trigger.py", "# LIDCO: trigger\n")
        watcher.watch_once()
        assert len(found) == 1
        assert found[0].instruction == "trigger"

    def test_unchanged_file_not_rescanned(self, watcher, tmp_path):
        p = write_file(tmp_path, "stable.py", "# LIDCO: once\n")
        watcher.watch_once()  # first pass — marks mtime
        found = []
        watcher.set_annotation_handler(lambda ann: found.append(ann))
        watcher.watch_once()  # second pass — no change
        assert len(found) == 0


class TestScanAll:
    def test_scan_all_finds_across_files(self, watcher, tmp_path):
        write_file(tmp_path, "a.py", "# LIDCO: fix a\n")
        write_file(tmp_path, "b.py", "# LIDCO: fix b\n")
        all_anns = watcher.scan_all()
        assert len(all_anns) == 2
