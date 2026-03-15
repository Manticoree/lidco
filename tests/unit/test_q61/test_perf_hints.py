"""Tests for PerformanceAnalyzer — Task 415."""

from __future__ import annotations

import pytest

from lidco.proactive.perf_hints import PerfHint, PerformanceAnalyzer


STRING_CONCAT_IN_LOOP = """\
result = ""
for item in items:
    result += item
"""

LEN_EQ_ZERO = """\
if len(x) == 0:
    pass
"""

LEN_NEQ_ZERO = """\
if len(x) != 0:
    pass
"""

SORTED_MULTIPLE_TIMES = """\
def process(data):
    first = sorted(data)[0]
    last = sorted(data)[-1]
    return first, last
"""

APPEND_IN_LOOP = """\
result = []
for item in items:
    result.append(item * 2)
"""

NESTED_LOOP_SUBSCRIPT = """\
for i in range(n):
    for j in range(m):
        val = matrix[i][j]
"""

CLEAN_CODE = """\
def clean(items):
    return [x * 2 for x in items]
"""

SYNTAX_ERROR = "def bad(:"


class TestPerfHint:

    def test_fields(self) -> None:
        h = PerfHint(file="f.py", line=1, kind="len_eq_zero",
                     message="Use not x", suggestion="Replace len check")
        assert h.file == "f.py"
        assert h.kind == "len_eq_zero"

    def test_frozen(self) -> None:
        h = PerfHint(file="f.py", line=1, kind="k", message="m", suggestion="s")
        with pytest.raises((AttributeError, TypeError)):
            h.kind = "other"  # type: ignore[misc]


class TestPerformanceAnalyzer:

    def setup_method(self) -> None:
        self.analyzer = PerformanceAnalyzer()

    def test_string_concat_in_loop(self) -> None:
        hints = self.analyzer.analyze(STRING_CONCAT_IN_LOOP, "f.py")
        kinds = [h.kind for h in hints]
        assert "string_concat_in_loop" in kinds

    def test_len_eq_zero(self) -> None:
        hints = self.analyzer.analyze(LEN_EQ_ZERO, "f.py")
        kinds = [h.kind for h in hints]
        assert "len_eq_zero" in kinds

    def test_len_neq_zero(self) -> None:
        hints = self.analyzer.analyze(LEN_NEQ_ZERO, "f.py")
        kinds = [h.kind for h in hints]
        assert "len_eq_zero" in kinds

    def test_sorted_multiple_times(self) -> None:
        hints = self.analyzer.analyze(SORTED_MULTIPLE_TIMES, "f.py")
        kinds = [h.kind for h in hints]
        assert "sorted_multiple_times" in kinds

    def test_append_in_loop(self) -> None:
        hints = self.analyzer.analyze(APPEND_IN_LOOP, "f.py")
        kinds = [h.kind for h in hints]
        assert "append_in_loop" in kinds

    def test_nested_loop_subscript(self) -> None:
        hints = self.analyzer.analyze(NESTED_LOOP_SUBSCRIPT, "f.py")
        kinds = [h.kind for h in hints]
        assert "nested_loop_list_access" in kinds

    def test_clean_code_no_hints(self) -> None:
        hints = self.analyzer.analyze(CLEAN_CODE, "f.py")
        assert hints == []

    def test_syntax_error_returns_empty(self) -> None:
        hints = self.analyzer.analyze(SYNTAX_ERROR, "f.py")
        assert hints == []

    def test_hint_has_suggestion(self) -> None:
        hints = self.analyzer.analyze(STRING_CONCAT_IN_LOOP, "f.py")
        for h in hints:
            assert h.suggestion

    def test_hint_has_file_and_line(self) -> None:
        hints = self.analyzer.analyze(LEN_EQ_ZERO, "myfile.py")
        assert len(hints) >= 1
        assert hints[0].file == "myfile.py"
        assert hints[0].line >= 1

    def test_analyze_missing_file(self) -> None:
        hints = self.analyzer.analyze_file("/nonexistent/path.py")
        assert hints == []

    def test_analyze_file_reads_and_analyzes(self, tmp_path) -> None:
        f = tmp_path / "code.py"
        f.write_text(STRING_CONCAT_IN_LOOP)
        hints = self.analyzer.analyze_file(str(f))
        assert len(hints) >= 1
