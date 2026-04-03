"""Tests for Q273 FilePicker widget."""
from __future__ import annotations

import unittest

from lidco.widgets.file_picker import FileEntry, FilePicker


class TestFileEntry(unittest.TestCase):
    def test_creation(self):
        e = FileEntry(path="/a/b.py", name="b.py")
        assert e.path == "/a/b.py"
        assert e.name == "b.py"
        assert e.is_dir is False
        assert e.size == 0

    def test_frozen(self):
        e = FileEntry(path="x", name="x")
        with self.assertRaises(AttributeError):
            e.path = "y"  # type: ignore[misc]


class TestFilePicker(unittest.TestCase):
    def _make_picker(self) -> FilePicker:
        fp = FilePicker(root="/project")
        fp.add_entry("/project/main.py", size=100)
        fp.add_entry("/project/utils.py", size=200)
        fp.add_entry("/project/src", is_dir=True)
        fp.add_entry("/project/src/app.py", size=50)
        return fp

    def test_add_entry(self):
        fp = FilePicker()
        e = fp.add_entry("/a/b.py", size=42)
        assert e.name == "b.py"
        assert e.size == 42

    def test_list_files_all(self):
        fp = self._make_picker()
        assert len(fp.list_files()) == 4

    def test_list_files_directory(self):
        fp = self._make_picker()
        result = fp.list_files("/project/src")
        paths = [e.path for e in result]
        assert "/project/src/app.py" in paths

    def test_search_by_name(self):
        fp = self._make_picker()
        results = fp.search("main")
        assert any(e.name == "main.py" for e in results)

    def test_search_empty_returns_all(self):
        fp = self._make_picker()
        assert len(fp.search("")) == 4

    def test_search_no_match(self):
        fp = self._make_picker()
        assert len(fp.search("zzzzz")) == 0

    def test_select_adds_recent(self):
        fp = self._make_picker()
        e = fp.select("/project/main.py")
        assert e is not None
        assert e.name == "main.py"
        assert "/project/main.py" in fp.recent()

    def test_select_not_found(self):
        fp = self._make_picker()
        assert fp.select("/nope") is None

    def test_bookmarks(self):
        fp = FilePicker()
        fp.add_bookmark("/a")
        fp.add_bookmark("/b")
        assert fp.bookmarks() == ["/a", "/b"]
        assert fp.remove_bookmark("/a") is True
        assert fp.remove_bookmark("/a") is False
        assert fp.bookmarks() == ["/b"]

    def test_recent_limit(self):
        fp = FilePicker()
        for i in range(15):
            fp.add_recent(f"/file{i}")
        assert len(fp.recent(limit=5)) == 5
        assert fp.recent(limit=5)[0] == "/file14"

    def test_render(self):
        fp = self._make_picker()
        r = fp.render()
        assert "4 files" in r
        assert "0 bookmarks" in r


if __name__ == "__main__":
    unittest.main()
