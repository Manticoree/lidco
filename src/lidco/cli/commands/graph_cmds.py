"""CLI commands for graph intelligence and semantic search (Q87)."""
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lidco.cli.commands.registry import CommandRegistry


def register_graph_commands(registry: "CommandRegistry") -> None:
    """Register /graph, /search, /task-dag, /approve-rules commands."""

    async def graph_handler(args: str) -> str:
        parts = args.strip().split(None, 1)
        sub = parts[0] if parts else "stats"
        rest = parts[1] if len(parts) > 1 else ""
        try:
            from lidco.graph.dependency_graph import DependencyGraph
            g = DependencyGraph()
            g.build_from_directory(".")
            if sub == "stats":
                return g.format_stats()
            elif sub == "deps" and rest:
                edges = g.edges_from(rest)
                if not edges:
                    return f"No outgoing edges from '{rest}'"
                return "\n".join(f"  {e.src} --[{e.kind}]--> {e.dst}  ({Path(e.file).name}:{e.line})" for e in edges[:20])
            elif sub == "callers" and rest:
                callers = g.dependents(rest, kind="calls")
                return f"Callers of '{rest}': {', '.join(sorted(callers)[:15]) or 'none'}"
            elif sub == "reach" and rest:
                reachable = g.reachable(rest)
                return f"Reachable from '{rest}': {', '.join(sorted(reachable)[:15]) or 'none'}"
            return "Usage: /graph [stats|deps <sym>|callers <sym>|reach <sym>]"
        except Exception as e:
            return f"/graph failed: {e}"

    async def search_handler(args: str) -> str:
        query = args.strip()
        if not query:
            return "Usage: /search <query>"
        try:
            from lidco.search.semantic_search import SemanticSearch
            ss = SemanticSearch()
            count = ss.index_directory(".")
            if count == 0:
                return "No Python files found to index."
            return ss.search_code(query, top_k=8)
        except Exception as e:
            return f"/search failed: {e}"

    async def task_dag_handler(args: str) -> str:
        parts = args.strip().split(None, 1)
        sub = parts[0] if parts else "demo"
        try:
            from lidco.tasks.task_dag import TaskDAG, DAGTask
            dag = TaskDAG(name="demo")
            dag.add("t1", "Setup", "Install dependencies")
            dag.add("t2", "Tests", "Run test suite", depends_on=["t1"])
            dag.add("t3", "Lint", "Run linter", depends_on=["t1"])
            dag.add("t4", "Deploy", "Deploy to staging", depends_on=["t2", "t3"])
            if sub == "plan":
                return dag.format_plan()
            elif sub == "run":
                import asyncio

                async def _noop(task):
                    return f"{task.name} done"

                result = await dag.run(_noop)
                return result.format_summary() + "\n" + dag.format_plan()
            return dag.format_plan()
        except Exception as e:
            return f"/task-dag failed: {e}"

    async def approve_rules_handler(args: str) -> str:
        parts = args.strip().split(None, 1)
        sub = parts[0] if parts else "list"
        diff_text = parts[1] if len(parts) > 1 else ""
        try:
            from lidco.review.approval_engine import ApprovalEngine
            engine = ApprovalEngine()
            engine.load_defaults()
            if sub == "list":
                return "\n".join(f"  {r.name}: {r.description}" for r in engine._rules)
            elif sub == "check" and diff_text:
                decisions = engine.evaluate_all(diff_text)
                lines = []
                for d in decisions:
                    lines.append(d.format())
                overall = "AUTO-APPROVE" if engine.is_auto_approvable(diff_text) else "NEEDS REVIEW"
                lines.append(f"\nVerdict: {overall}")
                return "\n".join(lines)
            return "Usage: /approve-rules [list|check <diff_text>]"
        except Exception as e:
            return f"/approve-rules failed: {e}"

    from lidco.cli.commands.registry import SlashCommand
    registry.register(SlashCommand("graph", "Query the codebase dependency graph", graph_handler))
    registry.register(SlashCommand("search", "Semantic TF-IDF code search", search_handler))
    registry.register(SlashCommand("task-dag", "Long-horizon task DAG with checkpoints", task_dag_handler))
    registry.register(SlashCommand("approve-rules", "Auto-approve rules engine for PRs", approve_rules_handler))
