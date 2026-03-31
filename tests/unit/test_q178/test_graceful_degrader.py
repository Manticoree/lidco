"""Tests for GracefulDegrader."""
import unittest

from lidco.resilience.graceful_degrader import GracefulDegrader


class TestGracefulDegrader(unittest.TestCase):
    def setUp(self):
        self.degrader = GracefulDegrader()

    def test_register_subsystem(self):
        self.degrader.register_subsystem("db", lambda: True)
        self.assertIn("db", self.degrader.list_subsystems())

    def test_is_healthy_true(self):
        self.degrader.register_subsystem("cache", lambda: True)
        self.assertTrue(self.degrader.is_healthy("cache"))

    def test_is_healthy_false_auto_disables(self):
        self.degrader.register_subsystem("cache", lambda: False)
        self.assertFalse(self.degrader.is_healthy("cache"))
        # Should stay disabled now
        self.assertIn("cache", self.degrader.disabled_subsystems())

    def test_is_healthy_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.degrader.is_healthy("nonexistent")

    def test_disable(self):
        self.degrader.register_subsystem("db", lambda: True)
        self.degrader.disable("db")
        self.assertFalse(self.degrader.is_healthy("db"))

    def test_disable_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.degrader.disable("nonexistent")

    def test_enable(self):
        self.degrader.register_subsystem("db", lambda: True)
        self.degrader.disable("db")
        self.degrader.enable("db")
        self.assertTrue(self.degrader.is_healthy("db"))

    def test_enable_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.degrader.enable("nonexistent")

    def test_check_all(self):
        self.degrader.register_subsystem("a", lambda: True)
        self.degrader.register_subsystem("b", lambda: False)
        result = self.degrader.check_all()
        self.assertTrue(result["a"])
        self.assertFalse(result["b"])

    def test_check_all_empty(self):
        self.assertEqual(self.degrader.check_all(), {})

    def test_auto_disable_on_exception(self):
        self.degrader.register_subsystem("bad", lambda: (_ for _ in ()).throw(RuntimeError("oops")))
        # The lambda raises — health check should catch and auto-disable
        def raising_check():
            raise RuntimeError("oops")
        self.degrader.register_subsystem("bad2", raising_check)
        self.assertFalse(self.degrader.is_healthy("bad2"))
        self.assertIn("bad2", self.degrader.disabled_subsystems())

    def test_list_subsystems(self):
        self.degrader.register_subsystem("x", lambda: True)
        self.degrader.register_subsystem("y", lambda: True)
        self.assertEqual(sorted(self.degrader.list_subsystems()), ["x", "y"])

    def test_enabled_subsystems(self):
        self.degrader.register_subsystem("a", lambda: True)
        self.degrader.register_subsystem("b", lambda: True)
        self.degrader.disable("b")
        self.assertEqual(self.degrader.enabled_subsystems(), ["a"])

    def test_disabled_subsystems(self):
        self.degrader.register_subsystem("a", lambda: True)
        self.degrader.register_subsystem("b", lambda: True)
        self.degrader.disable("a")
        self.assertEqual(self.degrader.disabled_subsystems(), ["a"])

    def test_disabled_stays_disabled_on_check(self):
        self.degrader.register_subsystem("db", lambda: True)
        self.degrader.disable("db")
        # Even though health check would return True, disabled overrides
        self.assertFalse(self.degrader.is_healthy("db"))

    def test_re_enable_after_auto_disable(self):
        calls = [0]
        def flaky():
            calls[0] += 1
            return calls[0] > 1
        self.degrader.register_subsystem("flaky", flaky)
        # First call fails, auto-disables
        self.assertFalse(self.degrader.is_healthy("flaky"))
        # Re-enable
        self.degrader.enable("flaky")
        # Now the second call succeeds
        self.assertTrue(self.degrader.is_healthy("flaky"))

    def test_check_all_auto_disables_failing(self):
        self.degrader.register_subsystem("ok", lambda: True)
        self.degrader.register_subsystem("fail", lambda: False)
        self.degrader.check_all()
        self.assertIn("fail", self.degrader.disabled_subsystems())
        self.assertIn("ok", self.degrader.enabled_subsystems())

    def test_multiple_registers_overwrites(self):
        self.degrader.register_subsystem("x", lambda: False)
        self.degrader.register_subsystem("x", lambda: True)
        self.assertTrue(self.degrader.is_healthy("x"))

    def test_disable_then_check_all(self):
        self.degrader.register_subsystem("a", lambda: True)
        self.degrader.disable("a")
        result = self.degrader.check_all()
        self.assertFalse(result["a"])

    def test_health_check_exception_returns_false(self):
        def boom():
            raise ValueError("broken")
        self.degrader.register_subsystem("boom", boom)
        self.assertFalse(self.degrader.is_healthy("boom"))


if __name__ == "__main__":
    unittest.main()
