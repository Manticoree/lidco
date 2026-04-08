"""Tests for lidco.chaos.injector."""

from __future__ import annotations

import time
import unittest
from unittest import mock

from lidco.chaos.injector import (
    FaultConfig,
    FaultInjector,
    FaultStatus,
    FaultType,
    InjectedFault,
)


class TestFaultConfig(unittest.TestCase):
    def test_create_config(self) -> None:
        cfg = FaultConfig(fault_type=FaultType.TIMEOUT, target="api-service")
        self.assertEqual(cfg.fault_type, FaultType.TIMEOUT)
        self.assertEqual(cfg.target, "api-service")
        self.assertEqual(cfg.duration_seconds, 10.0)
        self.assertEqual(cfg.probability, 1.0)

    def test_invalid_duration(self) -> None:
        with self.assertRaises(ValueError):
            FaultConfig(fault_type=FaultType.TIMEOUT, target="x", duration_seconds=0)

    def test_invalid_probability_high(self) -> None:
        with self.assertRaises(ValueError):
            FaultConfig(fault_type=FaultType.TIMEOUT, target="x", probability=1.5)

    def test_invalid_probability_negative(self) -> None:
        with self.assertRaises(ValueError):
            FaultConfig(fault_type=FaultType.TIMEOUT, target="x", probability=-0.1)

    def test_empty_target(self) -> None:
        with self.assertRaises(ValueError):
            FaultConfig(fault_type=FaultType.TIMEOUT, target="")

    def test_config_is_frozen(self) -> None:
        cfg = FaultConfig(fault_type=FaultType.TIMEOUT, target="x")
        with self.assertRaises(AttributeError):
            cfg.target = "y"  # type: ignore[misc]


class TestFaultTypes(unittest.TestCase):
    def test_all_types(self) -> None:
        types = list(FaultType)
        self.assertEqual(len(types), 6)
        self.assertIn(FaultType.TIMEOUT, types)
        self.assertIn(FaultType.ERROR_RESPONSE, types)
        self.assertIn(FaultType.SLOW_RESPONSE, types)
        self.assertIn(FaultType.CONNECTION_DROP, types)

    def test_all_statuses(self) -> None:
        statuses = list(FaultStatus)
        self.assertEqual(len(statuses), 3)


class TestInjectedFault(unittest.TestCase):
    def test_is_expired_not_active(self) -> None:
        fault = InjectedFault(
            id="abc",
            config=FaultConfig(fault_type=FaultType.TIMEOUT, target="x"),
            status=FaultStatus.ROLLED_BACK,
            injected_at=0.0,
        )
        self.assertFalse(fault.is_expired)

    def test_is_expired_within_duration(self) -> None:
        fault = InjectedFault(
            id="abc",
            config=FaultConfig(
                fault_type=FaultType.TIMEOUT, target="x", duration_seconds=9999
            ),
            status=FaultStatus.ACTIVE,
            injected_at=time.time(),
        )
        self.assertFalse(fault.is_expired)

    def test_is_expired_past_duration(self) -> None:
        fault = InjectedFault(
            id="abc",
            config=FaultConfig(
                fault_type=FaultType.TIMEOUT, target="x", duration_seconds=1
            ),
            status=FaultStatus.ACTIVE,
            injected_at=time.time() - 100,
        )
        self.assertTrue(fault.is_expired)


class TestFaultInjector(unittest.TestCase):
    def setUp(self) -> None:
        self.injector = FaultInjector()
        self.cfg = FaultConfig(
            fault_type=FaultType.TIMEOUT,
            target="api-service",
            duration_seconds=60.0,
        )

    def test_inject(self) -> None:
        fault = self.injector.inject(self.cfg)
        self.assertIsInstance(fault, InjectedFault)
        self.assertEqual(fault.status, FaultStatus.ACTIVE)
        self.assertGreater(fault.injected_at, 0)

    def test_rollback(self) -> None:
        fault = self.injector.inject(self.cfg)
        rolled = self.injector.rollback(fault.id)
        self.assertEqual(rolled.status, FaultStatus.ROLLED_BACK)
        self.assertGreater(rolled.rolled_back_at, 0)

    def test_rollback_nonexistent_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.injector.rollback("nope")

    def test_rollback_already_rolled_back_raises(self) -> None:
        fault = self.injector.inject(self.cfg)
        self.injector.rollback(fault.id)
        with self.assertRaises(RuntimeError):
            self.injector.rollback(fault.id)

    def test_rollback_all(self) -> None:
        self.injector.inject(self.cfg)
        self.injector.inject(
            FaultConfig(fault_type=FaultType.SLOW_RESPONSE, target="db")
        )
        rolled = self.injector.rollback_all()
        self.assertEqual(len(rolled), 2)
        for r in rolled:
            self.assertEqual(r.status, FaultStatus.ROLLED_BACK)

    def test_rollback_all_empty(self) -> None:
        rolled = self.injector.rollback_all()
        self.assertEqual(rolled, [])

    def test_get_fault(self) -> None:
        fault = self.injector.inject(self.cfg)
        fetched = self.injector.get_fault(fault.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, fault.id)

    def test_get_nonexistent(self) -> None:
        self.assertIsNone(self.injector.get_fault("nope"))

    def test_list_active(self) -> None:
        self.injector.inject(self.cfg)
        f2 = self.injector.inject(
            FaultConfig(fault_type=FaultType.SLOW_RESPONSE, target="db")
        )
        self.injector.rollback(f2.id)
        active = self.injector.list_active()
        self.assertEqual(len(active), 1)

    def test_list_all(self) -> None:
        self.injector.inject(self.cfg)
        self.injector.inject(
            FaultConfig(fault_type=FaultType.SLOW_RESPONSE, target="db")
        )
        self.assertEqual(len(self.injector.list_all()), 2)

    def test_check_fault_found(self) -> None:
        self.injector.inject(self.cfg)
        result = self.injector.check_fault("api-service")
        self.assertEqual(result, FaultType.TIMEOUT)

    def test_check_fault_not_found(self) -> None:
        self.assertIsNone(self.injector.check_fault("nonexistent"))

    def test_check_fault_increments_invocation(self) -> None:
        fault = self.injector.inject(self.cfg)
        self.injector.check_fault("api-service")
        self.injector.check_fault("api-service")
        updated = self.injector.get_fault(fault.id)
        self.assertEqual(updated.invocation_count, 2)

    def test_expire_stale(self) -> None:
        cfg_short = FaultConfig(
            fault_type=FaultType.TIMEOUT,
            target="api",
            duration_seconds=0.001,
        )
        self.injector.inject(cfg_short)
        # Let it expire
        import time as _t
        _t.sleep(0.01)
        expired = self.injector.expire_stale()
        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].status, FaultStatus.EXPIRED)

    def test_rollback_log(self) -> None:
        fault = self.injector.inject(self.cfg)
        self.injector.rollback(fault.id)
        log = self.injector.rollback_log
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["fault_id"], fault.id)
        self.assertEqual(log[0]["fault_type"], "timeout")

    def test_rollback_log_is_copy(self) -> None:
        log = self.injector.rollback_log
        log.append({"fake": True})
        self.assertEqual(len(self.injector.rollback_log), 0)


if __name__ == "__main__":
    unittest.main()
