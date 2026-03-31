"""Tests for Q132 DuplicateFinder."""
from __future__ import annotations
import unittest
from lidco.fs.duplicate_finder import DuplicateFinder, DuplicateGroup


class TestDuplicateGroup(unittest.TestCase):
    def test_wasted_bytes(self):
        group = DuplicateGroup(content_hash="abc", paths=["a.py", "b.py", "c.py"], size=100)
        self.assertEqual(group.wasted_bytes, 200)

    def test_wasted_bytes_two_files(self):
        group = DuplicateGroup(content_hash="abc", paths=["a.py", "b.py"], size=50)
        self.assertEqual(group.wasted_bytes, 50)

    def test_no_wasted_single(self):
        group = DuplicateGroup(content_hash="abc", paths=["a.py"], size=100)
        self.assertEqual(group.wasted_bytes, 0)


class TestDuplicateFinder(unittest.TestCase):
    def setUp(self):
        self.finder = DuplicateFinder()

    def test_no_duplicates(self):
        files = {"a.py": "content a", "b.py": "content b"}
        groups = self.finder.find(files)
        self.assertEqual(groups, [])

    def test_two_identical_files(self):
        files = {"a.py": "same content", "b.py": "same content"}
        groups = self.finder.find(files)
        self.assertEqual(len(groups), 1)
        self.assertEqual(sorted(groups[0].paths), ["a.py", "b.py"])

    def test_three_identical_files(self):
        files = {"a.py": "x", "b.py": "x", "c.py": "x"}
        groups = self.finder.find(files)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].paths), 3)

    def test_multiple_groups(self):
        files = {
            "a.py": "content a",
            "b.py": "content a",
            "c.py": "content b",
            "d.py": "content b",
        }
        groups = self.finder.find(files)
        self.assertEqual(len(groups), 2)

    def test_paths_sorted(self):
        files = {"z.py": "same", "a.py": "same"}
        groups = self.finder.find(files)
        self.assertEqual(groups[0].paths, ["a.py", "z.py"])

    def test_summary_empty(self):
        summary = self.finder.summary([])
        self.assertEqual(summary["groups"], 0)
        self.assertEqual(summary["total_wasted_bytes"], 0)
        self.assertEqual(summary["files_involved"], 0)

    def test_summary_with_groups(self):
        files = {"a.py": "same", "b.py": "same", "c.py": "same"}
        groups = self.finder.find(files)
        summary = self.finder.summary(groups)
        self.assertEqual(summary["groups"], 1)
        self.assertEqual(summary["files_involved"], 3)
        self.assertGreater(summary["total_wasted_bytes"], 0)

    def test_size_recorded(self):
        content = "hello world content"
        files = {"a.py": content, "b.py": content}
        groups = self.finder.find(files)
        self.assertEqual(groups[0].size, len(content.encode()))

    def test_custom_hash_fn(self):
        custom_hash = lambda c: "constant_hash"
        finder = DuplicateFinder(hash_fn=custom_hash)
        files = {"a.py": "aaa", "b.py": "bbb"}
        groups = finder.find(files)
        self.assertEqual(len(groups), 1)

    def test_empty_files_dict(self):
        groups = self.finder.find({})
        self.assertEqual(groups, [])

    def test_unique_content_no_groups(self):
        files = {f"file{i}.py": f"unique content {i}" for i in range(10)}
        groups = self.finder.find(files)
        self.assertEqual(groups, [])

    def test_sorted_by_size_descending(self):
        files = {
            "a.py": "x" * 10,
            "b.py": "x" * 10,
            "c.py": "y" * 100,
            "d.py": "y" * 100,
        }
        groups = self.finder.find(files)
        self.assertEqual(len(groups), 2)
        self.assertGreaterEqual(groups[0].size, groups[1].size)

    def test_content_hash_in_group(self):
        files = {"a.py": "hello", "b.py": "hello"}
        groups = self.finder.find(files)
        self.assertIsNotNone(groups[0].content_hash)
        self.assertNotEqual(groups[0].content_hash, "")


if __name__ == "__main__":
    unittest.main()
