"""Tests for ArchitectSession (T518)."""
import json

import pytest

from lidco.llm.architect_mode import (
    ArchitectPlan,
    ArchitectSession,
    EditResult,
    FileChangeSpec,
)


def _architect_fn_json(task: str) -> str:
    return json.dumps({
        "rationale": "do the thing",
        "file_changes": [
            {"file": "foo.py", "action": "modify", "description": "add docstring"},
            {"file": "bar.py", "action": "create", "description": "new module"},
        ],
    })


def _architect_fn_plain(task: str) -> str:
    return "Just modify foo.py to add logging"


def _editor_fn(file: str, description: str) -> str:
    return f"# edited: {description}"


def _editor_fn_raises(file: str, description: str) -> str:
    raise RuntimeError("editor failed")


# ---- plan ----

def test_plan_parses_json_response():
    session = ArchitectSession(architect_fn=_architect_fn_json)
    plan = session.plan("do something")
    assert isinstance(plan, ArchitectPlan)
    assert len(plan.file_changes) == 2
    assert plan.rationale == "do the thing"


def test_plan_fallback_on_plain_text():
    session = ArchitectSession(architect_fn=_architect_fn_plain)
    plan = session.plan("task")
    assert len(plan.file_changes) == 1
    assert plan.file_changes[0].action == "modify"
    assert "logging" in plan.file_changes[0].description


def test_plan_fallback_on_invalid_json():
    def bad_fn(task):
        return "{ broken json !!"

    session = ArchitectSession(architect_fn=bad_fn)
    plan = session.plan("task")
    assert len(plan.file_changes) == 1


def test_plan_file_change_spec_fields():
    session = ArchitectSession(architect_fn=_architect_fn_json)
    plan = session.plan("x")
    spec = plan.file_changes[0]
    assert isinstance(spec, FileChangeSpec)
    assert spec.file == "foo.py"
    assert spec.action == "modify"


# ---- execute ----

def test_execute_calls_editor_fn():
    session = ArchitectSession(architect_fn=_architect_fn_json, editor_fn=_editor_fn)
    plan = session.plan("x")
    results = session.execute(plan)
    assert len(results) == 2
    assert all(r.success for r in results)
    assert "edited" in results[0].content


def test_execute_no_editor_fn_returns_stub():
    session = ArchitectSession(architect_fn=_architect_fn_json, editor_fn=None)
    plan = session.plan("x")
    results = session.execute(plan)
    assert all(r.success for r in results)
    assert "[stub:" in results[0].content


def test_execute_handles_editor_exception():
    session = ArchitectSession(
        architect_fn=_architect_fn_json, editor_fn=_editor_fn_raises
    )
    plan = session.plan("x")
    results = session.execute(plan)
    assert all(not r.success for r in results)
    assert "editor failed" in results[0].error


def test_edit_result_fields():
    r = EditResult(file="x.py", success=True, content="abc", error="")
    assert r.file == "x.py"
    assert r.success is True


# ---- run ----

def test_run_returns_results_end_to_end():
    session = ArchitectSession(
        architect_fn=_architect_fn_json, editor_fn=_editor_fn
    )
    results = session.run("do something")
    assert len(results) == 2
    assert all(isinstance(r, EditResult) for r in results)


def test_run_empty_file_changes():
    def no_changes(task):
        return json.dumps({"rationale": "nothing to do", "file_changes": []})

    session = ArchitectSession(architect_fn=no_changes, editor_fn=_editor_fn)
    results = session.run("x")
    assert results == []
