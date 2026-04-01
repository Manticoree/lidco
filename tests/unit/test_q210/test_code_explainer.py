"""Tests for lidco.pairing.code_explainer."""

from __future__ import annotations

import unittest

from lidco.pairing.code_explainer import (
    CodeExplanation,
    CodeExplainer,
    DetailLevel,
)


class TestDetailLevel(unittest.TestCase):
    def test_values(self) -> None:
        assert DetailLevel.BRIEF == "brief"
        assert DetailLevel.DETAILED == "detailed"
        assert DetailLevel.ELI5 == "eli5"


class TestCodeExplanation(unittest.TestCase):
    def test_frozen(self) -> None:
        e = CodeExplanation(code="x", level=DetailLevel.BRIEF, summary="s")
        with self.assertRaises(AttributeError):
            e.summary = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        e = CodeExplanation(code="x", level=DetailLevel.BRIEF, summary="s")
        assert e.line_annotations == ()
        assert e.complexity_note == ""


class TestCodeExplainer(unittest.TestCase):
    def setUp(self) -> None:
        self.explainer = CodeExplainer()

    def test_explain_brief(self) -> None:
        code = "x = 1\ny = 2"
        result = self.explainer.explain(code, DetailLevel.BRIEF)
        assert result.level == DetailLevel.BRIEF
        assert "2 line(s)" in result.summary

    def test_explain_detailed(self) -> None:
        code = "def foo():\n    return 1"
        result = self.explainer.explain(code, DetailLevel.DETAILED)
        assert result.level == DetailLevel.DETAILED
        assert "function definition" in result.summary

    def test_explain_eli5(self) -> None:
        code = "for i in range(10):\n    print(i)"
        result = self.explainer.explain(code, DetailLevel.ELI5)
        assert result.level == DetailLevel.ELI5
        assert "repeat" in result.summary.lower() or "loop" in result.summary.lower()

    def test_explain_empty(self) -> None:
        result = self.explainer.explain("", DetailLevel.BRIEF)
        assert "Empty" in result.summary

    def test_explain_function(self) -> None:
        code = "def greet(name, greeting='hi'):\n    return f'{greeting} {name}'"
        result = self.explainer.explain_function(code)
        assert "greet" in result.summary
        assert "name" in result.summary
        assert "returns" in result.summary

    def test_annotate_lines(self) -> None:
        code = "import os\nx = 1\n# comment"
        annotations = self.explainer.annotate_lines(code)
        assert len(annotations) == 3
        assert annotations[0] == (1, "module import")
        assert annotations[2][1] == "comment or blank"

    def test_complexity_constant(self) -> None:
        code = "x = 1\ny = 2"
        result = self.explainer.complexity_estimate(code)
        assert "O(1)" in result

    def test_complexity_linear(self) -> None:
        code = "for i in range(n):\n    print(i)"
        result = self.explainer.complexity_estimate(code)
        assert "O(n)" in result


if __name__ == "__main__":
    unittest.main()
