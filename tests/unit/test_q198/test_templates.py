"""Tests for TemplateLibrary, ProjectTemplate — task 1104."""
from __future__ import annotations

import unittest

from lidco.onboarding.detector import ProjectType
from lidco.onboarding.templates import ProjectTemplate, TemplateLibrary


class TestProjectTemplateFrozen(unittest.TestCase):
    def test_creation(self):
        t = ProjectTemplate(
            name="test",
            project_type=ProjectType.PYTHON,
            files=(("a.py", "content"),),
            description="Test template",
        )
        self.assertEqual(t.name, "test")
        self.assertEqual(len(t.files), 1)

    def test_frozen(self):
        t = ProjectTemplate(
            name="test",
            project_type=ProjectType.PYTHON,
            files=(),
            description="",
        )
        with self.assertRaises(AttributeError):
            t.name = "other"  # type: ignore[misc]


class TestTemplateLibraryInit(unittest.TestCase):
    def test_empty(self):
        lib = TemplateLibrary()
        self.assertIsNone(lib.get("anything"))

    def test_with_templates(self):
        t = ProjectTemplate("a", ProjectType.PYTHON, (), "desc")
        lib = TemplateLibrary((t,))
        self.assertIsNotNone(lib.get("a"))


class TestTemplateLibraryRegister(unittest.TestCase):
    def test_register_returns_new(self):
        lib1 = TemplateLibrary()
        t = ProjectTemplate("a", ProjectType.PYTHON, (), "desc")
        lib2 = lib1.register(t)
        self.assertIsNot(lib1, lib2)
        self.assertIsNone(lib1.get("a"))
        self.assertIsNotNone(lib2.get("a"))

    def test_register_replaces_same_name(self):
        t1 = ProjectTemplate("a", ProjectType.PYTHON, (), "v1")
        t2 = ProjectTemplate("a", ProjectType.PYTHON, (), "v2")
        lib = TemplateLibrary().register(t1).register(t2)
        self.assertEqual(lib.get("a").description, "v2")

    def test_register_preserves_others(self):
        t1 = ProjectTemplate("a", ProjectType.PYTHON, (), "")
        t2 = ProjectTemplate("b", ProjectType.NODE, (), "")
        lib = TemplateLibrary().register(t1).register(t2)
        self.assertIsNotNone(lib.get("a"))
        self.assertIsNotNone(lib.get("b"))


class TestTemplateLibraryGet(unittest.TestCase):
    def test_get_existing(self):
        t = ProjectTemplate("x", ProjectType.GO, (), "go template")
        lib = TemplateLibrary((t,))
        self.assertEqual(lib.get("x").description, "go template")

    def test_get_missing_returns_none(self):
        lib = TemplateLibrary()
        self.assertIsNone(lib.get("missing"))


class TestTemplateLibraryListForType(unittest.TestCase):
    def test_filters_by_type(self):
        t1 = ProjectTemplate("py1", ProjectType.PYTHON, (), "")
        t2 = ProjectTemplate("node1", ProjectType.NODE, (), "")
        t3 = ProjectTemplate("py2", ProjectType.PYTHON, (), "")
        lib = TemplateLibrary((t1, t2, t3))
        py = lib.list_for_type(ProjectType.PYTHON)
        self.assertEqual(len(py), 2)
        names = {t.name for t in py}
        self.assertEqual(names, {"py1", "py2"})

    def test_empty_for_missing_type(self):
        t = ProjectTemplate("py", ProjectType.PYTHON, (), "")
        lib = TemplateLibrary((t,))
        self.assertEqual(lib.list_for_type(ProjectType.RUST), ())


class TestDefaultTemplates(unittest.TestCase):
    def test_returns_template_library(self):
        lib = TemplateLibrary.default_templates()
        self.assertIsInstance(lib, TemplateLibrary)

    def test_has_python_cli(self):
        lib = TemplateLibrary.default_templates()
        self.assertIsNotNone(lib.get("python-cli"))

    def test_has_node_app(self):
        lib = TemplateLibrary.default_templates()
        self.assertIsNotNone(lib.get("node-app"))

    def test_has_rust_cli(self):
        lib = TemplateLibrary.default_templates()
        self.assertIsNotNone(lib.get("rust-cli"))

    def test_python_templates_have_files(self):
        lib = TemplateLibrary.default_templates()
        t = lib.get("python-cli")
        self.assertGreater(len(t.files), 0)
