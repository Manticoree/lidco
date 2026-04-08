"""Tests for lidco.dr.failover — FailoverOrchestrator."""

from __future__ import annotations

import unittest

from lidco.dr.failover import (
    FailoverEvent,
    FailoverOrchestrator,
    FailoverStatus,
    HealthCheck,
    Node,
    NodeStatus,
)


class TestNode(unittest.TestCase):
    def test_valid_node(self) -> None:
        n = Node(node_id="n1", name="Primary", endpoint="http://localhost")
        self.assertEqual(n.node_id, "n1")
        self.assertFalse(n.is_primary)

    def test_empty_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            Node(node_id="", name="X", endpoint="http://x")

    def test_empty_endpoint_raises(self) -> None:
        with self.assertRaises(ValueError):
            Node(node_id="n1", name="X", endpoint="")


class TestFailoverOrchestrator(unittest.TestCase):
    def _orch(self) -> FailoverOrchestrator:
        o = FailoverOrchestrator(failure_threshold=3)
        o.register_node(Node(
            node_id="primary",
            name="Primary",
            endpoint="http://primary",
            is_primary=True,
        ))
        o.register_node(Node(
            node_id="secondary",
            name="Secondary",
            endpoint="http://secondary",
            status=NodeStatus.HEALTHY,
        ))
        return o

    def test_register_and_list_nodes(self) -> None:
        o = self._orch()
        self.assertEqual(len(o.nodes), 2)

    def test_remove_node(self) -> None:
        o = self._orch()
        self.assertTrue(o.remove_node("secondary"))
        self.assertEqual(len(o.nodes), 1)
        self.assertFalse(o.remove_node("nonexistent"))

    def test_get_primary(self) -> None:
        o = self._orch()
        p = o.get_primary()
        self.assertIsNotNone(p)
        self.assertEqual(p.node_id, "primary")

    def test_get_secondaries(self) -> None:
        o = self._orch()
        secs = o.get_secondaries()
        self.assertEqual(len(secs), 1)
        self.assertEqual(secs[0].node_id, "secondary")

    def test_check_health_default(self) -> None:
        o = self._orch()
        hc = o.check_health("primary")
        self.assertEqual(hc.status, NodeStatus.HEALTHY)

    def test_check_health_unknown_node(self) -> None:
        o = self._orch()
        hc = o.check_health("missing")
        self.assertEqual(hc.status, NodeStatus.UNKNOWN)

    def test_check_health_custom_checker(self) -> None:
        o = self._orch()
        o.set_health_checker(
            lambda node: HealthCheck(
                node_id=node.node_id,
                status=NodeStatus.UNHEALTHY,
                checked_at=1000.0,
            )
        )
        hc = o.check_health("primary")
        self.assertEqual(hc.status, NodeStatus.UNHEALTHY)

    def test_check_all_health(self) -> None:
        o = self._orch()
        checks = o.check_all_health()
        self.assertEqual(len(checks), 2)

    def test_needs_failover_false(self) -> None:
        o = self._orch()
        self.assertFalse(o.needs_failover())

    def test_needs_failover_true(self) -> None:
        o = self._orch()
        o.set_health_checker(
            lambda node: HealthCheck(
                node_id=node.node_id,
                status=NodeStatus.UNHEALTHY if node.is_primary else NodeStatus.HEALTHY,
                checked_at=1000.0,
            )
        )
        for _ in range(3):
            o.check_health("primary")
        self.assertTrue(o.needs_failover())

    def test_execute_failover(self) -> None:
        o = self._orch()
        evt = o.execute_failover()
        self.assertEqual(evt.status, FailoverStatus.COMPLETED)
        self.assertEqual(evt.from_node, "primary")
        self.assertEqual(evt.to_node, "secondary")
        # Roles should be swapped
        self.assertTrue(o.nodes["secondary"].is_primary)
        self.assertFalse(o.nodes["primary"].is_primary)

    def test_execute_failover_specific_target(self) -> None:
        o = self._orch()
        evt = o.execute_failover(target_id="secondary")
        self.assertEqual(evt.status, FailoverStatus.COMPLETED)
        self.assertEqual(evt.to_node, "secondary")

    def test_failover_no_primary(self) -> None:
        o = FailoverOrchestrator()
        o.register_node(Node(node_id="a", name="A", endpoint="http://a"))
        evt = o.execute_failover()
        self.assertEqual(evt.status, FailoverStatus.FAILED)
        self.assertIn("No primary", evt.error)

    def test_failover_no_target(self) -> None:
        o = FailoverOrchestrator()
        o.register_node(Node(
            node_id="solo", name="Solo", endpoint="http://solo", is_primary=True
        ))
        evt = o.execute_failover()
        self.assertEqual(evt.status, FailoverStatus.FAILED)
        self.assertIn("No suitable target", evt.error)

    def test_failover_data_verification_failure(self) -> None:
        o = self._orch()
        o.set_data_verifier(lambda src, dst: False)
        evt = o.execute_failover()
        self.assertEqual(evt.status, FailoverStatus.FAILED)
        self.assertIn("Data sync", evt.error)

    def test_dns_switcher_called(self) -> None:
        o = self._orch()
        calls: list[tuple[str, str]] = []
        o.set_dns_switcher(lambda src, dst: (calls.append((src, dst)) or True))
        evt = o.execute_failover()
        self.assertEqual(evt.status, FailoverStatus.COMPLETED)
        self.assertTrue(evt.dns_switched)
        self.assertEqual(len(calls), 1)

    def test_notifier_called(self) -> None:
        o = self._orch()
        events: list[FailoverEvent] = []
        o.set_notifier(lambda e: events.append(e))
        evt = o.execute_failover()
        self.assertEqual(evt.notifications_sent, 1)
        self.assertEqual(len(events), 1)

    def test_rollback(self) -> None:
        o = self._orch()
        evt = o.execute_failover()
        rollback = o.rollback(evt.event_id)
        self.assertIsNotNone(rollback)
        self.assertEqual(rollback.status, FailoverStatus.COMPLETED)
        # Primary should be restored
        self.assertTrue(o.nodes["primary"].is_primary)

    def test_rollback_nonexistent(self) -> None:
        o = self._orch()
        self.assertIsNone(o.rollback("nonexistent"))

    def test_events_tracked(self) -> None:
        o = self._orch()
        o.execute_failover()
        self.assertEqual(len(o.events), 1)


if __name__ == "__main__":
    unittest.main()
