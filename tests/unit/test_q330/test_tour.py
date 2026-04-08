"""Tests for src/lidco/onboard/tour.py — CodebaseTour."""

from __future__ import annotations

import unittest

from lidco.onboard.tour import ArchitectureOverview, CodebaseTour, TourProgress, TourStop


class TestTourStop(unittest.TestCase):
    def test_defaults(self) -> None:
        stop = TourStop(name="main", path="src/main.py", description="Entry point")
        self.assertEqual(stop.name, "main")
        self.assertEqual(stop.path, "src/main.py")
        self.assertEqual(stop.description, "Entry point")
        self.assertEqual(stop.category, "general")
        self.assertEqual(stop.order, 0)
        self.assertEqual(stop.highlights, [])

    def test_custom_fields(self) -> None:
        stop = TourStop(
            name="config",
            path="src/config.py",
            description="Config",
            category="core",
            order=2,
            highlights=["dataclass", "validation"],
        )
        self.assertEqual(stop.category, "core")
        self.assertEqual(stop.order, 2)
        self.assertEqual(stop.highlights, ["dataclass", "validation"])

    def test_frozen(self) -> None:
        stop = TourStop(name="a", path="b", description="c")
        with self.assertRaises(AttributeError):
            stop.name = "x"  # type: ignore[misc]


class TestTourProgress(unittest.TestCase):
    def test_empty(self) -> None:
        p = TourProgress()
        self.assertEqual(p.visited_count, 0)
        self.assertEqual(p.percent, 0.0)
        # 0 visited >= 0 total means trivially complete
        self.assertTrue(p.complete)

    def test_incomplete(self) -> None:
        p = TourProgress(total=3)
        self.assertFalse(p.complete)

    def test_with_visits(self) -> None:
        p = TourProgress(total=3, visited=["a", "b"])
        self.assertEqual(p.visited_count, 2)
        self.assertAlmostEqual(p.percent, 66.7)
        self.assertFalse(p.complete)

    def test_complete(self) -> None:
        p = TourProgress(total=2, visited=["a", "b"])
        self.assertTrue(p.complete)


class TestCodebaseTour(unittest.TestCase):
    def _make_tour(self) -> CodebaseTour:
        tour = CodebaseTour(root_dir="/project")
        tour.add_stop(TourStop(name="cli", path="src/cli.py", description="CLI", category="ui", order=1))
        tour.add_stop(TourStop(name="core", path="src/core.py", description="Core", category="core", order=0))
        tour.add_stop(TourStop(name="api", path="src/api.py", description="API", category="core", order=2))
        return tour

    def test_root_dir(self) -> None:
        tour = CodebaseTour(root_dir="/foo")
        self.assertEqual(tour.root_dir, "/foo")

    def test_add_stop(self) -> None:
        tour = self._make_tour()
        self.assertEqual(len(tour.stops), 3)
        self.assertEqual(tour.progress.total, 3)

    def test_add_stops(self) -> None:
        tour = CodebaseTour()
        stops = [
            TourStop(name="a", path="a.py", description="A"),
            TourStop(name="b", path="b.py", description="B"),
        ]
        tour.add_stops(stops)
        self.assertEqual(len(tour.stops), 2)

    def test_visit_existing(self) -> None:
        tour = self._make_tour()
        stop = tour.visit("cli")
        self.assertIsNotNone(stop)
        self.assertEqual(stop.name, "cli")
        self.assertEqual(tour.progress.visited_count, 1)

    def test_visit_idempotent(self) -> None:
        tour = self._make_tour()
        tour.visit("cli")
        tour.visit("cli")
        self.assertEqual(tour.progress.visited_count, 1)

    def test_visit_nonexistent(self) -> None:
        tour = self._make_tour()
        result = tour.visit("missing")
        self.assertIsNone(result)

    def test_next_stop_respects_order(self) -> None:
        tour = self._make_tour()
        nxt = tour.next_stop()
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.name, "core")  # order=0

    def test_next_stop_skips_visited(self) -> None:
        tour = self._make_tour()
        tour.visit("core")
        nxt = tour.next_stop()
        self.assertEqual(nxt.name, "cli")  # order=1

    def test_next_stop_none_when_all_visited(self) -> None:
        tour = self._make_tour()
        tour.visit("cli")
        tour.visit("core")
        tour.visit("api")
        self.assertIsNone(tour.next_stop())

    def test_stops_by_category(self) -> None:
        tour = self._make_tour()
        core_stops = tour.stops_by_category("core")
        self.assertEqual(len(core_stops), 2)
        self.assertEqual(tour.stops_by_category("missing"), [])

    def test_categories(self) -> None:
        tour = self._make_tour()
        cats = tour.categories()
        self.assertEqual(cats, ["core", "ui"])

    def test_reset(self) -> None:
        tour = self._make_tour()
        tour.visit("cli")
        tour.reset()
        self.assertEqual(tour.progress.visited_count, 0)
        self.assertEqual(tour.progress.total, 3)

    def test_architecture_overview(self) -> None:
        tour = self._make_tour()
        ov = tour.architecture_overview()
        self.assertIsInstance(ov, ArchitectureOverview)
        self.assertIn("project", ov.name)
        self.assertGreater(len(ov.layers), 0)

    def test_key_files(self) -> None:
        tour = self._make_tour()
        files = tour.key_files()
        self.assertEqual(len(files), 3)
        self.assertIn("name", files[0])
        self.assertIn("path", files[0])

    def test_summary_incomplete(self) -> None:
        tour = self._make_tour()
        s = tour.summary()
        self.assertIn("Stops: 3", s)
        self.assertIn("0/3", s)
        self.assertIn("Next:", s)

    def test_summary_complete(self) -> None:
        tour = self._make_tour()
        tour.visit("cli")
        tour.visit("core")
        tour.visit("api")
        s = tour.summary()
        self.assertIn("COMPLETE", s)


if __name__ == "__main__":
    unittest.main()
