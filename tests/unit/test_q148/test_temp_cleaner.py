"""Tests for Q148 TempCleaner."""
from __future__ import annotations

import unittest
from lidco.maintenance.temp_cleaner import TempCleaner, CleanupTarget, CleanupResult


class TestCleanupTarget(unittest.TestCase):
    def test_fields(self):
        t = CleanupTarget(path="/a/b.pyc", size_bytes=100, age_seconds=60.0, reason="matches *.pyc")
        self.assertEqual(t.path, "/a/b.pyc")
        self.assertEqual(t.size_bytes, 100)
        self.assertAlmostEqual(t.age_seconds, 60.0)
        self.assertEqual(t.reason, "matches *.pyc")


class TestCleanupResult(unittest.TestCase):
    def test_defaults(self):
        r = CleanupResult()
        self.assertEqual(r.removed, [])
        self.assertEqual(r.skipped, [])
        self.assertEqual(r.bytes_freed, 0)
        self.assertEqual(r.errors, [])

    def test_independent_defaults(self):
        r1 = CleanupResult()
        r2 = CleanupResult()
        r1.removed.append("x")
        self.assertEqual(r2.removed, [])


class TestTempCleanerInit(unittest.TestCase):
    def test_default_patterns(self):
        tc = TempCleaner()
        self.assertIn("*.pyc", tc.patterns)
        self.assertIn("__pycache__", tc.patterns)
        self.assertIn("*.bak", tc.patterns)
        self.assertIn("*.swp", tc.patterns)
        self.assertIn(".tmp", tc.patterns)

    def test_custom_patterns(self):
        tc = TempCleaner(patterns=["*.log"])
        self.assertEqual(tc.patterns, ["*.log"])

    def test_patterns_copy(self):
        original = ["*.log"]
        tc = TempCleaner(patterns=original)
        original.append("*.bak")
        self.assertEqual(tc.patterns, ["*.log"])


class TestPatternManagement(unittest.TestCase):
    def test_add_pattern(self):
        tc = TempCleaner(patterns=[])
        tc.add_pattern("*.log")
        self.assertIn("*.log", tc.patterns)

    def test_add_pattern_no_duplicate(self):
        tc = TempCleaner(patterns=["*.log"])
        tc.add_pattern("*.log")
        self.assertEqual(tc.patterns.count("*.log"), 1)

    def test_remove_pattern(self):
        tc = TempCleaner(patterns=["*.log", "*.bak"])
        tc.remove_pattern("*.log")
        self.assertNotIn("*.log", tc.patterns)

    def test_remove_pattern_missing(self):
        tc = TempCleaner(patterns=["*.log"])
        tc.remove_pattern("*.xyz")  # no error
        self.assertEqual(tc.patterns, ["*.log"])


class TestMatching(unittest.TestCase):
    def test_match_extension(self):
        tc = TempCleaner(patterns=["*.pyc"])
        self.assertTrue(tc._matches("foo.pyc"))
        self.assertFalse(tc._matches("foo.py"))

    def test_match_exact(self):
        tc = TempCleaner(patterns=["__pycache__"])
        self.assertTrue(tc._matches("__pycache__"))
        self.assertFalse(tc._matches("cache"))

    def test_match_dot_tmp(self):
        tc = TempCleaner(patterns=[".tmp"])
        self.assertTrue(tc._matches(".tmp"))
        self.assertFalse(tc._matches("file.tmp"))


class _FakeFS:
    """Injectable fake filesystem for TempCleaner."""

    def __init__(self, tree: dict[str, int | dict]):
        # tree: {name: size_int} or {name: {subtree}}
        self._tree = tree
        self._removed: list[str] = []

    def _resolve(self, path: str):
        import os
        parts = path.replace("\\", "/").strip("/").split("/")
        node = self._tree
        for p in parts:
            if isinstance(node, dict) and p in node:
                node = node[p]
            else:
                return None
        return node

    def listdir(self, path: str) -> list[str]:
        node = self._resolve(path)
        if isinstance(node, dict):
            return list(node.keys())
        raise OSError(f"not a dir: {path}")

    def isfile(self, path: str) -> bool:
        node = self._resolve(path)
        return isinstance(node, int)

    def isdir(self, path: str) -> bool:
        node = self._resolve(path)
        return isinstance(node, dict)

    def getsize(self, path: str) -> int:
        node = self._resolve(path)
        if isinstance(node, int):
            return node
        return 0

    def getmtime(self, path: str) -> float:
        return 1000.0

    def remove(self, path: str) -> None:
        self._removed.append(path)

    def rmdir(self, path: str) -> None:
        self._removed.append(path)


def _make_cleaner(tree: dict, patterns=None) -> tuple[TempCleaner, _FakeFS]:
    fs = _FakeFS(tree)
    tc = TempCleaner(
        patterns=patterns,
        _listdir=fs.listdir,
        _isfile=fs.isfile,
        _isdir=fs.isdir,
        _getsize=fs.getsize,
        _getmtime=fs.getmtime,
        _remove=fs.remove,
        _rmdir=fs.rmdir,
    )
    return tc, fs


class TestScan(unittest.TestCase):
    def test_scan_finds_pyc(self):
        tc, _ = _make_cleaner({"root": {"foo.pyc": 50, "bar.py": 100}})
        targets = tc.scan("root")
        self.assertEqual(len(targets), 1)
        self.assertIn("foo.pyc", targets[0].path)

    def test_scan_finds_pycache(self):
        tc, _ = _make_cleaner({"root": {"__pycache__": {"a.pyc": 10}}})
        targets = tc.scan("root")
        names = [t.path for t in targets]
        self.assertTrue(any("__pycache__" in n for n in names))

    def test_scan_empty_dir(self):
        tc, _ = _make_cleaner({"root": {}})
        self.assertEqual(tc.scan("root"), [])

    def test_scan_nested(self):
        tc, _ = _make_cleaner({"root": {"sub": {"deep.bak": 20}}})
        targets = tc.scan("root")
        self.assertEqual(len(targets), 1)
        self.assertIn("deep.bak", targets[0].path)


class TestClean(unittest.TestCase):
    def test_clean_removes(self):
        tc, fs = _make_cleaner({"root": {"a.pyc": 50, "b.py": 100}})
        result = tc.clean("root")
        self.assertEqual(len(result.removed), 1)
        self.assertEqual(result.bytes_freed, 50)
        self.assertEqual(len(result.errors), 0)

    def test_clean_dry_run(self):
        tc, fs = _make_cleaner({"root": {"a.pyc": 50}})
        result = tc.clean("root", dry_run=True)
        self.assertEqual(len(result.removed), 0)
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(len(fs._removed), 0)

    def test_clean_error_handling(self):
        def bad_remove(path):
            raise OSError("permission denied")

        tree = {"root": {"a.pyc": 10}}
        ffs = _FakeFS(tree)
        tc = TempCleaner(
            _listdir=ffs.listdir,
            _isfile=ffs.isfile,
            _isdir=ffs.isdir,
            _getsize=ffs.getsize,
            _getmtime=ffs.getmtime,
            _remove=bad_remove,
            _rmdir=ffs.rmdir,
        )
        result = tc.clean("root")
        self.assertTrue(len(result.errors) > 0)
        self.assertTrue(len(result.skipped) > 0)


class TestEstimate(unittest.TestCase):
    def test_estimate_counts(self):
        tc, _ = _make_cleaner({"root": {"a.pyc": 100, "b.bak": 200, "c.py": 50}})
        est = tc.estimate("root")
        self.assertEqual(est["total_files"], 2)
        self.assertEqual(est["total_bytes"], 300)

    def test_estimate_empty(self):
        tc, _ = _make_cleaner({"root": {}})
        est = tc.estimate("root")
        self.assertEqual(est["total_files"], 0)
        self.assertEqual(est["total_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
