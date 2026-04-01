"""Tests for lidco.tasks.dependencies — DependencyResolver."""
from __future__ import annotations

import pytest

from lidco.tasks.dependencies import CyclicDependencyError, DependencyResolver, TaskNode


class TestDependencyResolver:
    def test_empty_resolver(self):
        resolver = DependencyResolver()
        assert resolver.resolve() == []
        assert resolver.topological_sort() == []
        assert resolver.has_cycle() is False

    def test_single_node(self):
        resolver = DependencyResolver()
        resolver.add_node(TaskNode(id="a"))
        layers = resolver.resolve()
        assert layers == [["a"]]

    def test_linear_chain(self):
        resolver = DependencyResolver()
        resolver.add_node(TaskNode(id="a"))
        resolver.add_node(TaskNode(id="b", depends_on=("a",)))
        resolver.add_node(TaskNode(id="c", depends_on=("b",)))
        layers = resolver.resolve()
        assert len(layers) == 3
        assert layers[0] == ["a"]
        assert layers[1] == ["b"]
        assert layers[2] == ["c"]

    def test_parallel_nodes(self):
        resolver = DependencyResolver()
        resolver.add_node(TaskNode(id="a"))
        resolver.add_node(TaskNode(id="b"))
        resolver.add_node(TaskNode(id="c", depends_on=("a", "b")))
        layers = resolver.resolve()
        assert len(layers) == 2
        assert sorted(layers[0]) == ["a", "b"]
        assert layers[1] == ["c"]

    def test_topological_sort(self):
        resolver = DependencyResolver()
        resolver.add_node(TaskNode(id="a"))
        resolver.add_node(TaskNode(id="b", depends_on=("a",)))
        resolver.add_node(TaskNode(id="c", depends_on=("a",)))
        result = resolver.topological_sort()
        assert result[0] == "a"
        assert set(result) == {"a", "b", "c"}

    def test_cycle_detection(self):
        resolver = DependencyResolver()
        resolver.add_node(TaskNode(id="a", depends_on=("b",)))
        resolver.add_node(TaskNode(id="b", depends_on=("a",)))
        assert resolver.has_cycle() is True

    def test_cycle_raises_on_resolve(self):
        resolver = DependencyResolver()
        resolver.add_node(TaskNode(id="a", depends_on=("b",)))
        resolver.add_node(TaskNode(id="b", depends_on=("a",)))
        with pytest.raises(CyclicDependencyError):
            resolver.resolve()

    def test_cycle_raises_on_topological_sort(self):
        resolver = DependencyResolver()
        resolver.add_node(TaskNode(id="x", depends_on=("y",)))
        resolver.add_node(TaskNode(id="y", depends_on=("x",)))
        with pytest.raises(CyclicDependencyError):
            resolver.topological_sort()

    def test_get_ready(self):
        resolver = DependencyResolver()
        resolver.add_node(TaskNode(id="a"))
        resolver.add_node(TaskNode(id="b", depends_on=("a",)))
        resolver.add_node(TaskNode(id="c"))
        ready = resolver.get_ready(completed=set())
        assert sorted(ready) == ["a", "c"]
        ready2 = resolver.get_ready(completed={"a"})
        assert sorted(ready2) == ["b", "c"]

    def test_get_ready_excludes_completed(self):
        resolver = DependencyResolver()
        resolver.add_node(TaskNode(id="a"))
        ready = resolver.get_ready(completed={"a"})
        assert ready == []
