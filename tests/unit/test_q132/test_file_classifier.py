"""Tests for Q132 FileClassifier."""
from __future__ import annotations
import unittest
from lidco.fs.file_classifier import FileClassifier, FileClass


class TestFileClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = FileClassifier()

    def test_python_source(self):
        fc = self.classifier.classify("src/main.py")
        self.assertEqual(fc.language, "python")
        self.assertEqual(fc.category, "source")

    def test_javascript_source(self):
        fc = self.classifier.classify("src/app.js")
        self.assertEqual(fc.language, "javascript")
        self.assertEqual(fc.category, "source")

    def test_typescript(self):
        fc = self.classifier.classify("src/index.ts")
        self.assertEqual(fc.language, "typescript")

    def test_tsx(self):
        fc = self.classifier.classify("src/App.tsx")
        self.assertEqual(fc.language, "typescript")

    def test_test_file_by_prefix(self):
        fc = self.classifier.classify("tests/test_main.py")
        self.assertEqual(fc.category, "test")

    def test_test_file_by_suffix(self):
        fc = self.classifier.classify("src/main_test.py")
        self.assertEqual(fc.category, "test")

    def test_test_in_path(self):
        fc = self.classifier.classify("src/tests/utils.py")
        self.assertEqual(fc.category, "test")

    def test_json_config(self):
        fc = self.classifier.classify("config.json")
        self.assertEqual(fc.category, "config")

    def test_yaml_config(self):
        fc = self.classifier.classify("settings.yaml")
        self.assertEqual(fc.category, "config")

    def test_markdown_doc(self):
        fc = self.classifier.classify("README.md")
        self.assertEqual(fc.category, "doc")

    def test_binary_asset(self):
        fc = self.classifier.classify("image.png")
        self.assertEqual(fc.category, "asset")
        self.assertTrue(fc.is_binary)

    def test_generated_min_js(self):
        fc = self.classifier.classify("dist/bundle.min.js")
        self.assertEqual(fc.category, "generated")

    def test_generated_dist(self):
        fc = self.classifier.classify("dist/main.py")
        self.assertEqual(fc.category, "generated")

    def test_unknown_extension(self):
        fc = self.classifier.classify("data.xyz")
        self.assertEqual(fc.category, "unknown")

    def test_classify_many(self):
        paths = ["src/main.py", "README.md", "src/test_app.py"]
        results = self.classifier.classify_many(paths)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].language, "python")

    def test_filter_by_category(self):
        fcs = self.classifier.classify_many(["a.py", "b.md", "test_c.py"])
        sources = self.classifier.filter_by_category(fcs, "source")
        tests = self.classifier.filter_by_category(fcs, "test")
        self.assertTrue(any(f.path == "a.py" for f in sources))
        self.assertTrue(any(f.path == "test_c.py" for f in tests))

    def test_language_stats(self):
        fcs = self.classifier.classify_many(["a.py", "b.py", "c.js"])
        stats = self.classifier.language_stats(fcs)
        self.assertEqual(stats["python"], 2)
        self.assertEqual(stats["javascript"], 1)

    def test_path_preserved(self):
        fc = self.classifier.classify("my/path/file.py")
        self.assertEqual(fc.path, "my/path/file.py")

    def test_toml_config(self):
        fc = self.classifier.classify("pyproject.toml")
        self.assertEqual(fc.category, "config")

    def test_rst_doc(self):
        fc = self.classifier.classify("docs/index.rst")
        self.assertEqual(fc.category, "doc")

    def test_pyc_generated(self):
        fc = self.classifier.classify("__pycache__/main.cpython-313.pyc")
        self.assertEqual(fc.category, "generated")

    def test_go_source(self):
        fc = self.classifier.classify("main.go")
        self.assertEqual(fc.language, "go")
        self.assertEqual(fc.category, "source")

    def test_shell_source(self):
        fc = self.classifier.classify("run.sh")
        self.assertEqual(fc.language, "shell")

    def test_pdf_binary(self):
        fc = self.classifier.classify("report.pdf")
        self.assertTrue(fc.is_binary)
        self.assertEqual(fc.category, "asset")


if __name__ == "__main__":
    unittest.main()
