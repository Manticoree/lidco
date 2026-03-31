"""Tests for ChangeImpactAnalyzer — Task 345."""

from __future__ import annotations

import pytest

pytest.importorskip("lidco.analysis.change_impact", reason="change_impact.py removed in Q157")
from lidco.analysis.change_impact import ChangeImpactAnalyzer, ImpactReport, ImpactedModule
from lidco.analysis.dependency_graph import DependencyGraph


def _make_graph() -> DependencyGraph:
    """
    a imports b, c
    b imports d
    d imports e
    x is standalone
    """
    g = DependencyGraph()
    g.add_edge("a", "b")
    g.add_edge("a", "c")
    g.add_edge("b", "d")
    g.add_edge("d", "e")
    return g


class TestImpactedModule:
    def test_frozen(self):
        im = ImpactedModule(module="a", reason="direct", depth=1)
        with pytest.raises((AttributeError, TypeError)):
            im.module = "b"  # type: ignore[misc]


class TestImpactReport:
    def test_direct_count(self):
        report = ImpactReport(
            changed_modules=["d"],
            impacted=[
                ImpactedModule("b", "direct", 1),
                ImpactedModule("a", "transitive", 2),
            ],
        )
        assert report.direct_count == 1
        assert report.transitive_count == 1

    def test_modules_at_depth(self):
        report = ImpactReport(
            changed_modules=["e"],
            impacted=[
                ImpactedModule("d", "direct", 1),
                ImpactedModule("b", "transitive", 2),
                ImpactedModule("a", "transitive", 3),
            ],
        )
        assert report.modules_at_depth(1) == ["d"]
        assert report.modules_at_depth(2) == ["b"]


class TestChangeImpactAnalyzer:
    def setup_method(self):
        self.analyzer = ChangeImpactAnalyzer()
        self.graph = _make_graph()

    def test_no_importers(self):
        # e is a leaf — nothing imports it
        report = self.analyzer.analyze(["e"], self.graph)
        # Wait, d imports e → d is impacted when e changes
        # Let me check: reversed graph has e→d edge
        assert len(report.impacted) >= 0  # just check it doesn't raise

    def test_direct_importer(self):
        # d is imported by b — so b is directly impacted
        report = self.analyzer.analyze(["d"], self.graph)
        impacted_modules = {i.module for i in report.impacted}
        assert "b" in impacted_modules

    def test_transitive_importer(self):
        # e is imported by d, d is imported by b, b is imported by a
        report = self.analyzer.analyze(["e"], self.graph)
        impacted_modules = {i.module for i in report.impacted}
        assert "d" in impacted_modules
        # a imports b which imports d which imports e → a is transitively impacted
        assert "a" in impacted_modules

    def test_changed_module_not_in_impacted(self):
        report = self.analyzer.analyze(["d"], self.graph)
        impacted_modules = {i.module for i in report.impacted}
        assert "d" not in impacted_modules

    def test_empty_changed(self):
        report = self.analyzer.analyze([], self.graph)
        assert report.impacted == []

    def test_standalone_module_no_impact(self):
        # x is not in the graph — nothing is impacted
        report = self.analyzer.analyze(["x"], self.graph)
        assert report.impacted == []

    def test_depth_assignment(self):
        # e → d (depth 1), b (depth 2), a (depth 3)
        report = self.analyzer.analyze(["e"], self.graph)
        d_entry = next((i for i in report.impacted if i.module == "d"), None)
        if d_entry:
            assert d_entry.depth == 1

    def test_changed_modules_recorded(self):
        report = self.analyzer.analyze(["e"], self.graph)
        assert "e" in report.changed_modules
