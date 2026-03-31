"""Tests for DependencyChecker — Task 848."""

from __future__ import annotations

import unittest

from lidco.diagnostics.dep_checker import DependencyChecker, DepStatus, _compare_versions


class TestDepStatus(unittest.TestCase):
    def test_dataclass_fields(self):
        ds = DepStatus("pkg", True, "1.0", "1.0", True)
        self.assertEqual(ds.name, "pkg")
        self.assertTrue(ds.installed)
        self.assertEqual(ds.version, "1.0")
        self.assertTrue(ds.compatible)

    def test_missing_package(self):
        ds = DepStatus("missing", False, None, None, False)
        self.assertFalse(ds.installed)
        self.assertFalse(ds.compatible)


class TestCompareVersions(unittest.TestCase):
    def test_equal(self):
        self.assertTrue(_compare_versions("1.2.3", "1.2.3"))

    def test_greater(self):
        self.assertTrue(_compare_versions("2.0.0", "1.9.9"))

    def test_less(self):
        self.assertFalse(_compare_versions("1.0.0", "1.0.1"))

    def test_prefix_strip(self):
        self.assertTrue(_compare_versions("1.2.0", ">=1.0.0"))

    def test_major_only(self):
        self.assertTrue(_compare_versions("3", "2"))


class TestDependencyCheckerCheck(unittest.TestCase):
    def test_installed_no_version_req(self):
        dc = DependencyChecker(
            _import_check=lambda n: True,
            _version_getter=lambda n: "1.5.0",
        )
        result = dc.check("mypkg")
        self.assertTrue(result.installed)
        self.assertTrue(result.compatible)
        self.assertEqual(result.version, "1.5.0")

    def test_not_installed(self):
        dc = DependencyChecker(
            _import_check=lambda n: False,
            _version_getter=lambda n: None,
        )
        result = dc.check("missing")
        self.assertFalse(result.installed)
        self.assertFalse(result.compatible)

    def test_installed_compatible_version(self):
        dc = DependencyChecker(
            _import_check=lambda n: True,
            _version_getter=lambda n: "2.0.0",
        )
        result = dc.check("pkg", "1.0.0")
        self.assertTrue(result.compatible)

    def test_installed_incompatible_version(self):
        dc = DependencyChecker(
            _import_check=lambda n: True,
            _version_getter=lambda n: "0.9.0",
        )
        result = dc.check("pkg", "1.0.0")
        self.assertFalse(result.compatible)

    def test_installed_no_version_available(self):
        dc = DependencyChecker(
            _import_check=lambda n: True,
            _version_getter=lambda n: None,
        )
        result = dc.check("pkg", "1.0.0")
        self.assertTrue(result.compatible)  # assume ok when can't verify


class TestCheckAll(unittest.TestCase):
    def test_string_list(self):
        dc = DependencyChecker(
            _import_check=lambda n: True,
            _version_getter=lambda n: "1.0",
        )
        results = dc.check_all(["a", "b", "c"])
        self.assertEqual(len(results), 3)

    def test_tuple_list(self):
        dc = DependencyChecker(
            _import_check=lambda n: True,
            _version_getter=lambda n: "2.0",
        )
        results = dc.check_all([("a", "1.0"), ("b", "2.0")])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.compatible for r in results))

    def test_mixed_list(self):
        dc = DependencyChecker(
            _import_check=lambda n: n != "missing",
            _version_getter=lambda n: "1.0",
        )
        results = dc.check_all(["ok", ("missing", "1.0")])
        self.assertEqual(len(results), 2)


class TestMissing(unittest.TestCase):
    def test_missing_after_check_all(self):
        dc = DependencyChecker(
            _import_check=lambda n: n != "gone",
            _version_getter=lambda n: "1.0",
        )
        dc.check_all(["ok", "gone"])
        self.assertEqual(dc.missing(), ["gone"])

    def test_no_missing(self):
        dc = DependencyChecker(
            _import_check=lambda n: True,
            _version_getter=lambda n: "1.0",
        )
        dc.check_all(["a", "b"])
        self.assertEqual(dc.missing(), [])


class TestSummary(unittest.TestCase):
    def test_empty_summary(self):
        dc = DependencyChecker()
        self.assertIn("No dependencies checked", dc.summary())

    def test_summary_with_results(self):
        dc = DependencyChecker(
            _import_check=lambda n: True,
            _version_getter=lambda n: "1.0",
        )
        dc.check_all(["pkg"])
        text = dc.summary()
        self.assertIn("1/1 installed", text)
        self.assertIn("[ok]", text)

    def test_summary_missing(self):
        dc = DependencyChecker(
            _import_check=lambda n: False,
            _version_getter=lambda n: None,
        )
        dc.check_all(["gone"])
        text = dc.summary()
        self.assertIn("[MISSING]", text)


if __name__ == "__main__":
    unittest.main()
