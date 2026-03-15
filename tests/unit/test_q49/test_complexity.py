"""Tests for ComplexityAnalyzer — Task 337."""

from __future__ import annotations

import pytest

from lidco.analysis.complexity import ComplexityAnalyzer, FunctionComplexity


SIMPLE_FN = """\
def add(a, b):
    return a + b
"""

BRANCHY_FN = """\
def classify(x):
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
    else:
        return "zero"
"""

LOOP_FN = """\
def find(items, target):
    for item in items:
        if item == target:
            return True
    return False
"""

COMPLEX_FN = """\
def process(data):
    result = []
    for item in data:
        if item > 0:
            for sub in item:
                if sub:
                    while sub > 0:
                        sub -= 1
            result.append(item)
    return result
"""

BOOL_OP_FN = """\
def check(a, b, c):
    return a and b and c
"""

SYNTAX_ERROR_SRC = "def broken(:"


class TestFunctionComplexity:
    def test_frozen(self):
        fc = FunctionComplexity(name="f", file="x.py", line=1, cyclomatic=1, cognitive=0)
        with pytest.raises((AttributeError, TypeError)):
            fc.cyclomatic = 5  # type: ignore[misc]


class TestAnalyzeSource:
    def setup_method(self):
        self.ca = ComplexityAnalyzer()

    def test_simple_fn_cyclomatic_1(self):
        results = self.ca.analyze_source(SIMPLE_FN)
        assert len(results) == 1
        assert results[0].cyclomatic == 1
        assert results[0].name == "add"

    def test_branchy_fn_cyclomatic(self):
        results = self.ca.analyze_source(BRANCHY_FN)
        assert results[0].cyclomatic >= 3  # if + elif + implicit else

    def test_loop_fn_cyclomatic(self):
        results = self.ca.analyze_source(LOOP_FN)
        fc = results[0]
        # 1 base + 1 for + 1 if = 3
        assert fc.cyclomatic == 3

    def test_bool_op_counts_operators(self):
        # a and b and c → BoolOp with 3 values → 2 operators
        results = self.ca.analyze_source(BOOL_OP_FN)
        fc = results[0]
        assert fc.cyclomatic >= 3  # 1 base + 2 bool ops

    def test_syntax_error_returns_empty(self):
        results = self.ca.analyze_source(SYNTAX_ERROR_SRC)
        assert results == []

    def test_empty_source_returns_empty(self):
        results = self.ca.analyze_source("")
        assert results == []

    def test_file_path_recorded(self):
        results = self.ca.analyze_source(SIMPLE_FN, file_path="my.py")
        assert results[0].file == "my.py"

    def test_line_number_recorded(self):
        results = self.ca.analyze_source(SIMPLE_FN)
        assert results[0].line == 1

    def test_multiple_functions(self):
        src = SIMPLE_FN + "\n" + BRANCHY_FN
        results = self.ca.analyze_source(src)
        names = {r.name for r in results}
        assert "add" in names
        assert "classify" in names

    def test_cognitive_simple_fn(self):
        results = self.ca.analyze_source(SIMPLE_FN)
        assert results[0].cognitive == 0  # no branches

    def test_cognitive_higher_for_nesting(self):
        results_loop = self.ca.analyze_source(LOOP_FN)
        results_simple = self.ca.analyze_source(SIMPLE_FN)
        assert results_loop[0].cognitive > results_simple[0].cognitive


class TestScoreRisk:
    def setup_method(self):
        self.ca = ComplexityAnalyzer()

    def _fc(self, cyclomatic: int) -> FunctionComplexity:
        return FunctionComplexity("f", "", 1, cyclomatic=cyclomatic, cognitive=0)

    def test_low(self):
        assert self.ca.score_risk(self._fc(1)) == "low"
        assert self.ca.score_risk(self._fc(4)) == "low"

    def test_medium_boundary(self):
        assert self.ca.score_risk(self._fc(5)) == "medium"
        assert self.ca.score_risk(self._fc(9)) == "medium"

    def test_high_boundary(self):
        assert self.ca.score_risk(self._fc(10)) == "high"
        assert self.ca.score_risk(self._fc(20)) == "high"
