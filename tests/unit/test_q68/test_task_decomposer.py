"""Tests for Task 461: TaskDecomposer — design.md → tasks.md."""
import json
import pytest
from pathlib import Path
from lidco.spec.design_doc import Component, DesignDocument
from lidco.spec.task_decomposer import SpecTask, TaskDecomposer


def _design():
    return DesignDocument(
        components=[
            Component("Store", "Persist data", "src/store.py"),
            Component("API", "Expose endpoints", "src/api.py"),
        ],
        data_models=["Item: id: str, value: str"],
        api_contracts=["save(item: Item) -> None"],
        implementation_notes="Follow repo pattern.",
    )


class TestSpecTask:
    def test_checkbox_unchecked(self):
        t = SpecTask("T1", "Write tests", "unit tests first")
        line = t.to_checkbox_line()
        assert "[ ] T1" in line
        assert "Write tests" in line

    def test_checkbox_checked(self):
        t = SpecTask("T2", "Deploy", "to production", done=True)
        assert "[x]" in t.to_checkbox_line()

    def test_depends_on_in_line(self):
        t = SpecTask("T2", "Impl", "impl", depends_on=["T1"])
        line = t.to_checkbox_line()
        assert "depends: T1" in line

    def test_to_markdown_block_includes_files(self):
        t = SpecTask("T1", "Title", "desc", target_files=["src/a.py"])
        block = t.to_markdown_block()
        assert "src/a.py" in block


class TestTaskDecomposerOffline:
    def test_decompose_returns_tasks(self, tmp_path):
        td = TaskDecomposer()
        tasks = td.decompose(_design(), tmp_path)
        assert len(tasks) >= 1
        assert all(isinstance(t, SpecTask) for t in tasks)

    def test_decompose_saves_tasks_md(self, tmp_path):
        td = TaskDecomposer()
        td.decompose(_design(), tmp_path)
        assert (tmp_path / ".lidco" / "spec" / "tasks.md").exists()

    def test_decompose_creates_dirs(self, tmp_path):
        td = TaskDecomposer()
        td.decompose(_design(), tmp_path)
        assert (tmp_path / ".lidco" / "spec").is_dir()

    def test_load_returns_empty_when_absent(self, tmp_path):
        td = TaskDecomposer()
        assert td.load(tmp_path) == []

    def test_load_roundtrip(self, tmp_path):
        td = TaskDecomposer()
        original = td.decompose(_design(), tmp_path)
        loaded = td.load(tmp_path)
        assert len(loaded) == len(original)
        assert loaded[0].id == original[0].id

    def test_mark_done_toggles_task(self, tmp_path):
        td = TaskDecomposer()
        tasks = td.decompose(_design(), tmp_path)
        first_id = tasks[0].id
        result = td.mark_done(first_id, tmp_path)
        assert result is True
        reloaded = td.load(tmp_path)
        first = next(t for t in reloaded if t.id == first_id)
        assert first.done is True

    def test_mark_done_nonexistent_returns_false(self, tmp_path):
        td = TaskDecomposer()
        td.decompose(_design(), tmp_path)
        assert td.mark_done("T999", tmp_path) is False

    def test_topological_order_respected(self, tmp_path):
        td = TaskDecomposer()
        tasks = td.decompose(_design(), tmp_path)
        # offline generates tasks with sequential deps — T2 must come after T1
        ids = [t.id for t in tasks]
        for t in tasks:
            for dep in t.depends_on:
                assert ids.index(dep) < ids.index(t.id)

    def test_decompose_with_llm_client(self, tmp_path):
        payload = json.dumps({
            "tasks": [
                {
                    "id": "T1",
                    "title": "Init DB",
                    "description": "Create tables",
                    "target_files": ["src/db.py"],
                    "depends_on": [],
                    "done": False,
                },
                {
                    "id": "T2",
                    "title": "Add API",
                    "description": "REST endpoints",
                    "target_files": ["src/api.py"],
                    "depends_on": ["T1"],
                    "done": False,
                },
            ]
        })

        def fake_llm(messages):
            return payload

        td = TaskDecomposer(llm_client=fake_llm)
        tasks = td.decompose(_design(), tmp_path)
        assert tasks[0].id == "T1"
        assert tasks[1].depends_on == ["T1"]

    def test_t0_deps_stripped(self, tmp_path):
        payload = json.dumps({
            "tasks": [
                {
                    "id": "T1",
                    "title": "First",
                    "description": "desc",
                    "target_files": [],
                    "depends_on": ["T0"],
                    "done": False,
                }
            ]
        })

        def fake_llm(messages):
            return payload

        td = TaskDecomposer(llm_client=fake_llm)
        tasks = td.decompose(_design(), tmp_path)
        assert tasks[0].depends_on == []
