"""Tests for dep_checker — dependency gap detector."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.tools.dep_checker import (
    DepIssue,
    _parse_pyproject_deps,
    _parse_requirements_txt,
    check_dependencies,
    format_issues,
)


# ---------------------------------------------------------------------------
# _parse_pyproject_deps
# ---------------------------------------------------------------------------


class TestParsePyprojectDeps:
    def test_pep621_dependencies(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\n'
            'dependencies = [\n'
            '    "pydantic>=2.0",\n'
            '    "litellm>=1.20.0",\n'
            ']\n'
        )
        deps = _parse_pyproject_deps(tmp_path / "pyproject.toml")
        assert "pydantic>=2.0" in deps
        assert "litellm>=1.20.0" in deps

    def test_pep621_optional_deps_included(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\n'
            '[project.optional-dependencies]\n'
            'dev = ["pytest>=7.0", "mypy"]\n'
        )
        deps = _parse_pyproject_deps(tmp_path / "pyproject.toml")
        assert any("pytest" in d for d in deps)
        assert "mypy" in deps

    def test_poetry_style_deps(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\n'
            'python = "^3.12"\n'
            'pydantic = ">=2.0"\n'
            'requests = "*"\n'
        )
        deps = _parse_pyproject_deps(tmp_path / "pyproject.toml")
        # python entry must be excluded
        assert not any("python" in d.lower() for d in deps)
        assert any("pydantic" in d for d in deps)
        # "*" means no version constraint — just the package name
        assert "requests" in deps

    def test_missing_file_returns_empty(self, tmp_path):
        deps = _parse_pyproject_deps(tmp_path / "nonexistent.toml")
        assert deps == []

    def test_malformed_toml_returns_empty(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("this is not : valid [ toml !!!")
        deps = _parse_pyproject_deps(tmp_path / "pyproject.toml")
        assert deps == []


# ---------------------------------------------------------------------------
# _parse_requirements_txt
# ---------------------------------------------------------------------------


class TestParseRequirementsTxt:
    def test_normal_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text(
            "pydantic>=2.0\n"
            "litellm\n"
        )
        reqs = _parse_requirements_txt(tmp_path / "requirements.txt")
        assert "pydantic>=2.0" in reqs
        assert "litellm" in reqs

    def test_comments_and_blanks_skipped(self, tmp_path):
        (tmp_path / "requirements.txt").write_text(
            "# This is a comment\n"
            "\n"
            "pydantic>=2.0\n"
            "# another comment\n"
            "\n"
            "requests\n"
        )
        reqs = _parse_requirements_txt(tmp_path / "requirements.txt")
        assert len(reqs) == 2
        assert "pydantic>=2.0" in reqs
        assert "requests" in reqs

    def test_inline_comments_stripped(self, tmp_path):
        (tmp_path / "requirements.txt").write_text(
            "pydantic>=2.0  # required for validation\n"
        )
        reqs = _parse_requirements_txt(tmp_path / "requirements.txt")
        assert len(reqs) == 1
        assert reqs[0] == "pydantic>=2.0"

    def test_dash_r_lines_ignored(self, tmp_path):
        (tmp_path / "requirements.txt").write_text(
            "-r base.txt\n"
            "--index-url https://pypi.org\n"
            "pydantic\n"
        )
        reqs = _parse_requirements_txt(tmp_path / "requirements.txt")
        assert reqs == ["pydantic"]

    def test_missing_file_returns_empty(self, tmp_path):
        reqs = _parse_requirements_txt(tmp_path / "nonexistent.txt")
        assert reqs == []


# ---------------------------------------------------------------------------
# check_dependencies
# ---------------------------------------------------------------------------


class TestCheckDependencies:
    def test_empty_declared_no_issues(self):
        assert check_dependencies([], installed={}) == []

    def test_satisfied_requirement_no_issue(self):
        issues = check_dependencies(
            ["pydantic>=2.0"],
            installed={"pydantic": "2.7.0"},
        )
        assert issues == []

    def test_missing_package_reported(self):
        issues = check_dependencies(
            ["nonexistent-pkg>=1.0"],
            installed={},
        )
        assert len(issues) == 1
        assert issues[0].kind == "MISSING"
        assert issues[0].package == "nonexistent-pkg"
        assert issues[0].installed == ""

    def test_version_too_old_mismatch(self):
        issues = check_dependencies(
            ["pydantic>=2.0"],
            installed={"pydantic": "1.10.0"},
        )
        assert len(issues) == 1
        assert issues[0].kind == "MISMATCH"
        assert issues[0].installed == "1.10.0"
        assert ">=2.0" in issues[0].required

    def test_exact_version_mismatch(self):
        issues = check_dependencies(
            ["pydantic==2.7.0"],
            installed={"pydantic": "2.6.0"},
        )
        assert len(issues) == 1
        assert issues[0].kind == "MISMATCH"

    def test_no_specifier_any_version_ok(self):
        issues = check_dependencies(
            ["pydantic"],
            installed={"pydantic": "2.7.0"},
        )
        assert issues == []

    def test_case_insensitive_package_lookup(self):
        # Package declared as "PyYAML" but installed dict uses "pyyaml"
        issues = check_dependencies(
            ["PyYAML>=6.0"],
            installed={"pyyaml": "6.0.1"},
        )
        assert issues == []

    def test_hyphen_underscore_normalization(self):
        # "pydantic-settings" in declared, "pydantic_settings" in installed
        issues = check_dependencies(
            ["pydantic-settings>=2.0"],
            installed={"pydantic_settings": "2.2.0"},
        )
        assert issues == []

    def test_multiple_issues_returned(self):
        issues = check_dependencies(
            ["missing-pkg", "pydantic>=3.0"],
            installed={"pydantic": "2.7.0"},
        )
        kinds = {i.kind for i in issues}
        assert "MISSING" in kinds
        assert "MISMATCH" in kinds

    def test_invalid_specifier_skipped_gracefully(self):
        # Malformed specifier should not raise
        issues = check_dependencies(
            ["pydantic>=this-is-not-a-version"],
            installed={"pydantic": "2.7.0"},
        )
        # Should not raise — result can be empty or contain issues, just no exception
        assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# format_issues
# ---------------------------------------------------------------------------


class TestFormatIssues:
    def test_no_issues_ok_message(self):
        result = format_issues([], declared_count=5)
        assert "[OK]" in result
        assert "5" in result

    def test_missing_issue_shown(self):
        issues = [
            DepIssue(
                kind="MISSING",
                package="somepkg",
                required=">=1.0",
                installed="",
                detail='Not installed. Run: pip install "somepkg"',
            )
        ]
        result = format_issues(issues, declared_count=3)
        assert "somepkg" in result
        assert "MISSING" in result or "Missing" in result or "pip install" in result

    def test_mismatch_issue_shown(self):
        issues = [
            DepIssue(
                kind="MISMATCH",
                package="pydantic",
                required=">=3.0",
                installed="2.7.0",
                detail="Installed 2.7.0 does not satisfy >=3.0",
            )
        ]
        result = format_issues(issues, declared_count=1)
        assert "pydantic" in result
        assert "2.7.0" in result
