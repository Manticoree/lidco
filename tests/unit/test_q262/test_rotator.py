"""Tests for SecretRotator (Q262)."""
from __future__ import annotations

import unittest

from lidco.secrets.rotator import RotationResult, RotationHandler, SecretRotator


class _MockHandler:
    """Simple handler that appends '_rotated' to generate a new value."""

    def rotate(self, secret_name: str, current_value: str) -> tuple[str, str | None]:
        return (current_value + "_rotated", None)


class _FailingHandler:
    def rotate(self, secret_name: str, current_value: str) -> tuple[str, str | None]:
        return ("", "provider error")


class _ExplodingHandler:
    def rotate(self, secret_name: str, current_value: str) -> tuple[str, str | None]:
        raise RuntimeError("boom")


class TestRotationResult(unittest.TestCase):
    def test_frozen(self):
        r = RotationResult("s", "p", "old", "new", 0.0, True)
        with self.assertRaises(AttributeError):
            r.success = False  # type: ignore[misc]


class TestRegisterHandler(unittest.TestCase):
    def test_register_and_providers(self):
        rotator = SecretRotator()
        rotator.register_handler("aws", _MockHandler())
        rotator.register_handler("github", _MockHandler())
        self.assertEqual(rotator.providers(), ["aws", "github"])


class TestRotateSuccess(unittest.TestCase):
    def test_successful_rotation(self):
        rotator = SecretRotator()
        rotator.register_handler("aws", _MockHandler())
        result = rotator.rotate("db-password", "aws", "oldvalue12345678")
        self.assertTrue(result.success)
        self.assertEqual(result.old_prefix, "oldvalue")
        # new value is "oldvalue12345678_rotated", prefix is first 8 chars
        self.assertEqual(result.new_prefix, "oldvalue")
        self.assertIsNone(result.error)


class TestRotateNoHandler(unittest.TestCase):
    def test_missing_handler(self):
        rotator = SecretRotator()
        result = rotator.rotate("key", "unknown", "val")
        self.assertFalse(result.success)
        self.assertIn("No handler", result.error)


class TestRotateHandlerError(unittest.TestCase):
    def test_handler_returns_error(self):
        rotator = SecretRotator()
        rotator.register_handler("bad", _FailingHandler())
        result = rotator.rotate("key", "bad", "val12345678")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "provider error")

    def test_handler_exception(self):
        rotator = SecretRotator()
        rotator.register_handler("explode", _ExplodingHandler())
        result = rotator.rotate("key", "explode", "val12345678")
        self.assertFalse(result.success)
        self.assertIn("boom", result.error)


class TestHistory(unittest.TestCase):
    def test_history_all(self):
        rotator = SecretRotator()
        rotator.register_handler("p", _MockHandler())
        rotator.rotate("a", "p", "val12345678")
        rotator.rotate("b", "p", "val12345678")
        self.assertEqual(len(rotator.history()), 2)

    def test_history_filtered(self):
        rotator = SecretRotator()
        rotator.register_handler("p", _MockHandler())
        rotator.rotate("a", "p", "val12345678")
        rotator.rotate("b", "p", "val12345678")
        self.assertEqual(len(rotator.history("a")), 1)


class TestScheduleRotation(unittest.TestCase):
    def test_schedule(self):
        rotator = SecretRotator()
        sched = rotator.schedule_rotation("db-pass", "aws", 30)
        self.assertEqual(sched["secret_name"], "db-pass")
        self.assertEqual(sched["interval_days"], 30)
        self.assertIn("id", sched)

    def test_pending_rotations(self):
        rotator = SecretRotator()
        sched = rotator.schedule_rotation("db-pass", "aws", 0)
        # interval_days=0 means next_rotation = now, so it should be pending
        pending = rotator.pending_rotations()
        self.assertTrue(len(pending) >= 1)


class TestSummary(unittest.TestCase):
    def test_summary(self):
        rotator = SecretRotator()
        rotator.register_handler("p", _MockHandler())
        rotator.rotate("x", "p", "val12345678")
        s = rotator.summary()
        self.assertEqual(s["providers"], 1)
        self.assertEqual(s["total_rotations"], 1)
        self.assertEqual(s["successful"], 1)
        self.assertEqual(s["failed"], 0)


if __name__ == "__main__":
    unittest.main()
