"""Tests for T608 TodoScanner."""
from pathlib import Path
from unittest.mock import patch

import pytest

from lidco.analysis.todo_scanner import (
    TAG_SEVERITY,
    TodoScanner,
    TodoReport,
    TodoItem,
    _TAG_RE,
)


# ---------------------------------------------------------------------------
# Regex matching
# ---------------------------------------------------------------------------

class TestTagRegex:
    def test_python_todo(self):
        m = _TAG_RE.search("# TODO: fix this")
        assert m is not None
        assert m.group("tag").upper() == "TODO"
        assert "fix this" in m.group("text")

    def test_python_fixme(self):
        m = _TAG_RE.search("# FIXME: broken")
        assert m is not None
        assert m.group("tag").upper() == "FIXME"

    def test_js_comment(self):
        m = _TAG_RE.search("// TODO: add tests")
        assert m is not None

    def test_with_owner(self):
        m = _TAG_RE.search("# TODO(alice): needs review")
        assert m is not None
        assert m.group("owner") == "alice"

    def test_case_insensitive(self):
        m = _TAG_RE.search("# todo: lowercase")
        assert m is not None

    def test_no_match_on_regular_comment(self):
        m = _TAG_RE.search("# This is a normal comment")
        assert m is None

    def test_hack_matches(self):
        m = _TAG_RE.search("# HACK: temporary workaround")
        assert m is not None
        assert m.group("tag").upper() == "HACK"

    def test_xxx_matches(self):
        m = _TAG_RE.search("# XXX: bad code here")
        assert m is not None


# ---------------------------------------------------------------------------
# TAG_SEVERITY
# ---------------------------------------------------------------------------

class TestTagSeverity:
    def test_fixme_is_high(self):
        assert TAG_SEVERITY["FIXME"] == "high"

    def test_hack_is_high(self):
        assert TAG_SEVERITY["HACK"] == "high"

    def test_todo_is_medium(self):
        assert TAG_SEVERITY["TODO"] == "medium"

    def test_note_is_info(self):
        assert TAG_SEVERITY["NOTE"] == "info"


# ---------------------------------------------------------------------------
# TodoScanner.scan_file
# ---------------------------------------------------------------------------

class TestScanFile:
    def _write(self, tmp_path, name, content):
        p = tmp_path / name
        p.write_text(content)
        return str(p)

    def test_finds_todo(self, tmp_path):
        path = self._write(tmp_path, "main.py", "x = 1\n# TODO: fix this\ny = 2\n")
        scanner = TodoScanner()
        items = scanner.scan_file(path)
        assert len(items) == 1
        assert items[0].tag == "TODO"
        assert items[0].line == 2

    def test_finds_fixme(self, tmp_path):
        path = self._write(tmp_path, "main.py", "# FIXME: broken\n")
        scanner = TodoScanner()
        items = scanner.scan_file(path)
        assert items[0].tag == "FIXME"
        assert items[0].severity == "high"

    def test_extracts_owner(self, tmp_path):
        path = self._write(tmp_path, "main.py", "# TODO(alice): check this\n")
        scanner = TodoScanner()
        items = scanner.scan_file(path)
        assert items[0].owner == "alice"

    def test_no_items_in_clean_file(self, tmp_path):
        path = self._write(tmp_path, "main.py", "x = 1\ny = 2\n")
        scanner = TodoScanner()
        items = scanner.scan_file(path)
        assert items == []

    def test_multiple_items(self, tmp_path):
        content = "# TODO: one\n# FIXME: two\n# HACK: three\n"
        path = self._write(tmp_path, "main.py", content)
        scanner = TodoScanner()
        items = scanner.scan_file(path)
        assert len(items) == 3

    def test_javascript_comment(self, tmp_path):
        path = self._write(tmp_path, "app.js", "// TODO: add error handling\n")
        scanner = TodoScanner()
        items = scanner.scan_file(path)
        assert len(items) == 1

    def test_missing_file_returns_empty(self):
        scanner = TodoScanner()
        items = scanner.scan_file("/nonexistent/path/file.py")
        assert items == []

    def test_tag_filter(self, tmp_path):
        content = "# TODO: one\n# FIXME: two\n"
        path = self._write(tmp_path, "main.py", content)
        scanner = TodoScanner(tags=("FIXME",))
        items = scanner.scan_file(path)
        assert len(items) == 1
        assert items[0].tag == "FIXME"


# ---------------------------------------------------------------------------
# TodoScanner.scan (directory)
# ---------------------------------------------------------------------------

class TestScan:
    def _setup(self, tmp_path, files: dict[str, str]):
        for name, content in files.items():
            p = tmp_path / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)

    def test_scan_directory(self, tmp_path):
        self._setup(tmp_path, {
            "a.py": "# TODO: fix a\n",
            "b.py": "# FIXME: fix b\n",
        })
        scanner = TodoScanner(project_root=str(tmp_path))
        report = scanner.scan()
        assert len(report.items) == 2
        assert report.files_scanned == 2

    def test_skips_node_modules(self, tmp_path):
        # Create node_modules OUTSIDE the scanner root
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("# TODO: main\n")
        nm = tmp_path / "node_modules" / "lib"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("// TODO: skip me\n")

        # Scan only the src dir → node_modules not reachable
        scanner = TodoScanner(project_root=str(src))
        report = scanner.scan()
        paths = [i.file.replace("\\", "/") for i in report.items]
        assert not any("/node_modules/" in p for p in paths)
        assert len(report.items) == 1

    def test_report_by_tag(self, tmp_path):
        self._setup(tmp_path, {"main.py": "# TODO: one\n# FIXME: two\n"})
        scanner = TodoScanner(project_root=str(tmp_path))
        report = scanner.scan()
        assert "TODO" in report.by_tag
        assert "FIXME" in report.by_tag

    def test_report_by_file(self, tmp_path):
        self._setup(tmp_path, {
            "a.py": "# TODO: one\n",
            "b.py": "# TODO: two\n",
        })
        scanner = TodoScanner(project_root=str(tmp_path))
        report = scanner.scan()
        assert len(report.by_file) == 2

    def test_high_count(self, tmp_path):
        self._setup(tmp_path, {"main.py": "# FIXME: high1\n# HACK: high2\n# TODO: med\n"})
        scanner = TodoScanner(project_root=str(tmp_path))
        report = scanner.scan()
        assert report.high_count == 2
        assert report.medium_count == 1

    def test_summary_format(self, tmp_path):
        self._setup(tmp_path, {"main.py": "# TODO: one\n"})
        scanner = TodoScanner(project_root=str(tmp_path))
        report = scanner.scan()
        s = report.summary()
        assert "item" in s.lower()

    def test_empty_dir(self, tmp_path):
        scanner = TodoScanner(project_root=str(tmp_path))
        report = scanner.scan()
        assert report.items == []
        assert report.files_scanned == 0


# ---------------------------------------------------------------------------
# TodoItem
# ---------------------------------------------------------------------------

class TestTodoItem:
    def test_fields(self):
        item = TodoItem(
            file="main.py",
            line=42,
            tag="TODO",
            severity="medium",
            text="fix this",
            owner="alice",
        )
        assert item.file == "main.py"
        assert item.line == 42
        assert item.owner == "alice"
