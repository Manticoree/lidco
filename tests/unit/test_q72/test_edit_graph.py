"""Tests for EditGraph — T485."""
from __future__ import annotations
from pathlib import Path
import pytest
from lidco.prediction.edit_graph import EditGraph, EditSite


class TestEditGraph:
    def test_build_from_empty_dir(self, tmp_path):
        g = EditGraph.build(tmp_path)
        assert g.symbols() == []

    def test_build_finds_functions(self, tmp_path):
        (tmp_path / "a.py").write_text("def my_function():\n    pass\n")
        g = EditGraph.build(tmp_path)
        assert "my_function" in g.symbols()

    def test_build_finds_classes(self, tmp_path):
        (tmp_path / "a.py").write_text("class MyClass:\n    pass\n")
        g = EditGraph.build(tmp_path)
        assert "MyClass" in g.symbols()

    def test_related_sites_call_site(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo():\n    pass\n")
        (tmp_path / "b.py").write_text("from a import foo\nfoo()\n")
        g = EditGraph.build(tmp_path)
        sites = g.related_sites("foo")
        assert any(s.relationship in ("call_site", "implementation") for s in sites)

    def test_related_sites_excludes_own_file(self, tmp_path):
        (tmp_path / "a.py").write_text("def bar():\n    pass\nbar()\n")
        g = EditGraph.build(tmp_path)
        sites = g.related_sites("bar", file_path="a.py")
        assert all(s.file_path != "a.py" for s in sites)

    def test_edit_site_dataclass(self):
        s = EditSite(file_path="x.py", line=5, relationship="call_site", symbol="foo")
        assert s.file_path == "x.py"
        assert s.relationship == "call_site"

    def test_type_usage_detected(self, tmp_path):
        (tmp_path / "a.py").write_text("def func(x: MyType) -> MyType:\n    pass\n")
        g = EditGraph.build(tmp_path)
        # MyType should be detected as type_usage
        sites = g.related_sites("MyType")
        assert len(sites) > 0

    def test_test_file_relationship(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_foo.py").write_text("def test_bar():\n    pass\n")
        g = EditGraph.build(tmp_path)
        sites = g.related_sites("test_bar")
        assert any(s.relationship == "test" for s in sites)

    def test_related_unknown_symbol(self, tmp_path):
        g = EditGraph.build(tmp_path)
        assert g.related_sites("nonexistent") == []
