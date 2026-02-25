"""Tests for TestGapTool and its helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.tools.test_gap import (
    TestGapTool,
    _collect_test_names,
    _collect_source_symbols,
    _is_covered,
)


# ---------------------------------------------------------------------------
# Helper: _collect_test_names
# ---------------------------------------------------------------------------

class TestCollectTestNames:
    def test_finds_test_functions(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_foo.py").write_text("def test_my_func():\n    pass\n")
        names = _collect_test_names(tmp_path)
        assert "test_my_func" in names

    def test_finds_test_classes(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_bar.py").write_text("class TestMyClass:\n    pass\n")
        names = _collect_test_names(tmp_path)
        assert "testmyclass" in names

    def test_finds_async_test_functions(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_async.py").write_text("async def test_async_op():\n    pass\n")
        names = _collect_test_names(tmp_path)
        assert "test_async_op" in names

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert _collect_test_names(tmp_path) == set()

    def test_names_are_lowercase(self, tmp_path: Path) -> None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_x.py").write_text("def test_FooBar():\n    pass\n")
        names = _collect_test_names(tmp_path)
        assert "test_foobar" in names


# ---------------------------------------------------------------------------
# Helper: _is_covered
# ---------------------------------------------------------------------------

class TestIsCovered:
    def test_direct_match(self) -> None:
        assert _is_covered("my_func", {"test_my_func"}) is True

    def test_camel_case_to_snake(self) -> None:
        assert _is_covered("MyClass", {"test_my_class"}) is True

    def test_test_class_match(self) -> None:
        assert _is_covered("MyClass", {"testmyclass"}) is True

    def test_partial_containment(self) -> None:
        assert _is_covered("session", {"testmysession"}) is True

    def test_no_match(self) -> None:
        assert _is_covered("orphan_func", {"test_other", "test_another"}) is False

    def test_dunder_not_checked(self) -> None:
        # Dunders are filtered before calling _is_covered
        # so just verify it works with normal names
        assert _is_covered("__init__", set()) is False


# ---------------------------------------------------------------------------
# Helper: _collect_source_symbols
# ---------------------------------------------------------------------------

class TestCollectSourceSymbols:
    def test_finds_functions(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "foo.py").write_text(
            "def my_func():\n    x = 1\n    y = 2\n    return x + y\n"
        )
        syms = _collect_source_symbols(src, "", "function", 3)
        names = [s["name"] for s in syms]
        assert "my_func" in names

    def test_finds_classes(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "bar.py").write_text(
            "class MyClass:\n    def __init__(self):\n        self.x = 1\n    def go(self):\n        pass\n"
        )
        syms = _collect_source_symbols(src, "", "class", 2)
        names = [s["name"] for s in syms]
        assert "MyClass" in names

    def test_skips_dunder_methods(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text(
            "def __init__(self):\n    self.x = 1\n    y = 2\n    z = 3\n"
        )
        syms = _collect_source_symbols(src, "", "function", 1)
        names = [s["name"] for s in syms]
        assert "__init__" not in names

    def test_min_lines_filter(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text("def tiny():\n    pass\n\ndef big():\n    x=1\n    y=2\n    z=3\n    return z\n")
        syms = _collect_source_symbols(src, "", "function", 3)
        names = [s["name"] for s in syms]
        assert "tiny" not in names
        assert "big" in names

    def test_path_prefix_filter(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "sub").mkdir(parents=True)
        (src / "sub" / "a.py").write_text(
            "def sub_func():\n    x=1\n    y=2\n    z=3\n    return z\n"
        )
        (src / "other.py").write_text(
            "def other_func():\n    x=1\n    y=2\n    z=3\n    return z\n"
        )
        syms = _collect_source_symbols(src, "sub", "function", 1)
        names = [s["name"] for s in syms]
        assert "sub_func" in names
        assert "other_func" not in names


# ---------------------------------------------------------------------------
# TestGapTool._run()
# ---------------------------------------------------------------------------

class TestTestGapTool:
    def setup_method(self) -> None:
        self.tool = TestGapTool()

    def test_name(self) -> None:
        assert self.tool.name == "find_test_gaps"

    def test_has_three_parameters(self) -> None:
        names = {p.name for p in self.tool.parameters}
        assert names == {"path_prefix", "kind", "min_lines"}

    @pytest.mark.asyncio
    async def test_invalid_kind_returns_error(self) -> None:
        result = await self.tool._run(kind="method")
        assert result.success is False
        assert "kind" in result.error.lower()

    @pytest.mark.asyncio
    async def test_finds_gap_in_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "service.py").write_text(
            "def orphan_func():\n    x=1\n    y=2\n    return x+y\n"
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_service.py").write_text("def test_other():\n    pass\n")

        result = await self.tool._run(min_lines=1)
        assert result.success is True
        assert "orphan_func" in result.output
        assert result.metadata["gaps"] >= 1

    @pytest.mark.asyncio
    async def test_detects_covered_symbol(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "calc.py").write_text(
            "def add(x, y):\n    return x + y\n\ndef multiply(x, y):\n    return x * y\n"
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_calc.py").write_text(
            "def test_add():\n    pass\ndef test_multiply():\n    pass\n"
        )

        result = await self.tool._run(min_lines=1)
        assert result.success is True
        assert result.metadata["covered"] >= 2

    @pytest.mark.asyncio
    async def test_empty_project_returns_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = await self.tool._run()
        assert result.success is True
