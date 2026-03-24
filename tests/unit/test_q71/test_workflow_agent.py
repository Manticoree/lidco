"""Tests for WorkflowAgent — T479."""
from __future__ import annotations
import pytest
from lidco.agents.workflow_agent import WorkflowAgent, WorkflowRegistry, WorkflowRun, WorkflowStatus


class TestWorkflowAgent:
    def test_run_executes_tasks(self):
        agent = WorkflowAgent(name="w1", schedule="manual", tasks=["a", "b"])
        run = agent.run()
        assert run.status == WorkflowStatus.DONE
        assert run.finished_at is not None

    def test_run_with_executor(self):
        agent = WorkflowAgent(name="w1", schedule="manual", tasks=["task1"])
        results = []
        def executor(task):
            results.append(task)
            return f"done:{task}"
        run = agent.run(executor=executor)
        assert "task1" in results
        assert run.status == WorkflowStatus.DONE

    def test_run_failure(self):
        agent = WorkflowAgent(name="w1", schedule="manual", tasks=["fail"])
        def fail_exec(task):
            raise RuntimeError("boom")
        run = agent.run(executor=fail_exec)
        assert run.status == WorkflowStatus.FAILED

    def test_status_idle_after_success(self):
        agent = WorkflowAgent(name="w1", schedule="manual", tasks=["t"])
        agent.run()
        assert agent.status == WorkflowStatus.IDLE

    def test_last_run_stored(self):
        agent = WorkflowAgent(name="w1", schedule="manual", tasks=["t"])
        run = agent.run()
        assert agent.last_run is run

    def test_run_output_concatenated(self):
        agent = WorkflowAgent(name="w1", schedule="manual", tasks=["a", "b"])
        def exec_fn(task):
            return f"result_{task}"
        run = agent.run(executor=exec_fn)
        assert "result_a" in run.output
        assert "result_b" in run.output


class TestWorkflowRegistry:
    def test_add_and_get(self):
        reg = WorkflowRegistry()
        agent = WorkflowAgent(name="w1", schedule="daily", tasks=[])
        reg.add(agent)
        assert reg.get("w1") is agent

    def test_list(self):
        reg = WorkflowRegistry()
        reg.add(WorkflowAgent(name="a", schedule="manual", tasks=[]))
        reg.add(WorkflowAgent(name="b", schedule="manual", tasks=[]))
        assert len(reg.list()) == 2

    def test_remove(self):
        reg = WorkflowRegistry()
        reg.add(WorkflowAgent(name="x", schedule="manual", tasks=[]))
        assert reg.remove("x")
        assert reg.get("x") is None

    def test_remove_missing(self):
        reg = WorkflowRegistry()
        assert not reg.remove("nope")
