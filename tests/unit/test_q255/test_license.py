"""Tests for LicenseAnalyzer (Q255)."""
from __future__ import annotations

import unittest

from lidco.depgraph.license import LicenseAnalyzer, LicenseInfo


class TestLicenseInfo(unittest.TestCase):
    def test_frozen(self):
        info = LicenseInfo(package="pkg", license="MIT")
        with self.assertRaises(AttributeError):
            info.package = "x"  # type: ignore[misc]

    def test_defaults(self):
        info = LicenseInfo(package="pkg", license="MIT")
        self.assertEqual(info.category, "unknown")

    def test_fields(self):
        info = LicenseInfo(package="foo", license="GPL-3.0", category="copyleft")
        self.assertEqual(info.package, "foo")
        self.assertEqual(info.license, "GPL-3.0")
        self.assertEqual(info.category, "copyleft")


class TestLicenseAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = LicenseAnalyzer()

    def test_add_and_list_all(self):
        self.analyzer.add(LicenseInfo(package="a", license="MIT", category="permissive"))
        self.analyzer.add(LicenseInfo(package="b", license="GPL-3.0", category="copyleft"))
        entries = self.analyzer.list_all()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].package, "a")

    def test_check_compatibility_mit_project(self):
        self.analyzer.add(LicenseInfo(package="ok", license="MIT", category="permissive"))
        self.analyzer.add(LicenseInfo(package="bad", license="GPL-3.0", category="copyleft"))
        self.analyzer.add(LicenseInfo(package="bad2", license="Proprietary", category="proprietary"))
        incompatible = self.analyzer.check_compatibility("MIT")
        self.assertIn("bad", incompatible)
        self.assertIn("bad2", incompatible)
        self.assertNotIn("ok", incompatible)

    def test_check_compatibility_gpl_project(self):
        self.analyzer.add(LicenseInfo(package="prop", license="Proprietary", category="proprietary"))
        self.analyzer.add(LicenseInfo(package="perm", license="MIT", category="permissive"))
        incompatible = self.analyzer.check_compatibility("GPL-3.0")
        self.assertIn("prop", incompatible)
        self.assertNotIn("perm", incompatible)

    def test_check_compatibility_unknown_license(self):
        self.analyzer.add(LicenseInfo(package="any", license="X", category="copyleft"))
        incompatible = self.analyzer.check_compatibility("UnknownLicense")
        self.assertEqual(incompatible, [])

    def test_generate_sbom(self):
        self.analyzer.add(LicenseInfo(package="p1", license="MIT", category="permissive"))
        sbom = self.analyzer.generate_sbom()
        self.assertEqual(sbom["format"], "lidco-sbom-1.0")
        self.assertEqual(sbom["total"], 1)
        self.assertEqual(len(sbom["packages"]), 1)
        self.assertEqual(sbom["packages"][0]["name"], "p1")

    def test_generate_sbom_empty(self):
        sbom = self.analyzer.generate_sbom()
        self.assertEqual(sbom["total"], 0)
        self.assertEqual(sbom["packages"], [])

    def test_summary_empty(self):
        self.assertEqual(self.analyzer.summary(), "No license data.")

    def test_summary_with_entries(self):
        self.analyzer.add(LicenseInfo(package="x", license="MIT", category="permissive"))
        self.analyzer.add(LicenseInfo(package="y", license="GPL-3.0", category="copyleft"))
        s = self.analyzer.summary()
        self.assertIn("2 package(s)", s)
        self.assertIn("x: MIT", s)
        self.assertIn("y: GPL-3.0", s)

    def test_apache_compatibility(self):
        self.analyzer.add(LicenseInfo(package="gpl_pkg", license="GPL", category="copyleft"))
        self.analyzer.add(LicenseInfo(package="prop_pkg", license="P", category="proprietary"))
        incompatible = self.analyzer.check_compatibility("Apache-2.0")
        self.assertIn("gpl_pkg", incompatible)
        self.assertNotIn("prop_pkg", incompatible)


if __name__ == "__main__":
    unittest.main()
