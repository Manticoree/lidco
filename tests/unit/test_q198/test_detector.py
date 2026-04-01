"""Tests for ProjectDetector, ProjectType, FrameworkInfo, ProjectInfo — task 1102."""
from __future__ import annotations

import json
import os
import unittest

from lidco.onboarding.detector import (
    FrameworkInfo,
    ProjectDetector,
    ProjectInfo,
    ProjectType,
)


class TestProjectTypeEnum(unittest.TestCase):
    def test_all_members(self):
        names = {m.name for m in ProjectType}
        self.assertIn("PYTHON", names)
        self.assertIn("NODE", names)
        self.assertIn("RUST", names)
        self.assertIn("GO", names)
        self.assertIn("JAVA", names)
        self.assertIn("RUBY", names)
        self.assertIn("UNKNOWN", names)

    def test_values(self):
        self.assertEqual(ProjectType.PYTHON.value, "python")
        self.assertEqual(ProjectType.UNKNOWN.value, "unknown")


class TestFrameworkInfoFrozen(unittest.TestCase):
    def test_creation(self):
        fw = FrameworkInfo(name="django", version="4.2", config_file="requirements.txt")
        self.assertEqual(fw.name, "django")
        self.assertEqual(fw.version, "4.2")

    def test_frozen(self):
        fw = FrameworkInfo(name="flask", version=None, config_file="requirements.txt")
        with self.assertRaises(AttributeError):
            fw.name = "other"  # type: ignore[misc]


class TestProjectInfoFrozen(unittest.TestCase):
    def test_creation(self):
        info = ProjectInfo(
            project_type=ProjectType.PYTHON,
            frameworks=(),
            build_system="pyproject",
            is_monorepo=False,
            root_path="/tmp/proj",
        )
        self.assertEqual(info.project_type, ProjectType.PYTHON)
        self.assertFalse(info.is_monorepo)

    def test_frozen(self):
        info = ProjectInfo(
            project_type=ProjectType.NODE,
            frameworks=(),
            build_system=None,
            is_monorepo=False,
            root_path="/x",
        )
        with self.assertRaises(AttributeError):
            info.project_type = ProjectType.RUST  # type: ignore[misc]


class TestDetectType(unittest.TestCase):
    def test_python_pyproject(self, tmp_path=None):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "pyproject.toml"), "w").close()
            det = ProjectDetector()
            self.assertEqual(det.detect_type(td), ProjectType.PYTHON)

    def test_node_package_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "package.json"), "w") as f:
                json.dump({"name": "test"}, f)
            det = ProjectDetector()
            self.assertEqual(det.detect_type(td), ProjectType.NODE)

    def test_rust_cargo(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "Cargo.toml"), "w").close()
            det = ProjectDetector()
            self.assertEqual(det.detect_type(td), ProjectType.RUST)

    def test_go_mod(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "go.mod"), "w").close()
            det = ProjectDetector()
            self.assertEqual(det.detect_type(td), ProjectType.GO)

    def test_java_pom(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "pom.xml"), "w").close()
            det = ProjectDetector()
            self.assertEqual(det.detect_type(td), ProjectType.JAVA)

    def test_ruby_gemfile(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "Gemfile"), "w").close()
            det = ProjectDetector()
            self.assertEqual(det.detect_type(td), ProjectType.RUBY)

    def test_unknown_empty(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            det = ProjectDetector()
            self.assertEqual(det.detect_type(td), ProjectType.UNKNOWN)


class TestDetectFrameworks(unittest.TestCase):
    def test_node_frameworks_from_package_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            pkg = {"dependencies": {"react": "^18.0", "express": "^4.0"}}
            with open(os.path.join(td, "package.json"), "w") as f:
                json.dump(pkg, f)
            det = ProjectDetector()
            fws = det.detect_frameworks(td)
            names = {fw.name for fw in fws}
            self.assertIn("react", names)
            self.assertIn("express", names)

    def test_python_frameworks_from_requirements(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "requirements.txt"), "w") as f:
                f.write("django==4.2\nflask>=2.0\n")
            det = ProjectDetector()
            fws = det.detect_frameworks(td)
            names = {fw.name for fw in fws}
            self.assertIn("django", names)
            self.assertIn("flask", names)

    def test_empty_dir_no_frameworks(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            det = ProjectDetector()
            self.assertEqual(det.detect_frameworks(td), ())

    def test_framework_version_extracted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "requirements.txt"), "w") as f:
                f.write("django==4.2\n")
            det = ProjectDetector()
            fws = det.detect_frameworks(td)
            django = [fw for fw in fws if fw.name == "django"]
            self.assertEqual(len(django), 1)
            self.assertEqual(django[0].version, "4.2")


class TestIsMonorepo(unittest.TestCase):
    def test_lerna_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "lerna.json"), "w").close()
            det = ProjectDetector()
            self.assertTrue(det.is_monorepo(td))

    def test_package_json_workspaces(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "package.json"), "w") as f:
                json.dump({"workspaces": ["packages/*"]}, f)
            det = ProjectDetector()
            self.assertTrue(det.is_monorepo(td))

    def test_not_monorepo(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            det = ProjectDetector()
            self.assertFalse(det.is_monorepo(td))


class TestDetectFull(unittest.TestCase):
    def test_full_detection_python(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "pyproject.toml"), "w").close()
            det = ProjectDetector()
            info = det.detect(td)
            self.assertIsInstance(info, ProjectInfo)
            self.assertEqual(info.project_type, ProjectType.PYTHON)
            self.assertEqual(info.root_path, os.path.abspath(td))

    def test_full_detection_returns_build_system(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "Makefile"), "w").close()
            det = ProjectDetector()
            info = det.detect(td)
            self.assertEqual(info.build_system, "make")
