"""Tests for Breadcrumb (Q145 Task 860)."""
from __future__ import annotations

import time
import unittest

from lidco.ux.breadcrumb import Breadcrumb, Crumb


class TestCrumb(unittest.TestCase):
    def test_dataclass_fields(self):
        c = Crumb(label="Home", context="root", timestamp=1.0)
        self.assertEqual(c.label, "Home")
        self.assertEqual(c.context, "root")
        self.assertEqual(c.timestamp, 1.0)


class TestBreadcrumb(unittest.TestCase):
    def setUp(self):
        self.bc = Breadcrumb(max_depth=5)

    def test_initial_depth_zero(self):
        self.assertEqual(self.bc.depth, 0)

    def test_push_increases_depth(self):
        self.bc.push("Home")
        self.assertEqual(self.bc.depth, 1)

    def test_current_returns_last(self):
        self.bc.push("Home")
        self.bc.push("Project")
        self.assertEqual(self.bc.current().label, "Project")

    def test_current_empty_returns_none(self):
        self.assertIsNone(self.bc.current())

    def test_pop_returns_last(self):
        self.bc.push("Home")
        self.bc.push("Project")
        popped = self.bc.pop()
        self.assertEqual(popped.label, "Project")
        self.assertEqual(self.bc.depth, 1)

    def test_pop_empty_returns_none(self):
        self.assertIsNone(self.bc.pop())

    def test_trail_returns_full_list(self):
        self.bc.push("Home")
        self.bc.push("Project")
        self.bc.push("src")
        trail = self.bc.trail()
        self.assertEqual(len(trail), 3)
        self.assertEqual(trail[0].label, "Home")
        self.assertEqual(trail[2].label, "src")

    def test_trail_is_copy(self):
        self.bc.push("Home")
        trail = self.bc.trail()
        trail.clear()
        self.assertEqual(self.bc.depth, 1)

    def test_render_default_separator(self):
        self.bc.push("Home")
        self.bc.push("Project")
        self.bc.push("src")
        self.assertEqual(self.bc.render(), "Home > Project > src")

    def test_render_custom_separator(self):
        self.bc.push("A")
        self.bc.push("B")
        self.assertEqual(self.bc.render(separator=" / "), "A / B")

    def test_render_empty(self):
        self.assertEqual(self.bc.render(), "")

    def test_max_depth_eviction(self):
        for i in range(10):
            self.bc.push(f"c{i}")
        self.assertEqual(self.bc.depth, 5)
        # oldest crumbs evicted
        self.assertEqual(self.bc.trail()[0].label, "c5")

    def test_go_back_single(self):
        self.bc.push("Home")
        self.bc.push("Project")
        removed = self.bc.go_back()
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].label, "Project")
        self.assertEqual(self.bc.depth, 1)

    def test_go_back_multiple(self):
        self.bc.push("A")
        self.bc.push("B")
        self.bc.push("C")
        removed = self.bc.go_back(2)
        self.assertEqual(len(removed), 2)
        self.assertEqual(removed[0].label, "C")
        self.assertEqual(removed[1].label, "B")
        self.assertEqual(self.bc.depth, 1)

    def test_go_back_more_than_available(self):
        self.bc.push("X")
        removed = self.bc.go_back(5)
        self.assertEqual(len(removed), 1)
        self.assertEqual(self.bc.depth, 0)

    def test_clear(self):
        self.bc.push("Home")
        self.bc.push("Project")
        self.bc.clear()
        self.assertEqual(self.bc.depth, 0)

    def test_push_sets_timestamp(self):
        before = time.time()
        self.bc.push("Home")
        after = time.time()
        c = self.bc.current()
        self.assertGreaterEqual(c.timestamp, before)
        self.assertLessEqual(c.timestamp, after)

    def test_push_with_context(self):
        self.bc.push("Home", "root dir")
        self.assertEqual(self.bc.current().context, "root dir")

    def test_default_max_depth(self):
        bc = Breadcrumb()
        self.assertEqual(bc._max_depth, 20)


if __name__ == "__main__":
    unittest.main()
