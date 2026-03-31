"""Tests for Q132 DirectoryWalker."""
from __future__ import annotations
import os
import unittest
from lidco.fs.directory_walker import DirectoryWalker, WalkEntry


def _make_fs(structure: dict) -> tuple:
    """Build mock listdir/isdir/getsize from a nested dict.

    structure: {name: None (file) or {name: ...} (dir)}
    """
    # Flatten into path -> content mapping
    paths: dict[str, dict | None] = {}

    def _flatten(d: dict, prefix: str):
        for name, val in d.items():
            full = os.path.join(prefix, name) if prefix else name
            paths[full] = val
            if isinstance(val, dict):
                _flatten(val, full)

    _flatten(structure, "root")

    def listdir(path: str) -> list[str]:
        # strip trailing sep
        path = path.rstrip("/\\")
        if path == "root":
            return list(structure.keys())
        rel = path
        parts = rel.replace("\\", "/").split("/")
        cur = structure
        for part in parts[1:]:  # skip "root"
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return []
        return list(cur.keys()) if isinstance(cur, dict) else []

    def isdir(path: str) -> bool:
        path = path.rstrip("/\\")
        norm = path.replace("\\", "/")
        parts = norm.split("/")
        cur = structure
        for part in parts[1:]:  # skip "root"
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return False
        return isinstance(cur, dict)

    def getsize(path: str) -> int:
        return 100  # fixed size for files

    return listdir, isdir, getsize


class TestDirectoryWalker(unittest.TestCase):
    def setUp(self):
        self.walker = DirectoryWalker()
        self.fs = {
            "src": {
                "main.py": None,
                "utils.py": None,
                "sub": {
                    "helper.py": None,
                },
            },
            "README.md": None,
            "tests": {
                "test_main.py": None,
            },
        }
        self.listdir, self.isdir, self.getsize = _make_fs(self.fs)

    def _walk(self, ignore=None):
        w = DirectoryWalker(ignore_patterns=ignore)
        return w.walk("root", listdir_fn=self.listdir, isdir_fn=self.isdir, getsize_fn=self.getsize)

    def test_walk_returns_entries(self):
        entries = self._walk()
        self.assertGreater(len(entries), 0)

    def test_files_found(self):
        entries = self._walk()
        names = [os.path.basename(e.path) for e in entries if not e.is_dir]
        self.assertIn("main.py", names)
        self.assertIn("README.md", names)

    def test_dirs_found(self):
        entries = self._walk()
        dirs = [e for e in entries if e.is_dir]
        self.assertTrue(any(os.path.basename(d.path) == "src" for d in dirs))

    def test_depth_tracking(self):
        entries = self._walk()
        readme = next(e for e in entries if os.path.basename(e.path) == "README.md")
        self.assertEqual(readme.depth, 1)

    def test_sub_depth(self):
        entries = self._walk()
        helper = next((e for e in entries if os.path.basename(e.path) == "helper.py"), None)
        self.assertIsNotNone(helper)
        self.assertEqual(helper.depth, 3)

    def test_ignore_pattern(self):
        entries = self._walk(ignore=["tests"])
        names = [os.path.basename(e.path) for e in entries]
        self.assertNotIn("test_main.py", names)

    def test_files_only(self):
        entries = self._walk()
        files = self.walker.files_only(entries)
        self.assertTrue(all(not e.is_dir for e in files))

    def test_dirs_only(self):
        entries = self._walk()
        dirs = self.walker.dirs_only(entries)
        self.assertTrue(all(e.is_dir for e in dirs))

    def test_max_depth(self):
        entries = self._walk()
        filtered = self.walker.max_depth(entries, 1)
        self.assertTrue(all(e.depth <= 1 for e in filtered))

    def test_total_size(self):
        entries = self._walk()
        files = self.walker.files_only(entries)
        total = self.walker.total_size(files)
        self.assertEqual(total, len(files) * 100)

    def test_total_size_dirs_zero(self):
        entries = self._walk()
        dirs = self.walker.dirs_only(entries)
        total = self.walker.total_size(dirs)
        self.assertEqual(total, 0)

    def test_default_ignore_pycache(self):
        fs_with_cache = dict(self.fs)
        fs_with_cache["__pycache__"] = {"cached.pyc": None}
        listdir, isdir, getsize = _make_fs(fs_with_cache)
        walker = DirectoryWalker()
        entries = walker.walk("root", listdir_fn=listdir, isdir_fn=isdir, getsize_fn=getsize)
        names = [os.path.basename(e.path) for e in entries]
        self.assertNotIn("cached.pyc", names)

    def test_walk_entry_dataclass(self):
        entry = WalkEntry(path="a/b.py", is_dir=False, size=100, depth=2)
        self.assertEqual(entry.depth, 2)
        self.assertFalse(entry.is_dir)

    def test_custom_ignore_patterns(self):
        walker = DirectoryWalker(ignore_patterns=["*.md"])
        entries = walker.walk("root", listdir_fn=self.listdir, isdir_fn=self.isdir, getsize_fn=self.getsize)
        names = [os.path.basename(e.path) for e in entries]
        self.assertNotIn("README.md", names)


if __name__ == "__main__":
    unittest.main()
