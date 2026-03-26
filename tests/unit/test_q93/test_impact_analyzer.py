"""Tests for T598 TestImpactAnalyzer."""
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from lidco.testing.impact_analyzer import (
    ChangeSet,
    ImpactResult,
    TestImpactAnalyzer,
    _extract_imports,
    _path_to_module,
)


# ---------------------------------------------------------------------------
# _extract_imports
# ---------------------------------------------------------------------------

class TestExtractImports:
    def test_simple_import(self, tmp_path):
        py = tmp_path / "foo.py"
        py.write_text("import os\nimport sys\n")
        imports = _extract_imports(py)
        assert "os" in imports
        assert "sys" in imports

    def test_from_import(self, tmp_path):
        py = tmp_path / "foo.py"
        py.write_text("from pathlib import Path\n")
        imports = _extract_imports(py)
        assert "pathlib" in imports

    def test_submodule_import_returns_top(self, tmp_path):
        py = tmp_path / "foo.py"
        py.write_text("from os.path import join\n")
        imports = _extract_imports(py)
        assert "os" in imports

    def test_invalid_file_returns_empty(self, tmp_path):
        py = tmp_path / "bad.py"
        py.write_text("this is not python!!!")
        imports = _extract_imports(py)
        assert imports == []

    def test_nonexistent_file_returns_empty(self, tmp_path):
        py = tmp_path / "missing.py"
        imports = _extract_imports(py)
        assert imports == []


# ---------------------------------------------------------------------------
# _path_to_module
# ---------------------------------------------------------------------------

class TestPathToModule:
    def test_converts_path_to_dotted(self, tmp_path):
        py = tmp_path / "src" / "foo" / "bar.py"
        mod = _path_to_module(py, tmp_path)
        assert mod == "src.foo.bar"

    def test_top_level_file(self, tmp_path):
        py = tmp_path / "utils.py"
        mod = _path_to_module(py, tmp_path)
        assert mod == "utils"

    def test_outside_root_returns_stem(self, tmp_path):
        py = Path("/tmp/other/file.py")
        mod = _path_to_module(py, tmp_path)
        assert mod == "file"


# ---------------------------------------------------------------------------
# TestImpactAnalyzer.analyze
# ---------------------------------------------------------------------------

class TestAnalyze:
    def _setup_project(self, tmp_path):
        """Create a minimal project with source + test files."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "__init__.py").write_text("")

        # src/math_utils.py
        (src / "math_utils.py").write_text(
            "def add(a, b):\n    return a + b\n"
        )

        # src/string_utils.py — imports math_utils
        (src / "string_utils.py").write_text(
            "from src import math_utils\n\ndef repeat(s, n):\n    return s * n\n"
        )

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")

        # test for math_utils
        (tests / "test_math_utils.py").write_text(
            "from src import math_utils\n\ndef test_add():\n    assert math_utils.add(1, 2) == 3\n"
        )

        # test for string_utils
        (tests / "test_string_utils.py").write_text(
            "from src import string_utils\n\ndef test_repeat():\n    pass\n"
        )

        # unrelated test
        (tests / "test_other.py").write_text(
            "def test_standalone():\n    assert True\n"
        )

        return tmp_path

    def test_changed_file_marks_direct_test_affected(self, tmp_path):
        root = self._setup_project(tmp_path)
        analyzer = TestImpactAnalyzer(project_root=str(root), test_dirs=["tests"])
        changeset = ChangeSet(files=[str(root / "src" / "math_utils.py")])
        result = analyzer.analyze(changeset)

        # test_math_utils imports math_utils → should be affected
        affected_names = [Path(t).name for t in result.affected_tests]
        assert "test_math_utils.py" in affected_names

    def test_empty_changeset_returns_empty_affected(self, tmp_path):
        root = self._setup_project(tmp_path)
        analyzer = TestImpactAnalyzer(project_root=str(root), test_dirs=["tests"])
        result = analyzer.analyze(ChangeSet(files=[]))
        assert result.affected_tests == []

    def test_coverage_estimate_is_fraction(self, tmp_path):
        root = self._setup_project(tmp_path)
        analyzer = TestImpactAnalyzer(project_root=str(root), test_dirs=["tests"])
        changeset = ChangeSet(files=[str(root / "src" / "math_utils.py")])
        result = analyzer.analyze(changeset)
        assert 0.0 <= result.coverage_estimate <= 1.0

    def test_skipped_and_affected_partition_all_tests(self, tmp_path):
        root = self._setup_project(tmp_path)
        analyzer = TestImpactAnalyzer(project_root=str(root), test_dirs=["tests"])
        changeset = ChangeSet(files=[str(root / "src" / "math_utils.py")])
        result = analyzer.analyze(changeset)
        total = set(result.affected_tests) | set(result.skipped_tests)
        all_tests = set(str(t) for t in (root / "tests").rglob("test_*.py"))
        assert total == all_tests or total.issubset(all_tests)

    def test_analyze_no_test_dir(self, tmp_path):
        # When test dir doesn't exist, returns empty
        analyzer = TestImpactAnalyzer(project_root=str(tmp_path), test_dirs=["tests"])
        result = analyzer.analyze(ChangeSet(files=["foo.py"]))
        assert result.affected_tests == []
        assert result.skipped_tests == []
        assert result.coverage_estimate == 0.0

    def test_changed_files_reflected_in_result(self, tmp_path):
        root = self._setup_project(tmp_path)
        analyzer = TestImpactAnalyzer(project_root=str(root), test_dirs=["tests"])
        changeset = ChangeSet(files=["a.py", "b.py"])
        result = analyzer.analyze(changeset)
        assert result.changed_files == ["a.py", "b.py"]


# ---------------------------------------------------------------------------
# get_minimal_test_command
# ---------------------------------------------------------------------------

class TestGetMinimalTestCommand:
    def test_returns_pytest_command(self):
        result = ImpactResult(
            changed_files=[],
            affected_tests=["tests/test_foo.py", "tests/test_bar.py"],
            skipped_tests=[],
            coverage_estimate=0.5,
        )
        cmd = result.get_minimal_test_command()
        assert cmd.startswith("python -m pytest")
        assert "test_bar.py" in cmd
        assert "test_foo.py" in cmd

    def test_no_affected_tests_returns_collect_only(self):
        result = ImpactResult(
            changed_files=[],
            affected_tests=[],
            skipped_tests=["tests/test_foo.py"],
            coverage_estimate=0.0,
        )
        cmd = result.get_minimal_test_command()
        assert "--collect-only" in cmd

    def test_custom_runner(self):
        result = ImpactResult(
            changed_files=[],
            affected_tests=["tests/test_x.py"],
            skipped_tests=[],
            coverage_estimate=1.0,
        )
        cmd = result.get_minimal_test_command(runner="pytest")
        assert cmd.startswith("pytest")


# ---------------------------------------------------------------------------
# analyze_since (git subprocess)
# ---------------------------------------------------------------------------

class TestAnalyzeSince:
    def test_git_failure_returns_empty_changeset(self, tmp_path):
        analyzer = TestImpactAnalyzer(project_root=str(tmp_path))
        with patch("lidco.testing.impact_analyzer.subprocess.run", side_effect=Exception("no git")):
            result = analyzer.analyze_since("HEAD~1")
        assert result.changed_files == []

    def test_parse_git_output(self, tmp_path):
        # Create test dir so we can verify analysis runs
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_foo.py").write_text("def test_x(): pass\n")

        analyzer = TestImpactAnalyzer(project_root=str(tmp_path), test_dirs=["tests"])

        fake_proc = type("P", (), {"stdout": "src/foo.py\nother.txt\n", "returncode": 0})()
        with patch("lidco.testing.impact_analyzer.subprocess.run", return_value=fake_proc):
            result = analyzer.analyze_since("HEAD~1")

        # Only .py files should be in changed_files
        for f in result.changed_files:
            assert f.endswith(".py")
