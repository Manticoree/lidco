"""Execute agents as a directed acyclic graph."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeStatus(str, Enum):
    """Status of a DAG node."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class DAGNode:
    """A single node in the agent DAG."""

    id: str
    agent_name: str
    prompt: str = ""
    depends_on: tuple[str, ...] = ()
    status: NodeStatus = NodeStatus.PENDING
    result: str = ""


@dataclass(frozen=True)
class DAGRunResult:
    """Snapshot of a DAG execution."""

    nodes: tuple[DAGNode, ...] = ()
    completed: int = 0
    failed: int = 0
    duration: float = 0.0


class AgentDAGRunner:
    """Build and execute an agent DAG."""

    def __init__(self) -> None:
        self._nodes: dict[str, DAGNode] = {}

    def add_node(
        self,
        id: str,
        agent_name: str,
        prompt: str = "",
        depends_on: tuple[str, ...] = (),
    ) -> DAGNode:
        """Add a node to the DAG and return it."""
        node = DAGNode(
            id=id,
            agent_name=agent_name,
            prompt=prompt,
            depends_on=depends_on,
        )
        self._nodes = {**self._nodes, id: node}
        return node

    def topological_sort(self) -> list[str]:
        """Return node IDs in execution order; raise ValueError on cycle."""
        in_degree: dict[str, int] = {nid: 0 for nid in self._nodes}
        for node in self._nodes.values():
            for dep in node.depends_on:
                if dep in in_degree:
                    in_degree = {
                        **in_degree,
                        node.id: in_degree[node.id] + 1,
                    }

        queue: list[str] = [nid for nid, deg in in_degree.items() if deg == 0]
        result: list[str] = []

        while queue:
            current = queue[0]
            queue = queue[1:]
            result = [*result, current]
            for node in self._nodes.values():
                if current in node.depends_on:
                    new_deg = in_degree[node.id] - 1
                    in_degree = {**in_degree, node.id: new_deg}
                    if new_deg == 0:
                        queue = [*queue, node.id]

        if len(result) != len(self._nodes):
            raise ValueError("Cycle detected in DAG")
        return result

    def get_ready_nodes(self) -> list[DAGNode]:
        """Return nodes whose dependencies are all COMPLETED."""
        ready: list[DAGNode] = []
        for node in self._nodes.values():
            if node.status != NodeStatus.PENDING:
                continue
            all_done = all(
                self._nodes[dep].status == NodeStatus.COMPLETED
                for dep in node.depends_on
                if dep in self._nodes
            )
            if all_done:
                ready = [*ready, node]
        return ready

    def mark_completed(self, node_id: str, result: str = "") -> DAGNode:
        """Mark a node as COMPLETED and return the new node."""
        old = self._nodes[node_id]
        new_node = DAGNode(
            id=old.id,
            agent_name=old.agent_name,
            prompt=old.prompt,
            depends_on=old.depends_on,
            status=NodeStatus.COMPLETED,
            result=result,
        )
        self._nodes = {**self._nodes, node_id: new_node}
        return new_node

    def mark_failed(self, node_id: str, error: str = "") -> DAGNode:
        """Mark a node as FAILED and return the new node."""
        old = self._nodes[node_id]
        new_node = DAGNode(
            id=old.id,
            agent_name=old.agent_name,
            prompt=old.prompt,
            depends_on=old.depends_on,
            status=NodeStatus.FAILED,
            result=error,
        )
        self._nodes = {**self._nodes, node_id: new_node}
        return new_node

    def get_result(self) -> DAGRunResult:
        """Return a snapshot of all nodes."""
        nodes = tuple(self._nodes.values())
        completed = sum(1 for n in nodes if n.status == NodeStatus.COMPLETED)
        failed = sum(1 for n in nodes if n.status == NodeStatus.FAILED)
        return DAGRunResult(nodes=nodes, completed=completed, failed=failed)

    def validate(self) -> list[str]:
        """Return list of error messages (missing deps, cycles, etc.)."""
        errors: list[str] = []
        for node in self._nodes.values():
            for dep in node.depends_on:
                if dep not in self._nodes:
                    errors = [*errors, f"Node '{node.id}' depends on unknown '{dep}'"]
        try:
            self.topological_sort()
        except ValueError:
            errors = [*errors, "Cycle detected in DAG"]
        return errors

    def summary(self) -> str:
        """Human-readable summary."""
        res = self.get_result()
        total = len(res.nodes)
        return (
            f"DAG: {total} nodes, "
            f"{res.completed} completed, {res.failed} failed"
        )
