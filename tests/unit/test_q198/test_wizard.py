"""Tests for InitWizard, WizardStep, WizardResult — task 1103."""
from __future__ import annotations

import unittest

from lidco.onboarding.detector import FrameworkInfo, ProjectInfo, ProjectType
from lidco.onboarding.wizard import InitWizard, WizardResult, WizardStep


def _make_info(
    ptype: ProjectType = ProjectType.PYTHON,
    frameworks: tuple[FrameworkInfo, ...] = (),
    build_system: str | None = "pyproject",
    is_monorepo: bool = False,
) -> ProjectInfo:
    return ProjectInfo(
        project_type=ptype,
        frameworks=frameworks,
        build_system=build_system,
        is_monorepo=is_monorepo,
        root_path="/tmp/proj",
    )


class TestWizardStepFrozen(unittest.TestCase):
    def test_creation(self):
        s = WizardStep(name="x", question="Q?", default="d", required=True)
        self.assertEqual(s.name, "x")
        self.assertTrue(s.required)

    def test_frozen(self):
        s = WizardStep(name="x", question="Q?", default="d", required=True)
        with self.assertRaises(AttributeError):
            s.name = "y"  # type: ignore[misc]


class TestWizardResultFrozen(unittest.TestCase):
    def test_creation(self):
        r = WizardResult(steps_completed=("a",), config={"k": "v"}, claude_md="# hi")
        self.assertEqual(r.steps_completed, ("a",))
        self.assertEqual(r.claude_md, "# hi")

    def test_frozen(self):
        r = WizardResult(steps_completed=(), config={}, claude_md="")
        with self.assertRaises(AttributeError):
            r.claude_md = "new"  # type: ignore[misc]


class TestInitWizardSteps(unittest.TestCase):
    def test_steps_returns_tuple(self):
        w = InitWizard(_make_info())
        self.assertIsInstance(w.steps(), tuple)

    def test_steps_have_names(self):
        w = InitWizard(_make_info())
        names = [s.name for s in w.steps()]
        self.assertIn("project_name", names)
        self.assertIn("test_command", names)

    def test_python_defaults(self):
        w = InitWizard(_make_info(ProjectType.PYTHON))
        steps = {s.name: s for s in w.steps()}
        self.assertEqual(steps["test_command"].default, "pytest")

    def test_node_defaults(self):
        w = InitWizard(_make_info(ProjectType.NODE))
        steps = {s.name: s for s in w.steps()}
        self.assertEqual(steps["test_command"].default, "npm test")

    def test_unknown_no_defaults(self):
        w = InitWizard(_make_info(ProjectType.UNKNOWN))
        steps = {s.name: s for s in w.steps()}
        self.assertEqual(steps["test_command"].default, "")


class TestGenerateConfig(unittest.TestCase):
    def test_includes_project_type(self):
        w = InitWizard(_make_info())
        cfg = w.generate_config({"project_name": "myproj"})
        self.assertEqual(cfg["project_type"], "python")

    def test_includes_build_system(self):
        w = InitWizard(_make_info(build_system="cargo"))
        cfg = w.generate_config({})
        self.assertEqual(cfg["build_system"], "cargo")

    def test_includes_frameworks(self):
        fw = FrameworkInfo(name="django", version="4.2", config_file="req.txt")
        w = InitWizard(_make_info(frameworks=(fw,)))
        cfg = w.generate_config({})
        self.assertIn("django", cfg["frameworks"])

    def test_merges_answers(self):
        w = InitWizard(_make_info())
        cfg = w.generate_config({"project_name": "cool", "custom_key": "val"})
        self.assertEqual(cfg["project_name"], "cool")
        self.assertEqual(cfg["custom_key"], "val")


class TestGenerateClaudeMd(unittest.TestCase):
    def test_contains_project_type(self):
        w = InitWizard(_make_info())
        md = w.generate_claude_md({"project_type": "python", "project_name": "Test"})
        self.assertIn("python", md)

    def test_contains_test_command(self):
        w = InitWizard(_make_info())
        md = w.generate_claude_md({"test_command": "pytest"})
        self.assertIn("pytest", md)

    def test_contains_header(self):
        w = InitWizard(_make_info())
        md = w.generate_claude_md({"project_name": "MyApp"})
        self.assertIn("# MyApp", md)


class TestRun(unittest.TestCase):
    def test_run_returns_wizard_result(self):
        w = InitWizard(_make_info())
        result = w.run({"project_name": "test"})
        self.assertIsInstance(result, WizardResult)

    def test_run_steps_completed(self):
        w = InitWizard(_make_info())
        result = w.run({"project_name": "test", "description": "desc"})
        self.assertIn("project_name", result.steps_completed)
        self.assertIn("description", result.steps_completed)

    def test_run_generates_claude_md(self):
        w = InitWizard(_make_info())
        result = w.run({"project_name": "test"})
        self.assertIn("# test", result.claude_md)

    def test_run_with_empty_answers_uses_defaults(self):
        w = InitWizard(_make_info(ProjectType.PYTHON))
        result = w.run({})
        # test_command should use default "pytest"
        self.assertIn("test_command", result.steps_completed)
