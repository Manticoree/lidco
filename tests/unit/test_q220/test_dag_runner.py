"""Tests for lidco.agents.dag_runner."""
from __future__ import annotations

import pytest

from lidco.agents.dag_runner import (
    AgentDAGRunner,
    DAGNode,
    DAGRunResult,
    NodeStatus,
)


class TestNodeStatus:
    def test_enum_values(self) -> None:
        assert NodeStatus.PENDING == "pending"
        assert NodeStatus.RUNNING == "running"
        assert NodeStatus.COMPLETED == "completed"
        assert NodeStatus.FAILED == "failed"
        assert NodeStatus.CANCELLED == "cancelled"


class TestDAGNode:
    def test_frozen(self) -> None:
        node = DAGNode(id="a", agent_name="planner")
        with pytest.raises(AttributeError):
            node.id = "b"  # type: ignore[misc]

    def test_defaults(self) -> None:
        node = DAGNode(id="a", agent_name="planner")
        assert node.prompt == ""
        assert node.depends_on == ()
        assert node.status == NodeStatus.PENDING
        assert node.result == ""


class TestAgentDAGRunner:
    def test_add_node(self) -> None:
        runner = AgentDAGRunner()
        node = runner.add_node(id="a", agent_name="planner", prompt="plan it")
        assert node.id == "a"
        assert node.agent_name == "planner"
        assert node.prompt == "plan it"

    def test_topological_sort_linear(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first")
        runner.add_node(id="b", agent_name="second", depends_on=("a",))
        runner.add_node(id="c", agent_name="third", depends_on=("b",))
        order = runner.topological_sort()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_topological_sort_parallel(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first")
        runner.add_node(id="b", agent_name="second")
        runner.add_node(id="c", agent_name="third", depends_on=("a", "b"))
        order = runner.topological_sort()
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("c")

    def test_topological_sort_cycle(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first", depends_on=("b",))
        runner.add_node(id="b", agent_name="second", depends_on=("a",))
        with pytest.raises(ValueError, match="Cycle"):
            runner.topological_sort()

    def test_get_ready_nodes_initial(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first")
        runner.add_node(id="b", agent_name="second", depends_on=("a",))
        ready = runner.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == "a"

    def test_get_ready_nodes_after_completion(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first")
        runner.add_node(id="b", agent_name="second", depends_on=("a",))
        runner.mark_completed("a", result="done")
        ready = runner.get_ready_nodes()
        assert len(ready) == 1
        assert ready[0].id == "b"

    def test_mark_completed(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first")
        node = runner.mark_completed("a", result="ok")
        assert node.status == NodeStatus.COMPLETED
        assert node.result == "ok"

    def test_mark_failed(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first")
        node = runner.mark_failed("a", error="boom")
        assert node.status == NodeStatus.FAILED
        assert node.result == "boom"

    def test_get_result(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first")
        runner.add_node(id="b", agent_name="second")
        runner.mark_completed("a")
        runner.mark_failed("b", error="err")
        res = runner.get_result()
        assert res.completed == 1
        assert res.failed == 1
        assert len(res.nodes) == 2

    def test_validate_missing_dep(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first", depends_on=("missing",))
        errors = runner.validate()
        assert any("missing" in e for e in errors)

    def test_validate_clean(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first")
        runner.add_node(id="b", agent_name="second", depends_on=("a",))
        errors = runner.validate()
        assert errors == []

    def test_summary(self) -> None:
        runner = AgentDAGRunner()
        runner.add_node(id="a", agent_name="first")
        s = runner.summary()
        assert "1 nodes" in s
