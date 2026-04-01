"""Tests for docgen.readme_gen — READMEConfig, READMEGenerator."""
from __future__ import annotations

import os
import tempfile
import unittest

from lidco.docgen.readme_gen import READMEConfig, READMEGenerator


class TestREADMEConfig(unittest.TestCase):
    def test_frozen(self):
        c = READMEConfig(project_name="P", description="D", include_badges=True, include_install=True)
        with self.assertRaises(AttributeError):
            c.project_name = "X"  # type: ignore[misc]

    def test_fields(self):
        c = READMEConfig("MyProject", "A project", False, True)
        self.assertEqual(c.project_name, "MyProject")
        self.assertEqual(c.description, "A project")
        self.assertFalse(c.include_badges)
        self.assertTrue(c.include_install)

    def test_equality(self):
        a = READMEConfig("P", "D", True, True)
        b = READMEConfig("P", "D", True, True)
        self.assertEqual(a, b)


class TestREADMEGenerator(unittest.TestCase):
    def _make_gen(self, name="TestProject", desc="Test", badges=True, install=True):
        config = READMEConfig(name, desc, badges, install)
        return READMEGenerator(config)

    def test_generate_title(self):
        gen = self._make_gen(name="MyLib")
        result = gen.generate(".")
        self.assertIn("# MyLib", result)

    def test_generate_description(self):
        gen = self._make_gen(desc="A cool library")
        result = gen.generate(".")
        self.assertIn("A cool library", result)

    def test_generate_with_badges(self):
        gen = self._make_gen(badges=True)
        result = gen.generate(".")
        self.assertIn("build", result.lower())

    def test_generate_without_badges(self):
        gen = self._make_gen(badges=False)
        result = gen.generate(".")
        self.assertNotIn("img.shields.io", result)

    def test_generate_with_install(self):
        gen = self._make_gen(install=True, name="MyPkg")
        result = gen.generate(".")
        self.assertIn("pip install", result)
        self.assertIn("mypkg", result)

    def test_generate_without_install(self):
        gen = self._make_gen(install=False)
        result = gen.generate(".")
        self.assertNotIn("pip install", result)

    def test_detect_sections_empty(self):
        gen = self._make_gen()
        with tempfile.TemporaryDirectory() as td:
            sections = gen.detect_sections(td)
            self.assertEqual(sections, ())

    def test_detect_sections_with_tests(self):
        gen = self._make_gen()
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "tests"))
            sections = gen.detect_sections(td)
            self.assertIn("Testing", sections)

    def test_detect_sections_with_license(self):
        gen = self._make_gen()
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "LICENSE"), "w").close()
            sections = gen.detect_sections(td)
            self.assertIn("License", sections)

    def test_detect_sections_with_docs(self):
        gen = self._make_gen()
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "docs"))
            sections = gen.detect_sections(td)
            self.assertIn("Documentation", sections)

    def test_detect_sections_nonexistent_path(self):
        gen = self._make_gen()
        sections = gen.detect_sections("/nonexistent/path")
        self.assertEqual(sections, ())

    def test_detect_sections_returns_tuple(self):
        gen = self._make_gen()
        with tempfile.TemporaryDirectory() as td:
            result = gen.detect_sections(td)
            self.assertIsInstance(result, tuple)

    def test_generate_badge_build(self):
        gen = self._make_gen()
        badge = gen.generate_badge("build")
        self.assertIn("build", badge)
        self.assertIn("passing", badge)

    def test_generate_badge_unknown(self):
        gen = self._make_gen()
        badge = gen.generate_badge("custom")
        self.assertIn("custom", badge)

    def test_generate_badge_version(self):
        gen = self._make_gen()
        badge = gen.generate_badge("version")
        self.assertIn("version", badge)

    def test_generate_returns_string(self):
        gen = self._make_gen()
        result = gen.generate(".")
        self.assertIsInstance(result, str)

    def test_detect_sections_contributing(self):
        gen = self._make_gen()
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "CONTRIBUTING.md"), "w").close()
            sections = gen.detect_sections(td)
            self.assertIn("Contributing", sections)

    def test_readme_config_different_not_equal(self):
        a = READMEConfig("A", "D", True, True)
        b = READMEConfig("B", "D", True, True)
        self.assertNotEqual(a, b)


class TestREADMEGenAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.docgen import readme_gen

        self.assertIn("READMEConfig", readme_gen.__all__)
        self.assertIn("READMEGenerator", readme_gen.__all__)


if __name__ == "__main__":
    unittest.main()
