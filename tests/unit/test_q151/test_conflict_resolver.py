"""Tests for ConflictResolver."""
from __future__ import annotations

import unittest

from lidco.merge.three_way import MergeConflict, MergeResult, ThreeWayMerge
from lidco.merge.conflict_resolver import ConflictResolver, Resolution


class TestResolution(unittest.TestCase):
    def test_dataclass_fields(self):
        r = Resolution(conflict_index=0, strategy="ours", resolved_text="text")
        self.assertEqual(r.conflict_index, 0)
        self.assertEqual(r.strategy, "ours")
        self.assertEqual(r.resolved_text, "text")


class TestConflictResolver(unittest.TestCase):
    def setUp(self):
        self.resolver = ConflictResolver()
        self.conflict = MergeConflict(
            start_line=1,
            base_text="base\n",
            ours_text="ours\n",
            theirs_text="theirs\n",
        )

    def test_resolve_ours(self):
        r = self.resolver.resolve_ours(self.conflict)
        self.assertEqual(r.strategy, "ours")
        self.assertEqual(r.resolved_text, "ours\n")

    def test_resolve_theirs(self):
        r = self.resolver.resolve_theirs(self.conflict)
        self.assertEqual(r.strategy, "theirs")
        self.assertEqual(r.resolved_text, "theirs\n")

    def test_resolve_both(self):
        r = self.resolver.resolve_both(self.conflict)
        self.assertEqual(r.strategy, "both")
        self.assertIn("ours", r.resolved_text)
        self.assertIn("theirs", r.resolved_text)

    def test_resolve_custom(self):
        r = self.resolver.resolve_custom(self.conflict, "custom text")
        self.assertEqual(r.strategy, "custom")
        self.assertEqual(r.resolved_text, "custom text")

    def test_apply_resolutions_no_conflicts(self):
        result = MergeResult(merged="clean text", has_conflicts=False)
        out = self.resolver.apply_resolutions(result, [])
        self.assertEqual(out, "clean text")

    def test_apply_resolutions_single(self):
        merger = ThreeWayMerge()
        base = "a\nb\n"
        ours = "a\nX\n"
        theirs = "a\nY\n"
        result = merger.merge(base, ours, theirs)
        self.assertTrue(result.has_conflicts)

        r = self.resolver.resolve_ours(result.conflicts[0])
        r.conflict_index = 0
        final = self.resolver.apply_resolutions(result, [r])
        self.assertIn("X", final)
        self.assertNotIn("<<<<<<", final)

    def test_apply_resolutions_theirs(self):
        merger = ThreeWayMerge()
        base = "a\nb\n"
        ours = "a\nX\n"
        theirs = "a\nY\n"
        result = merger.merge(base, ours, theirs)

        r = self.resolver.resolve_theirs(result.conflicts[0])
        r.conflict_index = 0
        final = self.resolver.apply_resolutions(result, [r])
        self.assertIn("Y", final)

    def test_apply_resolutions_both(self):
        merger = ThreeWayMerge()
        base = "a\nb\n"
        ours = "a\nX\n"
        theirs = "a\nY\n"
        result = merger.merge(base, ours, theirs)

        r = self.resolver.resolve_both(result.conflicts[0])
        r.conflict_index = 0
        final = self.resolver.apply_resolutions(result, [r])
        self.assertIn("X", final)
        self.assertIn("Y", final)

    def test_apply_resolutions_custom(self):
        merger = ThreeWayMerge()
        base = "a\nb\n"
        ours = "a\nX\n"
        theirs = "a\nY\n"
        result = merger.merge(base, ours, theirs)

        r = self.resolver.resolve_custom(result.conflicts[0], "CUSTOM\n")
        r.conflict_index = 0
        final = self.resolver.apply_resolutions(result, [r])
        self.assertIn("CUSTOM", final)

    def test_auto_resolve_whitespace_only(self):
        conflict = MergeConflict(
            start_line=1,
            base_text="base\n",
            ours_text="  same  \n",
            theirs_text="same\n",
        )
        resolutions = self.resolver.auto_resolve([conflict])
        self.assertEqual(len(resolutions), 1)
        self.assertEqual(resolutions[0].strategy, "ours")

    def test_auto_resolve_no_trivial(self):
        conflict = MergeConflict(
            start_line=1,
            base_text="base\n",
            ours_text="different_a\n",
            theirs_text="different_b\n",
        )
        resolutions = self.resolver.auto_resolve([conflict])
        self.assertEqual(len(resolutions), 0)

    def test_auto_resolve_empty_strings(self):
        conflict = MergeConflict(
            start_line=0,
            base_text="",
            ours_text="   \n",
            theirs_text="\n",
        )
        resolutions = self.resolver.auto_resolve([conflict])
        self.assertEqual(len(resolutions), 1)

    def test_auto_resolve_multiple(self):
        c1 = MergeConflict(start_line=0, base_text="", ours_text="a\n", theirs_text=" a \n")
        c2 = MergeConflict(start_line=5, base_text="", ours_text="X\n", theirs_text="Y\n")
        resolutions = self.resolver.auto_resolve([c1, c2])
        self.assertEqual(len(resolutions), 1)
        self.assertEqual(resolutions[0].conflict_index, 0)

    def test_resolve_ours_returns_resolution(self):
        r = self.resolver.resolve_ours(self.conflict)
        self.assertIsInstance(r, Resolution)

    def test_resolve_both_concatenation(self):
        c = MergeConflict(start_line=0, base_text="", ours_text="A", theirs_text="B")
        r = self.resolver.resolve_both(c)
        self.assertEqual(r.resolved_text, "AB")

    def test_conflict_index_default(self):
        r = self.resolver.resolve_ours(self.conflict)
        self.assertEqual(r.conflict_index, 0)

    def test_apply_resolutions_preserves_non_conflict_lines(self):
        merger = ThreeWayMerge()
        base = "header\na\nfooter\n"
        ours = "header\nX\nfooter\n"
        theirs = "header\nY\nfooter\n"
        result = merger.merge(base, ours, theirs)

        r = self.resolver.resolve_ours(result.conflicts[0])
        r.conflict_index = 0
        final = self.resolver.apply_resolutions(result, [r])
        self.assertIn("header", final)
        self.assertIn("footer", final)


if __name__ == "__main__":
    unittest.main()
