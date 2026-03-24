"""Tests for AgentMemoryScope (T520)."""
from pathlib import Path

import pytest

from lidco.memory.agent_scope import AgentMemoryScope


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path / "project"


@pytest.fixture
def global_dir(tmp_path):
    return tmp_path / "global"


@pytest.fixture
def scope(project_dir, global_dir):
    return AgentMemoryScope("my-agent", project_dir=project_dir, global_dir=global_dir)


def _project_mem_path(project_dir, name):
    return project_dir / ".lidco" / "agent-memory" / name / "MEMORY.md"


def _global_mem_path(global_dir, name):
    return global_dir / ".lidco" / "agent-memory" / name / "MEMORY.md"


# ---- load ----

def test_load_returns_empty_when_no_files(scope):
    assert scope.load() == ""


def test_load_reads_project_scope(scope, project_dir):
    path = _project_mem_path(project_dir, "my-agent")
    path.parent.mkdir(parents=True)
    path.write_text("project memory", encoding="utf-8")
    assert scope.load() == "project memory"


def test_load_falls_back_to_global(scope, global_dir):
    path = _global_mem_path(global_dir, "my-agent")
    path.parent.mkdir(parents=True)
    path.write_text("global memory", encoding="utf-8")
    assert scope.load() == "global memory"


def test_load_project_overrides_global(scope, project_dir, global_dir):
    _project_mem_path(project_dir, "my-agent").parent.mkdir(parents=True)
    _project_mem_path(project_dir, "my-agent").write_text("project", encoding="utf-8")
    _global_mem_path(global_dir, "my-agent").parent.mkdir(parents=True)
    _global_mem_path(global_dir, "my-agent").write_text("global", encoding="utf-8")
    assert scope.load() == "project"


def test_load_trims_to_200_lines(scope, project_dir):
    path = _project_mem_path(project_dir, "my-agent")
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(f"line {i}" for i in range(250)), encoding="utf-8")
    content = scope.load()
    assert len(content.splitlines()) == 200


# ---- save ----

def test_save_writes_to_project_scope(scope, project_dir):
    scope.save("hello world")
    path = _project_mem_path(project_dir, "my-agent")
    assert path.exists()
    assert path.read_text() == "hello world"


def test_save_use_global_writes_to_global(scope, global_dir):
    scope.save("global content", use_global=True)
    path = _global_mem_path(global_dir, "my-agent")
    assert path.exists()
    assert path.read_text() == "global content"


def test_save_no_project_dir_writes_to_global(global_dir):
    scope = AgentMemoryScope("agent", project_dir=None, global_dir=global_dir)
    scope.save("no project")
    path = _global_mem_path(global_dir, "agent")
    assert path.exists()


# ---- append ----

def test_append_adds_timestamped_entry(scope):
    scope.append("did something")
    content = scope.load()
    assert "did something" in content
    assert "T" in content  # ISO timestamp


def test_append_multiple_entries(scope):
    scope.append("entry 1")
    scope.append("entry 2")
    content = scope.load()
    assert "entry 1" in content
    assert "entry 2" in content


def test_append_trims_oldest_over_200_lines(scope):
    for i in range(205):
        scope.save("\n".join(f"line {j}" for j in range(199)))
        break  # pre-fill with 199 lines
    for _ in range(5):
        scope.append("new entry")
    content = scope.load()
    assert len(content.splitlines()) <= 200


# ---- clear ----

def test_clear_removes_file(scope, project_dir):
    scope.save("data")
    scope.clear()
    assert scope.load() == ""


def test_clear_no_file_no_error(scope):
    scope.clear()  # should not raise
