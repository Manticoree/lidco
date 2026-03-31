"""Tests for PatchGenerator."""
from __future__ import annotations

import unittest

from lidco.merge.patch_generator import PatchFile, PatchGenerator


class TestPatchFile(unittest.TestCase):
    def test_dataclass_fields(self):
        p = PatchFile(file_path="a.py", old_content="old", new_content="new", hunks=["@@ -1 +1 @@"])
        self.assertEqual(p.file_path, "a.py")
        self.assertEqual(p.old_content, "old")
        self.assertEqual(p.new_content, "new")
        self.assertEqual(len(p.hunks), 1)

    def test_defaults(self):
        p = PatchFile(file_path="b.py", old_content="", new_content="")
        self.assertEqual(p.hunks, [])


class TestPatchGenerator(unittest.TestCase):
    def setUp(self):
        self.pg = PatchGenerator()

    def test_generate_empty_diff(self):
        patch = self.pg.generate("f.py", "same\n", "same\n")
        self.assertEqual(patch, "")

    def test_generate_simple_change(self):
        patch = self.pg.generate("f.py", "old\n", "new\n")
        self.assertIn("--- a/f.py", patch)
        self.assertIn("+++ b/f.py", patch)
        self.assertIn("-old", patch)
        self.assertIn("+new", patch)

    def test_generate_addition(self):
        patch = self.pg.generate("f.py", "a\n", "a\nb\n")
        self.assertIn("+b", patch)

    def test_generate_deletion(self):
        patch = self.pg.generate("f.py", "a\nb\n", "a\n")
        self.assertIn("-b", patch)

    def test_generate_context_lines(self):
        old = "a\nb\nc\nd\ne\n"
        new = "a\nb\nX\nd\ne\n"
        patch = self.pg.generate("f.py", old, new, context_lines=1)
        self.assertIn("@@", patch)

    def test_generate_multi_single(self):
        files = [("a.py", "old\n", "new\n")]
        patch = self.pg.generate_multi(files)
        self.assertIn("a.py", patch)

    def test_generate_multi_multiple(self):
        files = [
            ("a.py", "old\n", "new\n"),
            ("b.py", "x\n", "y\n"),
        ]
        patch = self.pg.generate_multi(files)
        self.assertIn("a.py", patch)
        self.assertIn("b.py", patch)

    def test_generate_multi_no_diff(self):
        files = [("a.py", "same\n", "same\n")]
        patch = self.pg.generate_multi(files)
        self.assertEqual(patch, "")

    def test_parse_patch_single(self):
        patch = self.pg.generate("f.py", "old\n", "new\n")
        parsed = self.pg.parse_patch(patch)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].file_path, "f.py")

    def test_parse_patch_content(self):
        patch = self.pg.generate("f.py", "old\n", "new\n")
        parsed = self.pg.parse_patch(patch)
        self.assertIn("old", parsed[0].old_content)
        self.assertIn("new", parsed[0].new_content)

    def test_parse_patch_hunks(self):
        patch = self.pg.generate("f.py", "old\n", "new\n")
        parsed = self.pg.parse_patch(patch)
        self.assertGreater(len(parsed[0].hunks), 0)

    def test_parse_patch_multi(self):
        files = [("a.py", "x\n", "y\n"), ("b.py", "1\n", "2\n")]
        patch = self.pg.generate_multi(files)
        parsed = self.pg.parse_patch(patch)
        self.assertEqual(len(parsed), 2)

    def test_parse_patch_empty(self):
        parsed = self.pg.parse_patch("")
        self.assertEqual(parsed, [])

    def test_apply_simple(self):
        old = "hello\nworld\n"
        new = "hello\nearth\n"
        patch = self.pg.generate("f.py", old, new)
        result = self.pg.apply(old, patch)
        self.assertIn("earth", result)

    def test_apply_addition(self):
        old = "a\nb\n"
        new = "a\nb\nc\n"
        patch = self.pg.generate("f.py", old, new)
        result = self.pg.apply(old, patch)
        self.assertIn("c", result)

    def test_apply_deletion(self):
        old = "a\nb\nc\n"
        new = "a\nc\n"
        patch = self.pg.generate("f.py", old, new)
        result = self.pg.apply(old, patch)
        self.assertNotIn("b", result)

    def test_reverse_patch(self):
        patch = self.pg.generate("f.py", "old\n", "new\n")
        rev = self.pg.reverse(patch)
        self.assertIn("+old", rev)
        self.assertIn("-new", rev)

    def test_reverse_swaps_file_headers(self):
        patch = self.pg.generate("f.py", "a\n", "b\n")
        rev = self.pg.reverse(patch)
        # The --- and +++ should swap
        self.assertIn("--- a/f.py", rev)
        self.assertIn("+++ b/f.py", rev)

    def test_apply_no_change(self):
        old = "hello\n"
        patch = self.pg.generate("f.py", old, old)
        result = self.pg.apply(old, patch)
        self.assertEqual(result, old)

    def test_generate_preserves_path(self):
        patch = self.pg.generate("deep/path/file.py", "a\n", "b\n")
        self.assertIn("deep/path/file.py", patch)

    def test_apply_roundtrip(self):
        old = "line1\nline2\nline3\n"
        new = "line1\nmodified\nline3\n"
        patch = self.pg.generate("f.py", old, new)
        result = self.pg.apply(old, patch)
        self.assertEqual(result, new)


if __name__ == "__main__":
    unittest.main()
