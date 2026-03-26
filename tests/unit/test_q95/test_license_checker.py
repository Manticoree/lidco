"""Tests for T609 LicenseChecker."""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lidco.compliance.license_checker import (
    LicenseChecker,
    LicenseReport,
    PackageLicense,
    LicenseIssue,
    _classify,
    _parse_metadata,
    _read_package_json,
)


# ---------------------------------------------------------------------------
# _classify
# ---------------------------------------------------------------------------

class TestClassify:
    def test_mit_is_permissive(self):
        assert _classify("MIT") == "permissive"

    def test_apache_is_permissive(self):
        assert _classify("Apache-2.0") == "permissive"

    def test_bsd_is_permissive(self):
        assert _classify("BSD-3-Clause") == "permissive"

    def test_gpl_is_copyleft(self):
        assert _classify("GPL-3.0") == "copyleft"

    def test_agpl_is_copyleft(self):
        assert _classify("AGPL-3.0") == "copyleft"

    def test_lgpl_is_weak_copyleft(self):
        assert _classify("LGPL-2.1") == "weak_copyleft"

    def test_mpl_is_weak_copyleft(self):
        assert _classify("MPL-2.0") == "weak_copyleft"

    def test_empty_is_unknown(self):
        assert _classify("") == "unknown"

    def test_none_string_is_unknown(self):
        assert _classify("unknown") == "unknown"

    def test_case_insensitive(self):
        assert _classify("mit") == "permissive"
        assert _classify("GPL-2.0") == "copyleft"


# ---------------------------------------------------------------------------
# _parse_metadata
# ---------------------------------------------------------------------------

class TestParseMetadata:
    def test_basic_fields(self, tmp_path):
        f = tmp_path / "METADATA"
        f.write_text("Name: requests\nVersion: 2.28.0\nLicense: Apache-2.0\n")
        meta = _parse_metadata(f)
        assert meta["Name"] == "requests"
        assert meta["Version"] == "2.28.0"
        assert meta["License"] == "Apache-2.0"

    def test_classifier_extracted(self, tmp_path):
        f = tmp_path / "METADATA"
        f.write_text("Name: foo\nClassifier: License :: OSI Approved :: MIT License\n")
        meta = _parse_metadata(f)
        assert any("MIT License" in clf for clf in meta["_classifiers"])

    def test_empty_file(self, tmp_path):
        f = tmp_path / "METADATA"
        f.write_text("")
        meta = _parse_metadata(f)
        assert meta == {"_classifiers": []}


# ---------------------------------------------------------------------------
# _read_package_json
# ---------------------------------------------------------------------------

class TestReadPackageJson:
    def test_reads_license(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text('{"name": "myapp", "version": "1.0.0", "license": "MIT"}')
        pkgs = _read_package_json(f)
        assert len(pkgs) == 1
        assert pkgs[0].license == "MIT"
        assert pkgs[0].classification == "permissive"

    def test_license_object_format(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text('{"name": "myapp", "license": {"type": "MIT"}}')
        pkgs = _read_package_json(f)
        assert pkgs[0].license == "MIT"

    def test_missing_license_defaults_unknown(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text('{"name": "myapp"}')
        pkgs = _read_package_json(f)
        assert pkgs[0].license == "unknown"

    def test_invalid_json_returns_empty(self, tmp_path):
        f = tmp_path / "package.json"
        f.write_text("{invalid}")
        assert _read_package_json(f) == []


# ---------------------------------------------------------------------------
# LicenseChecker
# ---------------------------------------------------------------------------

class TestLicenseChecker:
    def _make_pkg(self, name, license_, classification=None):
        return PackageLicense(
            name=name,
            version="1.0.0",
            license=license_,
            classification=classification or _classify(license_),
        )

    def test_check_no_packages(self, tmp_path):
        checker = LicenseChecker(
            project_root=str(tmp_path),
            site_packages_path=str(tmp_path / "nonexistent"),
        )
        report = checker.check()
        assert report.packages == []

    def test_copyleft_flagged_for_mit_project(self, tmp_path):
        checker = LicenseChecker(
            project_root=str(tmp_path),
            project_license="MIT",
            site_packages_path=str(tmp_path / "sp"),
        )
        packages = [self._make_pkg("badlib", "GPL-3.0")]
        issues = checker._detect_issues(packages)
        errors = [i for i in issues if i.severity == "error"]
        assert len(errors) >= 1
        assert errors[0].package == "badlib"

    def test_copyleft_not_flagged_when_disabled(self, tmp_path):
        checker = LicenseChecker(
            project_root=str(tmp_path),
            project_license="MIT",
            flag_copyleft=False,
            site_packages_path=str(tmp_path / "sp"),
        )
        packages = [self._make_pkg("badlib", "GPL-3.0")]
        issues = checker._detect_issues(packages)
        assert not any(i.issue_type if hasattr(i, 'issue_type') else True for i in issues
                       if i.package == "badlib" and i.severity == "error")

    def test_weak_copyleft_is_warning(self, tmp_path):
        checker = LicenseChecker(
            project_root=str(tmp_path),
            project_license="MIT",
            site_packages_path=str(tmp_path / "sp"),
        )
        packages = [self._make_pkg("lgplpkg", "LGPL-2.1")]
        issues = checker._detect_issues(packages)
        warnings = [i for i in issues if i.severity == "warning" and i.package == "lgplpkg"]
        assert len(warnings) >= 1

    def test_unknown_license_warning(self, tmp_path):
        checker = LicenseChecker(
            project_root=str(tmp_path),
            flag_unknown=True,
            site_packages_path=str(tmp_path / "sp"),
        )
        packages = [self._make_pkg("mysterylib", "Custom-1.0", classification="unknown")]
        issues = checker._detect_issues(packages)
        unknowns = [i for i in issues if i.classification == "unknown"]
        assert len(unknowns) >= 1

    def test_unknown_flag_disabled(self, tmp_path):
        checker = LicenseChecker(
            project_root=str(tmp_path),
            flag_unknown=False,
            site_packages_path=str(tmp_path / "sp"),
        )
        packages = [self._make_pkg("mysterylib", "Custom-1.0", classification="unknown")]
        issues = checker._detect_issues(packages)
        unknowns = [i for i in issues if i.classification == "unknown"]
        assert len(unknowns) == 0

    def test_permissive_no_issues(self, tmp_path):
        checker = LicenseChecker(
            project_root=str(tmp_path),
            project_license="MIT",
            flag_unknown=False,
            site_packages_path=str(tmp_path / "sp"),
        )
        packages = [self._make_pkg("goodlib", "MIT")]
        issues = checker._detect_issues(packages)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# LicenseReport
# ---------------------------------------------------------------------------

class TestLicenseReport:
    def _make_report(self):
        return LicenseReport(
            packages=[
                PackageLicense("mit-pkg", "1.0", "MIT", "permissive"),
                PackageLicense("gpl-pkg", "1.0", "GPL-3.0", "copyleft"),
                PackageLicense("lgpl-pkg", "1.0", "LGPL-2.1", "weak_copyleft"),
                PackageLicense("unknown-pkg", "1.0", "Custom", "unknown"),
            ],
            issues=[
                LicenseIssue("error", "gpl-pkg", "GPL-3.0", "copyleft", "incompatible"),
            ],
            project_license="MIT",
        )

    def test_by_classification(self):
        report = self._make_report()
        bc = report.by_classification
        assert len(bc["permissive"]) == 1
        assert len(bc["copyleft"]) == 1
        assert len(bc["weak_copyleft"]) == 1
        assert len(bc["unknown"]) == 1

    def test_summary(self):
        report = self._make_report()
        s = report.summary()
        assert "4" in s  # 4 packages
        assert "copyleft" in s.lower()

    def test_summary_includes_issue_count(self):
        report = self._make_report()
        s = report.summary()
        assert "issue" in s.lower()
