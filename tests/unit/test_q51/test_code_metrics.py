"""Tests for CodeMetricsCollector — Task 351."""

from __future__ import annotations

import pytest

from lidco.analysis.code_metrics import CodeMetricsCollector, FileMetrics, ProjectMetrics


SIMPLE_SOURCE = """\
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

class Calculator:
    pass
"""

COMMENT_HEAVY = """\
# This is a comment
# Another comment
x = 1
# Third comment
y = 2
"""

BLANK_HEAVY = """\
def foo():
    pass


def bar():


    return 1
"""

LONG_FN = "def long_fn():\n" + "    x = 1\n" * 30 + "    return x\n"

EMPTY_SOURCE = ""
SYNTAX_ERROR = "def broken(:"


class TestFileMetrics:
    def test_frozen(self):
        m = FileMetrics(
            file="x.py", loc=10, blank_lines=2, comment_lines=1,
            total_lines=13, functions=2, classes=0,
            avg_function_length=5.0, max_function_length=7,
        )
        with pytest.raises((AttributeError, TypeError)):
            m.loc = 99  # type: ignore[misc]


class TestCodeMetricsCollector:
    def setup_method(self):
        self.collector = CodeMetricsCollector()

    def test_empty_source(self):
        m = self.collector.analyze_source(EMPTY_SOURCE)
        assert m.loc == 0
        assert m.total_lines == 0

    def test_syntax_error(self):
        m = self.collector.analyze_source(SYNTAX_ERROR)
        assert isinstance(m, FileMetrics)

    def test_counts_functions(self):
        m = self.collector.analyze_source(SIMPLE_SOURCE)
        assert m.functions == 2

    def test_counts_classes(self):
        m = self.collector.analyze_source(SIMPLE_SOURCE)
        assert m.classes == 1

    def test_blank_lines_counted(self):
        m = self.collector.analyze_source(BLANK_HEAVY)
        assert m.blank_lines >= 2

    def test_comment_lines_counted(self):
        m = self.collector.analyze_source(COMMENT_HEAVY)
        assert m.comment_lines == 3

    def test_loc_excludes_blank_and_comments(self):
        m = self.collector.analyze_source(COMMENT_HEAVY)
        # 5 total - 3 comments = 2 loc (x=1 and y=2)
        assert m.loc == 2

    def test_avg_function_length(self):
        m = self.collector.analyze_source(SIMPLE_SOURCE)
        assert m.avg_function_length > 0

    def test_max_function_length(self):
        m = self.collector.analyze_source(LONG_FN)
        assert m.max_function_length >= 30

    def test_file_path_recorded(self):
        m = self.collector.analyze_source(SIMPLE_SOURCE, file_path="my.py")
        assert m.file == "my.py"

    def test_total_lines_correct(self):
        m = self.collector.analyze_source(COMMENT_HEAVY)
        assert m.total_lines == 5


class TestProjectMetrics:
    def setup_method(self):
        self.collector = CodeMetricsCollector()

    def test_empty_project(self):
        pm = self.collector.analyze_project({})
        assert pm.total_files == 0
        assert pm.total_loc == 0

    def test_single_file(self):
        pm = self.collector.analyze_project({"a.py": SIMPLE_SOURCE})
        assert pm.total_files == 1

    def test_total_loc_summed(self):
        sources = {"a.py": SIMPLE_SOURCE, "b.py": SIMPLE_SOURCE}
        pm = self.collector.analyze_project(sources)
        single = self.collector.analyze_source(SIMPLE_SOURCE)
        assert pm.total_loc == single.loc * 2

    def test_total_functions_summed(self):
        sources = {"a.py": SIMPLE_SOURCE, "b.py": SIMPLE_SOURCE}
        pm = self.collector.analyze_project(sources)
        assert pm.total_functions == 4  # 2 per file

    def test_total_classes_summed(self):
        sources = {"a.py": SIMPLE_SOURCE, "b.py": SIMPLE_SOURCE}
        pm = self.collector.analyze_project(sources)
        assert pm.total_classes == 2

    def test_avg_file_loc(self):
        sources = {"a.py": SIMPLE_SOURCE, "b.py": SIMPLE_SOURCE}
        pm = self.collector.analyze_project(sources)
        single = self.collector.analyze_source(SIMPLE_SOURCE)
        assert pm.avg_file_loc == pytest.approx(single.loc)

    def test_largest_files(self):
        sources = {"big.py": LONG_FN, "small.py": "x = 1\n"}
        pm = self.collector.analyze_project(sources)
        largest = pm.largest_files(1)
        assert largest[0].file == "big.py"

    def test_most_complex_files(self):
        sources = {"complex.py": SIMPLE_SOURCE, "simple.py": "x = 1\n"}
        pm = self.collector.analyze_project(sources)
        most_complex = pm.most_complex_files(1)
        assert most_complex[0].file == "complex.py"
