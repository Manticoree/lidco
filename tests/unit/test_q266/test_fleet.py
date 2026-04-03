"""Tests for lidco.enterprise.fleet."""
from __future__ import annotations

import time
import unittest

from lidco.enterprise.fleet import FleetManager, Instance


class TestInstance(unittest.TestCase):
    def test_defaults(self) -> None:
        inst = Instance(id="a", name="n", version="1.0")
        self.assertEqual(inst.status, "healthy")
        self.assertEqual(inst.metadata, {})


class TestFleetManager(unittest.TestCase):
    def setUp(self) -> None:
        self.fm = FleetManager(heartbeat_timeout=1.0)

    def test_register(self) -> None:
        inst = self.fm.register("web-1", "2.0")
        self.assertEqual(inst.name, "web-1")
        self.assertEqual(inst.version, "2.0")
        self.assertEqual(inst.status, "healthy")

    def test_deregister(self) -> None:
        inst = self.fm.register("web-1", "1.0")
        self.assertTrue(self.fm.deregister(inst.id))
        self.assertFalse(self.fm.deregister(inst.id))

    def test_heartbeat(self) -> None:
        inst = self.fm.register("web-1", "1.0")
        old_hb = inst.last_heartbeat
        time.sleep(0.01)
        updated = self.fm.heartbeat(inst.id)
        self.assertIsNotNone(updated)
        self.assertGreater(updated.last_heartbeat, old_hb)  # type: ignore[union-attr]

    def test_heartbeat_missing(self) -> None:
        self.assertIsNone(self.fm.heartbeat("nope"))

    def test_heartbeat_revives_offline(self) -> None:
        inst = self.fm.register("web-1", "1.0")
        inst.status = "offline"
        self.fm.heartbeat(inst.id)
        self.assertEqual(inst.status, "healthy")

    def test_get(self) -> None:
        inst = self.fm.register("web-1", "1.0")
        self.assertEqual(self.fm.get(inst.id), inst)
        self.assertIsNone(self.fm.get("missing"))

    def test_check_health_marks_offline(self) -> None:
        inst = self.fm.register("web-1", "1.0")
        inst.last_heartbeat = time.time() - 500
        health = self.fm.check_health()
        self.assertEqual(health["offline"], 1)
        self.assertEqual(inst.status, "offline")

    def test_by_status(self) -> None:
        self.fm.register("a", "1.0")
        inst = self.fm.register("b", "1.0")
        inst.status = "degraded"
        self.assertEqual(len(self.fm.by_status("healthy")), 1)
        self.assertEqual(len(self.fm.by_status("degraded")), 1)

    def test_by_version(self) -> None:
        self.fm.register("a", "1.0")
        self.fm.register("b", "2.0")
        self.fm.register("c", "1.0")
        self.assertEqual(len(self.fm.by_version("1.0")), 2)

    def test_all_instances(self) -> None:
        self.fm.register("a", "1.0")
        self.fm.register("b", "2.0")
        self.assertEqual(len(self.fm.all_instances()), 2)

    def test_summary(self) -> None:
        self.fm.register("a", "1.0")
        self.fm.register("b", "2.0")
        s = self.fm.summary()
        self.assertEqual(s["total"], 2)
        self.assertIn("healthy", s["by_status"])

    def test_register_with_metadata(self) -> None:
        inst = self.fm.register("a", "1.0", metadata={"env": "prod"})
        self.assertEqual(inst.metadata["env"], "prod")


if __name__ == "__main__":
    unittest.main()
