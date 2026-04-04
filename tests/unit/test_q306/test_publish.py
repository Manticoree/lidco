"""Tests for PublishOrchestrator."""

import unittest

from lidco.monorepo.publish import PublishOrchestrator


class TestPublishOrchestrator(unittest.TestCase):
    def _make_orch(self) -> PublishOrchestrator:
        o = PublishOrchestrator()
        o.add_package("core", "1.0.0", [])
        o.add_package("utils", "1.2.0", ["core"])
        o.add_package("web", "2.0.0", ["utils", "core"])
        return o

    # -- publish_order ------------------------------------------------

    def test_publish_order_deps_first(self):
        o = self._make_orch()
        order = o.publish_order()
        self.assertLess(order.index("core"), order.index("utils"))
        self.assertLess(order.index("utils"), order.index("web"))

    def test_publish_order_single(self):
        o = PublishOrchestrator()
        o.add_package("solo", "1.0.0")
        self.assertEqual(o.publish_order(), ["solo"])

    # -- bump_all -----------------------------------------------------

    def test_bump_patch(self):
        o = self._make_orch()
        result = o.bump_all("patch")
        self.assertEqual(result["core"], "1.0.1")
        self.assertEqual(result["utils"], "1.2.1")
        self.assertEqual(result["web"], "2.0.1")

    def test_bump_minor(self):
        o = self._make_orch()
        result = o.bump_all("minor")
        self.assertEqual(result["core"], "1.1.0")
        self.assertEqual(result["utils"], "1.3.0")
        self.assertEqual(result["web"], "2.1.0")

    def test_bump_major(self):
        o = self._make_orch()
        result = o.bump_all("major")
        self.assertEqual(result["core"], "2.0.0")
        self.assertEqual(result["utils"], "2.0.0")
        self.assertEqual(result["web"], "3.0.0")

    # -- canary_versions ----------------------------------------------

    def test_canary_versions_format(self):
        o = self._make_orch()
        canaries = o.canary_versions()
        self.assertEqual(len(canaries), 3)
        for name, ver in canaries.items():
            self.assertIn("-canary.", ver)
            self.assertTrue(ver.startswith({"core": "1.0.0", "utils": "1.2.0", "web": "2.0.0"}[name]))

    # -- rollback_plan ------------------------------------------------

    def test_rollback_plan_empty_initially(self):
        o = self._make_orch()
        self.assertEqual(o.rollback_plan(), [])

    def test_rollback_plan_after_bump(self):
        o = self._make_orch()
        o.bump_all("patch")
        plan = o.rollback_plan()
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["core"], "1.0.0")

    def test_rollback_plan_multiple_bumps(self):
        o = self._make_orch()
        o.bump_all("patch")
        o.bump_all("minor")
        plan = o.rollback_plan()
        self.assertEqual(len(plan), 2)
        # Most recent first
        self.assertEqual(plan[0]["core"], "1.0.1")
        self.assertEqual(plan[1]["core"], "1.0.0")

    # -- status -------------------------------------------------------

    def test_status_keys(self):
        o = self._make_orch()
        st = o.status()
        self.assertEqual(st["total"], 3)
        self.assertIn("packages", st)
        self.assertIn("core", st["packages"])
        self.assertEqual(st["packages"]["core"]["version"], "1.0.0")

    def test_status_after_bump(self):
        o = self._make_orch()
        o.bump_all("patch")
        st = o.status()
        self.assertEqual(st["packages"]["core"]["version"], "1.0.1")

    # -- add_package --------------------------------------------------

    def test_add_package_defaults(self):
        o = PublishOrchestrator()
        o.add_package("x")
        st = o.status()
        self.assertEqual(st["packages"]["x"]["version"], "0.0.0")
        self.assertEqual(st["packages"]["x"]["deps"], [])


if __name__ == "__main__":
    unittest.main()
