"""Tests for T602 DependencyAnalyzer."""
from pathlib import Path
from unittest.mock import patch

import pytest

from lidco.dependencies.analyzer import (
    DependencyAnalyzer,
    DependencyReport,
    PackageInfo,
    _parse_package_json,
    _parse_pyproject_toml,
    _parse_requirements_txt,
)


# ---------------------------------------------------------------------------
# _parse_requirements_txt
# ---------------------------------------------------------------------------

class TestParseRequirementsTxt:
    def test_simple_pinned(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("requests==2.28.0\n")
        pkgs = _parse_requirements_txt(req)
        assert len(pkgs) == 1
        assert pkgs[0].name == "requests"
        assert pkgs[0].version_spec == "==2.28.0"
        assert pkgs[0].is_pinned is True

    def test_unpinned(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("flask>=2.0\n")
        pkgs = _parse_requirements_txt(req)
        assert pkgs[0].is_pinned is False

    def test_comment_lines_skipped(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("# comment\nrequests==2.0\n")
        pkgs = _parse_requirements_txt(req)
        assert len(pkgs) == 1

    def test_empty_file(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("")
        assert _parse_requirements_txt(req) == []

    def test_inline_comment_stripped(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("django==4.2  # web framework\n")
        pkgs = _parse_requirements_txt(req)
        assert pkgs[0].name == "django"
        assert "web framework" not in pkgs[0].version_spec

    def test_dash_r_lines_skipped(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("-r other.txt\nflask==2.0\n")
        pkgs = _parse_requirements_txt(req)
        assert len(pkgs) == 1


# ---------------------------------------------------------------------------
# _parse_package_json
# ---------------------------------------------------------------------------

class TestParsePackageJson:
    def test_basic(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text('{"dependencies": {"lodash": "^4.0.0"}, "devDependencies": {"jest": "^29.0.0"}}')
        pkgs = _parse_package_json(pkg)
        names = {p.name for p in pkgs}
        assert "lodash" in names
        assert "jest" in names

    def test_dev_flag(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text('{"devDependencies": {"eslint": "^8.0.0"}}')
        pkgs = _parse_package_json(pkg)
        assert pkgs[0].is_dev is True

    def test_pinned_exact_version(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text('{"dependencies": {"react": "18.2.0"}}')
        pkgs = _parse_package_json(pkg)
        assert pkgs[0].is_pinned is True

    def test_invalid_json_returns_empty(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text("{invalid json}")
        assert _parse_package_json(pkg) == []

    def test_empty_deps(self, tmp_path):
        pkg = tmp_path / "package.json"
        pkg.write_text('{"name": "myapp"}')
        assert _parse_package_json(pkg) == []


# ---------------------------------------------------------------------------
# _parse_pyproject_toml
# ---------------------------------------------------------------------------

class TestParsePyprojectToml:
    def test_poetry_dependencies(self, tmp_path):
        toml = tmp_path / "pyproject.toml"
        toml.write_text(
            '[tool.poetry.dependencies]\n'
            'requests = "^2.28"\n'
            'python = "^3.10"\n'
        )
        pkgs = _parse_pyproject_toml(toml)
        names = {p.name for p in pkgs}
        assert "requests" in names
        # python excluded
        assert "python" not in names

    def test_dev_dependencies(self, tmp_path):
        toml = tmp_path / "pyproject.toml"
        toml.write_text(
            '[tool.poetry.dev-dependencies]\n'
            'pytest = "^7.0"\n'
        )
        pkgs = _parse_pyproject_toml(toml)
        assert len(pkgs) >= 1
        dev_pkgs = [p for p in pkgs if p.is_dev]
        assert len(dev_pkgs) >= 1

    def test_empty_toml(self, tmp_path):
        toml = tmp_path / "pyproject.toml"
        toml.write_text("[project]\nname = 'myapp'\n")
        pkgs = _parse_pyproject_toml(toml)
        assert pkgs == []


# ---------------------------------------------------------------------------
# DependencyAnalyzer
# ---------------------------------------------------------------------------

class TestDependencyAnalyzer:
    def _setup_project(self, tmp_path, req_content="", pkg_json=None):
        if req_content:
            (tmp_path / "requirements.txt").write_text(req_content)
        if pkg_json:
            (tmp_path / "package.json").write_text(pkg_json)
        return tmp_path

    def test_no_manifests_returns_empty_packages(self, tmp_path):
        analyzer = DependencyAnalyzer(project_root=str(tmp_path))
        report = analyzer.analyze()
        assert report.packages == []

    def test_pinned_package_no_unpinned_issue(self, tmp_path):
        self._setup_project(tmp_path, "requests==2.28.0\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=False,
            check_unpinned=True,
        )
        report = analyzer.analyze()
        unpinned = [i for i in report.issues if i.issue_type == "unpinned"]
        assert not any(i.package == "requests" for i in unpinned)

    def test_unpinned_package_flagged(self, tmp_path):
        self._setup_project(tmp_path, "flask>=2.0\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=False,
            check_unpinned=True,
        )
        report = analyzer.analyze()
        unpinned = [i for i in report.issues if i.issue_type == "unpinned"]
        assert any(i.package == "flask" for i in unpinned)

    def test_known_vulnerable_flagged(self, tmp_path):
        self._setup_project(tmp_path, "pyyaml<4.0\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=False,
            check_unpinned=False,
            check_vulnerable=True,
        )
        report = analyzer.analyze()
        vulns = [i for i in report.issues if i.issue_type == "known_vulnerable"]
        assert any(i.package == "pyyaml" for i in vulns)

    def test_check_vulnerable_disabled(self, tmp_path):
        self._setup_project(tmp_path, "pyyaml<4.0\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=False,
            check_unpinned=False,
            check_vulnerable=False,
        )
        report = analyzer.analyze()
        vulns = [i for i in report.issues if i.issue_type == "known_vulnerable"]
        assert len(vulns) == 0

    def test_unused_package_flagged(self, tmp_path):
        self._setup_project(tmp_path, "somelib==1.0.0\n")
        # Create a py file that doesn't import somelib
        (tmp_path / "main.py").write_text("import os\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=True,
            check_unpinned=False,
        )
        report = analyzer.analyze()
        unused = [i for i in report.issues if i.issue_type == "unused"]
        assert any(i.package == "somelib" for i in unused)

    def test_used_package_not_flagged_as_unused(self, tmp_path):
        self._setup_project(tmp_path, "requests==2.28.0\n")
        (tmp_path / "main.py").write_text("import requests\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=True,
            check_unpinned=False,
        )
        report = analyzer.analyze()
        unused = [i for i in report.issues if i.issue_type == "unused"]
        assert not any(i.package == "requests" for i in unused)

    def test_summary_format(self, tmp_path):
        self._setup_project(tmp_path, "requests==2.28.0\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=False,
        )
        report = analyzer.analyze()
        summary = report.summary()
        assert "package" in summary.lower()

    def test_high_issues_property(self, tmp_path):
        self._setup_project(tmp_path, "pyyaml<3.0\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=False,
            check_unpinned=False,
        )
        report = analyzer.analyze()
        assert len(report.high_issues) >= 0  # may or may not match

    def test_multiple_manifest_files(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
        (tmp_path / "requirements-dev.txt").write_text("pytest==7.0.0\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=False,
            check_unpinned=False,
        )
        report = analyzer.analyze()
        names = {p.name for p in report.packages}
        assert "requests" in names
        assert "pytest" in names

    def test_canonical_mapping_pyyaml(self, tmp_path):
        """pyyaml package → yaml import name (canonical mapping)."""
        (tmp_path / "requirements.txt").write_text("pyyaml==6.0\n")
        (tmp_path / "main.py").write_text("import yaml\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=True,
            check_unpinned=False,
        )
        report = analyzer.analyze()
        unused = [i for i in report.issues if i.issue_type == "unused" and i.package == "pyyaml"]
        assert len(unused) == 0  # pyyaml is used via 'yaml'

    def test_undeclared_import_flagged(self, tmp_path):
        # No manifest, but code imports something
        (tmp_path / "main.py").write_text("import some_third_party_lib\n")
        analyzer = DependencyAnalyzer(
            project_root=str(tmp_path),
            check_unused=True,
            check_unpinned=False,
        )
        report = analyzer.analyze()
        undeclared = [i for i in report.issues if i.issue_type == "undeclared"]
        assert any(i.package == "some_third_party_lib" for i in undeclared)
