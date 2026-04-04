"""Tests for AffectedFinder."""

import unittest

from lidco.monorepo.affected import AffectedFinder


class TestAffectedFinder(unittest.TestCase):
    def _make_finder(self) -> AffectedFinder:
        f = AffectedFinder()
        f.add_package("core", "packages/core", [])
        f.add_package("utils", "packages/utils", ["core"])
        f.add_package("web", "packages/web", ["utils", "core"])
        f.add_package("docs", "packages/docs", [])
        return f

    # -- find_affected ------------------------------------------------

    def test_find_affected_direct(self):
        f = self._make_finder()
        affected = f.find_affected(["packages/docs/readme.md"])
        self.assertEqual(affected, ["docs"])

    def test_find_affected_transitive(self):
        f = self._make_finder()
        affected = f.find_affected(["packages/core/src/index.ts"])
        self.assertIn("core", affected)
        self.assertIn("utils", affected)
        self.assertIn("web", affected)
        self.assertNotIn("docs", affected)

    def test_find_affected_no_match(self):
        f = self._make_finder()
        affected = f.find_affected(["unrelated/file.txt"])
        self.assertEqual(affected, [])

    def test_find_affected_multiple_files(self):
        f = self._make_finder()
        affected = f.find_affected(["packages/core/a.ts", "packages/docs/b.md"])
        self.assertIn("core", affected)
        self.assertIn("docs", affected)

    # -- transitive_deps ----------------------------------------------

    def test_transitive_deps_leaf(self):
        f = self._make_finder()
        self.assertEqual(f.transitive_deps("core"), set())

    def test_transitive_deps_deep(self):
        f = self._make_finder()
        self.assertEqual(f.transitive_deps("web"), {"utils", "core"})

    def test_transitive_deps_one_level(self):
        f = self._make_finder()
        self.assertEqual(f.transitive_deps("utils"), {"core"})

    def test_transitive_deps_unknown_package(self):
        f = self._make_finder()
        self.assertEqual(f.transitive_deps("nonexistent"), set())

    # -- optimize_test / optimize_build --------------------------------

    def test_optimize_test_order(self):
        f = self._make_finder()
        order = f.optimize_test(["core", "utils", "web"])
        self.assertEqual(order.index("core"), 0)
        self.assertLess(order.index("utils"), order.index("web"))

    def test_optimize_build_order(self):
        f = self._make_finder()
        order = f.optimize_build(["utils", "core"])
        self.assertEqual(order[0], "core")

    def test_optimize_test_single(self):
        f = self._make_finder()
        self.assertEqual(f.optimize_test(["docs"]), ["docs"])

    # -- add_package --------------------------------------------------

    def test_add_package_no_deps(self):
        f = AffectedFinder()
        f.add_package("solo", "packages/solo")
        affected = f.find_affected(["packages/solo/x.py"])
        self.assertEqual(affected, ["solo"])


if __name__ == "__main__":
    unittest.main()
