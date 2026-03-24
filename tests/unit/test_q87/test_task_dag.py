"""Tests for TaskDAG (T569)."""
from __future__ import annotations
import asyncio
from pathlib import Path
import pytest
from lidco.tasks.task_dag import TaskDAG, DAGTask, DAGResult


async def _ok(task: DAGTask) -> str:
    return f"{task.id}:done"


async def _fail(task: DAGTask) -> str:
    raise ValueError(f"{task.id} failed")


def test_add_task():
    dag = TaskDAG()
    dag.add("t1", "Task 1")
    assert dag.get_task("t1") is not None


def test_topo_order_respects_deps():
    dag = TaskDAG()
    dag.add("t1", "First")
    dag.add("t2", "Second", depends_on=["t1"])
    order = dag._topo_order()
    assert order.index("t1") < order.index("t2")


def test_run_all_pass():
    dag = TaskDAG()
    dag.add("a", "A")
    dag.add("b", "B", depends_on=["a"])
    result = asyncio.run(dag.run(_ok))
    assert result.completed == 2
    assert result.failed == 0
    assert result.success


def test_run_failure_skips_dependents():
    dag = TaskDAG()
    dag.add("a", "A")
    dag.add("b", "B", depends_on=["a"])
    result = asyncio.run(dag.run(_fail))
    assert result.failed == 1
    assert result.skipped == 1


def test_format_plan():
    dag = TaskDAG()
    dag.add("t1", "Setup")
    dag.add("t2", "Test", depends_on=["t1"])
    plan = dag.format_plan()
    assert "Setup" in plan
    assert "Test" in plan


def test_checkpoint_save_load(tmp_path):
    cp = str(tmp_path / "cp.json")
    dag = TaskDAG(checkpoint_path=cp)
    dag.add("t1", "T1")
    asyncio.run(dag.run(_ok))
    assert Path(cp).exists()
    dag2 = TaskDAG(checkpoint_path=cp)
    dag2.add("t1", "T1")
    loaded = dag2.load_checkpoint()
    assert loaded
    assert dag2.get_task("t1").status == "done"


def test_resume_skips_done(tmp_path):
    cp = str(tmp_path / "cp.json")
    dag = TaskDAG(checkpoint_path=cp)
    dag.add("t1", "T1")
    asyncio.run(dag.run(_ok))
    ran = []

    async def track(task):
        ran.append(task.id)
        return "ok"

    dag2 = TaskDAG(checkpoint_path=cp)
    dag2.add("t1", "T1")
    asyncio.run(dag2.run(track, resume=True))
    assert "t1" not in ran  # already done, skipped


def test_dag_result_format():
    r = DAGResult(completed=3, failed=1, skipped=1, total=5)
    s = r.format_summary()
    assert "3/5" in s
