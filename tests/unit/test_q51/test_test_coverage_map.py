"""Tests for TestCoverageMapper — Task 349."""

from __future__ import annotations

import pytest

from lidco.analysis.test_coverage_map import (
    CoverageMap, TestCoverageMapper, SourceMapping, _infer_source,
)


TEST_SOURCE = """\
from mymodule import MyClass, my_func

class TestMyClass:
    def test_init(self):
        obj = MyClass()
        assert obj is not None

    def test_method(self):
        result = my_func(1, 2)
        assert result == 3

def test_standalone():
    pass
"""

SYNTAX_ERROR_SOURCE = "def broken(:"


class TestInferSource:
    def test_test_prefix_stripped(self):
        assert _infer_source("test_session.py") == "session.py"

    def test_no_prefix(self):
        # No test_ prefix, just return stem + .py
        assert _infer_source("utils.py") == "utils.py"

    def test_deep_path(self):
        result = _infer_source("tests/unit/test_auth.py")
        assert result == "auth.py"


class TestSourceMapping:
    def test_frozen(self):
        m = SourceMapping(
            test_file="test_x.py",
            source_file="x.py",
            test_functions=("test_a",),
            covered_symbols=("foo",),
        )
        with pytest.raises((AttributeError, TypeError)):
            m.test_file = "other.py"  # type: ignore[misc]


class TestCoverageMapClass:
    def test_find_tests_for(self):
        m = SourceMapping("test_foo.py", "foo.py", ("test_a",), ("Foo",))
        cmap = CoverageMap(mappings=[m])
        result = cmap.find_tests_for("foo.py")
        assert len(result) == 1

    def test_find_tests_for_missing(self):
        cmap = CoverageMap()
        assert cmap.find_tests_for("ghost.py") == []

    def test_untested_sources(self):
        m = SourceMapping("test_foo.py", "foo.py", (), ())
        cmap = CoverageMap(mappings=[m])
        untested = cmap.untested_sources({"foo.py", "bar.py", "baz.py"})
        assert "bar.py" in untested
        assert "baz.py" in untested
        assert "foo.py" not in untested

    def test_untested_all_covered(self):
        m = SourceMapping("test_foo.py", "foo.py", (), ())
        cmap = CoverageMap(mappings=[m])
        assert cmap.untested_sources({"foo.py"}) == set()


class TestTestCoverageMapper:
    def setup_method(self):
        self.mapper = TestCoverageMapper()

    def test_empty_sources(self):
        cmap = self.mapper.build({})
        assert len(cmap.mappings) == 0

    def test_builds_mapping(self):
        cmap = self.mapper.build({"tests/test_mymodule.py": TEST_SOURCE})
        assert len(cmap.mappings) == 1

    def test_infers_source_file(self):
        cmap = self.mapper.build({"tests/test_mymodule.py": TEST_SOURCE})
        assert cmap.mappings[0].source_file == "mymodule.py"

    def test_extracts_test_functions(self):
        cmap = self.mapper.build({"test_mymodule.py": TEST_SOURCE})
        fns = cmap.mappings[0].test_functions
        assert "test_init" in fns
        assert "test_method" in fns
        assert "test_standalone" in fns

    def test_extracts_covered_symbols(self):
        cmap = self.mapper.build({"test_mymodule.py": TEST_SOURCE})
        symbols = set(cmap.mappings[0].covered_symbols)
        assert "MyClass" in symbols or "my_func" in symbols

    def test_syntax_error_handled(self):
        cmap = self.mapper.build({"test_bad.py": SYNTAX_ERROR_SOURCE})
        assert len(cmap.mappings) == 1
        # No test functions extracted
        assert cmap.mappings[0].test_functions == ()

    def test_multiple_test_files(self):
        sources = {
            "test_a.py": "def test_foo(): pass\n",
            "test_b.py": "def test_bar(): pass\n",
        }
        cmap = self.mapper.build(sources)
        assert len(cmap.mappings) == 2
