"""Tests for LanguageDetector (Q250)."""
from __future__ import annotations

import unittest

from lidco.polyglot.detector import DetectionResult, LanguageDetector


class TestDetectionResult(unittest.TestCase):
    def test_frozen(self):
        r = DetectionResult(language="python", confidence=0.9, method="extension")
        with self.assertRaises(AttributeError):
            r.language = "go"  # type: ignore[misc]

    def test_fields(self):
        r = DetectionResult(language="go", confidence=0.5, method="content")
        self.assertEqual(r.language, "go")
        self.assertAlmostEqual(r.confidence, 0.5)
        self.assertEqual(r.method, "content")


class TestDetectByExtension(unittest.TestCase):
    def setUp(self):
        self.det = LanguageDetector()

    def test_python(self):
        r = self.det.detect_by_extension("main.py")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "python")
        self.assertAlmostEqual(r.confidence, 0.9)
        self.assertEqual(r.method, "extension")

    def test_javascript(self):
        r = self.det.detect_by_extension("app.js")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "javascript")

    def test_typescript(self):
        r = self.det.detect_by_extension("index.ts")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "typescript")

    def test_go(self):
        r = self.det.detect_by_extension("main.go")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "go")

    def test_rust(self):
        r = self.det.detect_by_extension("lib.rs")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "rust")

    def test_java(self):
        r = self.det.detect_by_extension("App.java")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "java")

    def test_c_variants(self):
        for ext in ("file.c", "file.cpp", "file.h"):
            r = self.det.detect_by_extension(ext)
            self.assertIsNotNone(r, f"Failed for {ext}")
            self.assertEqual(r.language, "c")

    def test_unknown_extension(self):
        r = self.det.detect_by_extension("data.xyz")
        self.assertIsNone(r)

    def test_no_extension(self):
        r = self.det.detect_by_extension("Makefile")
        self.assertIsNone(r)

    def test_shell(self):
        r = self.det.detect_by_extension("run.sh")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "shell")

    def test_case_insensitive(self):
        r = self.det.detect_by_extension("Main.PY")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "python")


class TestDetectByShebang(unittest.TestCase):
    def setUp(self):
        self.det = LanguageDetector()

    def test_python_shebang(self):
        r = self.det.detect_by_shebang("#!/usr/bin/python3\nimport sys")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "python")
        self.assertEqual(r.method, "shebang")

    def test_env_python(self):
        r = self.det.detect_by_shebang("#!/usr/bin/env python3\nprint('hi')")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "python")

    def test_node_shebang(self):
        r = self.det.detect_by_shebang("#!/usr/bin/env node\nconsole.log('hi')")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "javascript")

    def test_bash_shebang(self):
        r = self.det.detect_by_shebang("#!/bin/bash\necho hello")
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "shell")

    def test_no_shebang(self):
        r = self.det.detect_by_shebang("import os\nprint('hi')")
        self.assertIsNone(r)

    def test_empty(self):
        r = self.det.detect_by_shebang("")
        self.assertIsNone(r)


class TestDetectByContent(unittest.TestCase):
    def setUp(self):
        self.det = LanguageDetector()

    def test_python_keywords(self):
        code = "def main():\n    import os\n    class Foo:\n        self.x = 1"
        r = self.det.detect_by_content(code)
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "python")
        self.assertEqual(r.method, "content")

    def test_javascript_keywords(self):
        code = "const x = 1;\nfunction run() {}\nlet y = require('fs')"
        r = self.det.detect_by_content(code)
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "javascript")

    def test_go_keywords(self):
        code = 'package main\nimport (\n    "fmt"\n)\nfunc main() {\n    fmt.Println("hi")\n}'
        r = self.det.detect_by_content(code)
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "go")

    def test_rust_keywords(self):
        code = "fn main() {\n    let mut x = 5;\n    pub fn helper() {}\n}"
        r = self.det.detect_by_content(code)
        self.assertIsNotNone(r)
        self.assertEqual(r.language, "rust")

    def test_empty_content(self):
        r = self.det.detect_by_content("")
        self.assertIsNone(r)

    def test_whitespace_only(self):
        r = self.det.detect_by_content("   \n\n  ")
        self.assertIsNone(r)

    def test_confidence_capped(self):
        code = "def a():\ndef b():\ndef c():\nimport x\nimport y\nclass Z:\nself.a\nelif True:"
        r = self.det.detect_by_content(code)
        self.assertIsNotNone(r)
        self.assertLessEqual(r.confidence, 0.85)


class TestDetectCombined(unittest.TestCase):
    def setUp(self):
        self.det = LanguageDetector()

    def test_extension_wins_over_content(self):
        r = self.det.detect("main.py", "function foo() {}")
        self.assertEqual(r.language, "python")
        self.assertAlmostEqual(r.confidence, 0.9)

    def test_content_only(self):
        r = self.det.detect("unknown", "def main():\n    import os")
        self.assertEqual(r.language, "python")

    def test_no_info(self):
        r = self.det.detect("unknown")
        self.assertEqual(r.language, "unknown")
        self.assertAlmostEqual(r.confidence, 0.0)
        self.assertEqual(r.method, "none")

    def test_shebang_plus_extension(self):
        r = self.det.detect("script.py", "#!/usr/bin/env python3\nimport sys")
        self.assertEqual(r.language, "python")
        self.assertGreaterEqual(r.confidence, 0.8)


class TestSupportedLanguages(unittest.TestCase):
    def test_returns_sorted(self):
        det = LanguageDetector()
        langs = det.supported_languages()
        self.assertEqual(langs, sorted(langs))

    def test_includes_common(self):
        det = LanguageDetector()
        langs = det.supported_languages()
        for lang in ("python", "javascript", "go", "rust", "java", "c"):
            self.assertIn(lang, langs)

    def test_no_duplicates(self):
        det = LanguageDetector()
        langs = det.supported_languages()
        self.assertEqual(len(langs), len(set(langs)))


if __name__ == "__main__":
    unittest.main()
