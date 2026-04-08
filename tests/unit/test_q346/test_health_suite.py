"""Tests for lidco.stability.health_suite."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from lidco.stability.health_suite import HealthCheckSuite


_FAKE_DISK = type("FakeDisk", (), {"free": 200 * 1024 * 1024, "total": 1024 ** 3, "used": 0})()
_FAKE_DISK_LOW = type("FakeDisk", (), {"free": 50 * 1024 * 1024, "total": 1024 ** 3, "used": 0})()


class TestCheckDiskSpace(unittest.TestCase):
    def setUp(self):
        self.suite = HealthCheckSuite()

    @patch("shutil.disk_usage", return_value=_FAKE_DISK)
    def test_healthy_when_enough_space(self, _mock):
        result = self.suite.check_disk_space(".", min_mb=100.0)
        self.assertTrue(result["healthy"])

    @patch("shutil.disk_usage", return_value=_FAKE_DISK_LOW)
    def test_unhealthy_when_not_enough_space(self, _mock):
        result = self.suite.check_disk_space(".", min_mb=100.0)
        self.assertFalse(result["healthy"])

    @patch("shutil.disk_usage", return_value=_FAKE_DISK)
    def test_result_keys_present(self, _mock):
        result = self.suite.check_disk_space()
        for key in ("healthy", "available_mb", "min_mb", "path"):
            self.assertIn(key, result)

    @patch("shutil.disk_usage", return_value=_FAKE_DISK)
    def test_available_mb_is_float(self, _mock):
        result = self.suite.check_disk_space()
        self.assertIsInstance(result["available_mb"], float)

    @patch("shutil.disk_usage", side_effect=OSError("no disk"))
    def test_handles_disk_error_gracefully(self, _mock):
        result = self.suite.check_disk_space(".")
        self.assertFalse(result["healthy"])
        self.assertEqual(result["available_mb"], 0.0)


class TestCheckMemory(unittest.TestCase):
    def setUp(self):
        self.suite = HealthCheckSuite()

    @patch.object(HealthCheckSuite, "_get_memory_percent", return_value=50.0)
    def test_healthy_below_threshold(self, _mock):
        result = self.suite.check_memory(max_percent=90.0)
        self.assertTrue(result["healthy"])

    @patch.object(HealthCheckSuite, "_get_memory_percent", return_value=95.0)
    def test_unhealthy_above_threshold(self, _mock):
        result = self.suite.check_memory(max_percent=90.0)
        self.assertFalse(result["healthy"])

    @patch.object(HealthCheckSuite, "_get_memory_percent", return_value=75.0)
    def test_result_keys_present(self, _mock):
        result = self.suite.check_memory()
        for key in ("healthy", "used_percent", "max_percent"):
            self.assertIn(key, result)

    @patch.object(HealthCheckSuite, "_get_memory_percent", return_value=80.0)
    def test_used_percent_stored(self, _mock):
        result = self.suite.check_memory(max_percent=90.0)
        self.assertAlmostEqual(result["used_percent"], 80.0)


class TestCheckConfigValidity(unittest.TestCase):
    def setUp(self):
        self.suite = HealthCheckSuite()

    def test_valid_config(self):
        result = self.suite.check_config_validity(
            {"host": "localhost", "port": 8080}, ["host", "port"]
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["missing_keys"], [])

    def test_missing_key_detected(self):
        result = self.suite.check_config_validity(
            {"host": "localhost"}, ["host", "port"]
        )
        self.assertFalse(result["valid"])
        self.assertIn("port", result["missing_keys"])

    def test_extra_keys_reported(self):
        result = self.suite.check_config_validity(
            {"host": "x", "port": 1, "debug": True}, ["host", "port"]
        )
        self.assertIn("debug", result["extra_keys"])

    def test_empty_config_all_missing(self):
        result = self.suite.check_config_validity({}, ["a", "b"])
        self.assertFalse(result["valid"])
        self.assertEqual(sorted(result["missing_keys"]), ["a", "b"])

    def test_empty_required_keys(self):
        result = self.suite.check_config_validity({"x": 1}, [])
        self.assertTrue(result["valid"])
        self.assertIn("x", result["extra_keys"])


class TestRunAll(unittest.TestCase):
    def setUp(self):
        self.suite = HealthCheckSuite()

    @patch("shutil.disk_usage", return_value=_FAKE_DISK)
    @patch.object(HealthCheckSuite, "_get_memory_percent", return_value=50.0)
    def test_overall_healthy(self, _m1, _m2):
        result = self.suite.run_all(path=".", config={})
        self.assertTrue(result["overall_healthy"])

    @patch("shutil.disk_usage", return_value=_FAKE_DISK_LOW)
    @patch.object(HealthCheckSuite, "_get_memory_percent", return_value=50.0)
    def test_overall_unhealthy_on_disk_fail(self, _m1, _m2):
        result = self.suite.run_all(path=".")
        self.assertFalse(result["overall_healthy"])

    @patch("shutil.disk_usage", return_value=_FAKE_DISK)
    @patch.object(HealthCheckSuite, "_get_memory_percent", return_value=50.0)
    def test_result_keys_present(self, _m1, _m2):
        result = self.suite.run_all()
        for key in ("overall_healthy", "checks", "timestamp"):
            self.assertIn(key, result)

    @patch("shutil.disk_usage", return_value=_FAKE_DISK)
    @patch.object(HealthCheckSuite, "_get_memory_percent", return_value=50.0)
    def test_checks_contains_all_suites(self, _m1, _m2):
        result = self.suite.run_all()
        self.assertIn("disk_space", result["checks"])
        self.assertIn("memory", result["checks"])
        self.assertIn("config_validity", result["checks"])

    @patch("shutil.disk_usage", return_value=_FAKE_DISK)
    @patch.object(HealthCheckSuite, "_get_memory_percent", return_value=50.0)
    def test_timestamp_is_string(self, _m1, _m2):
        result = self.suite.run_all()
        self.assertIsInstance(result["timestamp"], str)
        self.assertTrue(result["timestamp"].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
