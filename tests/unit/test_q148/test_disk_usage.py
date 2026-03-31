"""Tests for Q148 DiskUsageAnalyzer."""
from __future__ import annotations

import os
import unittest
from lidco.maintenance.disk_usage import DiskUsageAnalyzer, UsageEntry, _format_size


class TestUsageEntry(unittest.TestCase):
    def test_fields(self):
        e = UsageEntry(path="/a", size_bytes=1024, file_count=5, is_dir=True)
        self.assertEqual(e.path, "/a")
        self.assertEqual(e.size_bytes, 1024)
        self.assertEqual(e.file_count, 5)
        self.assertTrue(e.is_dir)


class TestFormatSize(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(_format_size(500), "500 B")

    def test_kilobytes(self):
        self.assertIn("KB", _format_size(2048))

    def test_megabytes(self):
        self.assertIn("MB", _format_size(5 * 1024 * 1024))

    def test_gigabytes(self):
        self.assertIn("GB", _format_size(2 * 1024 * 1024 * 1024))

    def test_zero(self):
        self.assertEqual(_format_size(0), "0 B")


def _fake_walk(tree: dict, root: str = ""):
    """Yield (dirpath, dirs, files) from a nested dict."""
    dirs = []
    files = []
    for k, v in tree.items():
        if isinstance(v, dict):
            dirs.append(k)
        else:
            files.append(k)
    yield root or ".", dirs, files
    for d in dirs:
        child_path = os.path.join(root or ".", d)
        yield from _fake_walk(tree[d], child_path)


class TestAnalyze(unittest.TestCase):
    def test_single_dir(self):
        def walk(root):
            yield root, [], ["a.py", "b.py"]
        analyzer = DiskUsageAnalyzer(_walk=walk)
        with unittest.mock.patch("os.path.getsize", return_value=100):
            entries = analyzer.analyze("/project")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].file_count, 2)

    def test_nested_dirs(self):
        def walk(root):
            yield root, ["sub"], ["a.py"]
            yield os.path.join(root, "sub"), [], ["b.py"]
        analyzer = DiskUsageAnalyzer(_walk=walk)
        with unittest.mock.patch("os.path.getsize", return_value=50):
            entries = analyzer.analyze("/project")
        self.assertEqual(len(entries), 2)

    def test_empty_dir(self):
        def walk(root):
            yield root, [], []
        analyzer = DiskUsageAnalyzer(_walk=walk)
        entries = analyzer.analyze("/project")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].size_bytes, 0)
        self.assertEqual(entries[0].file_count, 0)

    def test_getsize_error(self):
        def walk(root):
            yield root, [], ["broken.py"]
        def bad_getsize(path):
            raise OSError("no")
        analyzer = DiskUsageAnalyzer(_walk=walk)
        with unittest.mock.patch("os.path.getsize", side_effect=bad_getsize):
            entries = analyzer.analyze("/project")
        self.assertEqual(entries[0].size_bytes, 0)
        self.assertEqual(entries[0].file_count, 1)


class TestLargest(unittest.TestCase):
    def test_top_n(self):
        def walk(root):
            yield root, ["a", "b", "c"], []
            yield os.path.join(root, "a"), [], ["f1"]
            yield os.path.join(root, "b"), [], ["f2"]
            yield os.path.join(root, "c"), [], ["f3"]
        sizes = {
            os.path.join("/r", "a", "f1"): 100,
            os.path.join("/r", "b", "f2"): 300,
            os.path.join("/r", "c", "f3"): 200,
        }
        analyzer = DiskUsageAnalyzer(_walk=walk)
        with unittest.mock.patch("os.path.getsize", side_effect=lambda p: sizes.get(p, 0)):
            top = analyzer.largest("/r", n=2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].size_bytes, 300)

    def test_top_n_more_than_available(self):
        def walk(root):
            yield root, [], ["f"]
        analyzer = DiskUsageAnalyzer(_walk=walk)
        with unittest.mock.patch("os.path.getsize", return_value=10):
            top = analyzer.largest("/r", n=100)
        self.assertEqual(len(top), 1)


class TestByExtension(unittest.TestCase):
    def test_groups_by_ext(self):
        entries = [
            UsageEntry("a.py", 100, 1, False),
            UsageEntry("b.py", 200, 1, False),
            UsageEntry("c.js", 50, 1, False),
        ]
        result = DiskUsageAnalyzer.by_extension(entries)
        self.assertEqual(result[".py"], 300)
        self.assertEqual(result[".js"], 50)

    def test_no_ext(self):
        entries = [UsageEntry("Makefile", 10, 1, False)]
        result = DiskUsageAnalyzer.by_extension(entries)
        self.assertIn("(no ext)", result)

    def test_empty(self):
        result = DiskUsageAnalyzer.by_extension([])
        self.assertEqual(result, {})


class TestTotalSize(unittest.TestCase):
    def test_sum(self):
        entries = [
            UsageEntry("a", 100, 1, True),
            UsageEntry("b", 200, 2, True),
        ]
        self.assertEqual(DiskUsageAnalyzer.total_size(entries), 300)

    def test_empty(self):
        self.assertEqual(DiskUsageAnalyzer.total_size([]), 0)


class TestFormatTree(unittest.TestCase):
    def test_empty_entries(self):
        analyzer = DiskUsageAnalyzer()
        self.assertEqual(analyzer.format_tree([]), "(empty)")

    def test_single_entry(self):
        analyzer = DiskUsageAnalyzer()
        entries = [UsageEntry("/project", 1024, 5, True)]
        result = analyzer.format_tree(entries)
        self.assertIn("project", result)
        self.assertIn("5 files", result)

    def test_max_depth_filtering(self):
        analyzer = DiskUsageAnalyzer()
        entries = [
            UsageEntry("/p", 100, 1, True),
            UsageEntry("/p/a", 50, 1, True),
            UsageEntry("/p/a/b", 25, 1, True),
            UsageEntry("/p/a/b/c", 10, 1, True),
            UsageEntry("/p/a/b/c/d", 5, 1, True),
        ]
        result = analyzer.format_tree(entries, max_depth=2)
        self.assertNotIn("d/", result)


if __name__ == "__main__":
    unittest.main()
