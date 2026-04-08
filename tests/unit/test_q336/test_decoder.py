"""Tests for lidco.archaeology.decoder — LegacyDecoder."""

from __future__ import annotations

import unittest

from lidco.archaeology.decoder import CodePattern, DecoderResult, LegacyDecoder


class TestCodePattern(unittest.TestCase):
    def test_label_info(self) -> None:
        p = CodePattern(name="todo-comment", description="d", line_range=(1, 1), severity="info")
        self.assertEqual(p.label(), "[INFO] todo-comment")

    def test_label_critical(self) -> None:
        p = CodePattern(name="dynamic-exec", description="d", line_range=(5, 5), severity="critical")
        self.assertEqual(p.label(), "[CRITICAL] dynamic-exec")

    def test_frozen(self) -> None:
        p = CodePattern(name="x", description="d", line_range=(1, 1))
        with self.assertRaises(AttributeError):
            p.name = "y"  # type: ignore[misc]


class TestDecoderResult(unittest.TestCase):
    def test_pattern_count(self) -> None:
        r = DecoderResult(
            source_name="test",
            patterns=(
                CodePattern(name="a", description="d", line_range=(1, 1)),
                CodePattern(name="b", description="d", line_range=(2, 2)),
            ),
            historical_context="ctx",
            original_requirements="req",
            total_lines=10,
        )
        self.assertEqual(r.pattern_count, 2)

    def test_summary_contains_name(self) -> None:
        r = DecoderResult(
            source_name="legacy.py",
            patterns=(),
            historical_context="old code",
            original_requirements="must handle X",
            total_lines=5,
        )
        s = r.summary()
        self.assertIn("legacy.py", s)
        self.assertIn("old code", s)


class TestLegacyDecoder(unittest.TestCase):
    def test_detector_count_default(self) -> None:
        d = LegacyDecoder()
        self.assertGreater(d.detector_count, 0)

    def test_extra_patterns(self) -> None:
        extra = [(r"custom_thing", "custom", "desc", "fix it")]
        d = LegacyDecoder(extra_patterns=extra)
        self.assertEqual(d.detector_count, LegacyDecoder().detector_count + 1)

    def test_decode_empty_source(self) -> None:
        d = LegacyDecoder()
        result = d.decode("", name="empty.py")
        self.assertEqual(result.pattern_count, 0)
        self.assertEqual(result.total_lines, 0)  # empty string has no lines

    def test_decode_hack_comment(self) -> None:
        source = "x = 1\n# HACK: workaround for bug\ny = 2"
        d = LegacyDecoder()
        result = d.decode(source, name="hack.py")
        names = [p.name for p in result.patterns]
        self.assertIn("hack-comment", names)

    def test_decode_todo_comment(self) -> None:
        source = "# TODO: fix this later\npass"
        d = LegacyDecoder()
        result = d.decode(source)
        names = [p.name for p in result.patterns]
        self.assertIn("todo-comment", names)

    def test_decode_dynamic_exec(self) -> None:
        source = "result = eval(user_input)"
        d = LegacyDecoder()
        result = d.decode(source)
        names = [p.name for p in result.patterns]
        self.assertIn("dynamic-exec", names)
        severities = [p.severity for p in result.patterns if p.name == "dynamic-exec"]
        self.assertEqual(severities[0], "critical")

    def test_decode_bare_except(self) -> None:
        source = "try:\n    x()\nexcept:\n    pass"
        d = LegacyDecoder()
        result = d.decode(source)
        names = [p.name for p in result.patterns]
        self.assertIn("bare-except", names)

    def test_decode_star_import(self) -> None:
        source = "from os import *"
        d = LegacyDecoder()
        result = d.decode(source)
        names = [p.name for p in result.patterns]
        self.assertIn("star-import", names)

    def test_decode_global_variable(self) -> None:
        source = "def f():\n    global counter\n    counter += 1"
        d = LegacyDecoder()
        result = d.decode(source)
        names = [p.name for p in result.patterns]
        self.assertIn("global-variable", names)

    def test_decode_deprecated(self) -> None:
        source = "# deprecated: use new_func instead"
        d = LegacyDecoder()
        result = d.decode(source)
        names = [p.name for p in result.patterns]
        self.assertIn("deprecated-marker", names)

    def test_explain_known_pattern(self) -> None:
        d = LegacyDecoder()
        explanation = d.explain_pattern("bare-except")
        self.assertIn("bare-except", explanation)
        self.assertIn("Suggestion", explanation)

    def test_explain_unknown_pattern(self) -> None:
        d = LegacyDecoder()
        explanation = d.explain_pattern("nonexistent")
        self.assertIn("Unknown pattern", explanation)

    def test_infer_requirements_with_docstring(self) -> None:
        source = '"""This module handles user authentication."""\nimport os'
        d = LegacyDecoder()
        result = d.decode(source, name="auth.py")
        self.assertIn("authentication", result.original_requirements)

    def test_infer_requirements_no_docstring(self) -> None:
        source = "import os\nx = 1"
        d = LegacyDecoder()
        result = d.decode(source, name="no_doc.py")
        self.assertIn("No module-level docstring", result.original_requirements)

    def test_infer_context_no_comments(self) -> None:
        source = "x = 1\ny = 2"
        d = LegacyDecoder()
        result = d.decode(source)
        self.assertIn("No inline documentation", result.historical_context)

    def test_infer_context_with_comments(self) -> None:
        source = "# first comment\n# second comment\nx = 1"
        d = LegacyDecoder()
        result = d.decode(source)
        self.assertIn("2 comment(s)", result.historical_context)

    def test_severity_mapping(self) -> None:
        self.assertEqual(LegacyDecoder._severity_for("dynamic-exec"), "critical")
        self.assertEqual(LegacyDecoder._severity_for("bare-except"), "critical")
        self.assertEqual(LegacyDecoder._severity_for("global-variable"), "warning")
        self.assertEqual(LegacyDecoder._severity_for("star-import"), "warning")
        self.assertEqual(LegacyDecoder._severity_for("todo-comment"), "info")


if __name__ == "__main__":
    unittest.main()
