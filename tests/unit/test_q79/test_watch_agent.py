"""Tests for WatchAgentTrigger (T517)."""
from pathlib import Path

import pytest

from lidco.watch.agent_trigger import AIComment, WatchAgentTrigger


@pytest.fixture
def trigger(tmp_path):
    return WatchAgentTrigger(project_dir=tmp_path)


@pytest.fixture
def trigger_with_fn(tmp_path):
    answers = []

    def agent_fn(task):
        answers.append(task)
        return "agent answer"

    t = WatchAgentTrigger(project_dir=tmp_path, agent_fn=agent_fn)
    t._answers = answers
    return t


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---- scan_file ----

def test_scan_file_finds_execute_comment(tmp_path, trigger):
    f = _write(tmp_path / "foo.py", "x = 1\n# AI! add docstring\ny = 2\n")
    comments = trigger.scan_file(f)
    assert len(comments) == 1
    assert comments[0].mode == "execute"
    assert comments[0].instruction == "add docstring"
    assert comments[0].line_number == 2


def test_scan_file_finds_ask_comment(tmp_path, trigger):
    f = _write(tmp_path / "bar.py", "# AI? what does this do\npass\n")
    comments = trigger.scan_file(f)
    assert len(comments) == 1
    assert comments[0].mode == "ask"


def test_scan_file_cpp_style(tmp_path, trigger):
    f = _write(tmp_path / "foo.js", "const x = 1; // AI! refactor\n")
    comments = trigger.scan_file(f)
    assert len(comments) == 1
    assert comments[0].mode == "execute"


def test_scan_file_sql_style(tmp_path, trigger):
    f = _write(tmp_path / "foo.sql", "SELECT 1; -- AI! optimize\n")
    comments = trigger.scan_file(f)
    assert len(comments) == 1


def test_scan_file_no_comments(tmp_path, trigger):
    f = _write(tmp_path / "clean.py", "x = 1\ny = 2\n")
    assert trigger.scan_file(f) == []


def test_scan_file_missing_file(tmp_path, trigger):
    assert trigger.scan_file(tmp_path / "nonexistent.py") == []


def test_scan_file_multiple_comments(tmp_path, trigger):
    f = _write(tmp_path / "multi.py", "# AI! do A\npass\n# AI? explain B\n")
    comments = trigger.scan_file(f)
    assert len(comments) == 2


# ---- collect_all_comments ----

def test_collect_all_comments_aggregates(tmp_path, trigger):
    f1 = _write(tmp_path / "a.py", "# AI! fix\n")
    f2 = _write(tmp_path / "b.py", "# AI? explain\n")
    all_comments = trigger.collect_all_comments([f1, f2])
    assert len(all_comments) == 2


# ---- lifecycle ----

def test_start_stop(trigger):
    assert not trigger.running
    trigger.start()
    assert trigger.running
    trigger.stop()
    assert not trigger.running


# ---- process ----

def test_process_returns_agent_answer(tmp_path, trigger_with_fn):
    f = _write(tmp_path / "x.py", "# AI! do something\npass\n")
    result = trigger_with_fn.process([f])
    assert result == "agent answer"


def test_process_removes_execute_comments(tmp_path, trigger_with_fn):
    f = _write(tmp_path / "x.py", "# AI! do something\npass\n")
    trigger_with_fn.process([f])
    content = f.read_text()
    assert "# AI!" not in content
    assert "pass" in content


def test_process_appends_answer_for_ask(tmp_path, trigger_with_fn):
    f = _write(tmp_path / "x.py", "# AI? what is x\npass\n")
    trigger_with_fn.process([f])
    content = f.read_text()
    assert "AI Answer" in content


def test_process_no_comments_returns_empty(tmp_path, trigger_with_fn):
    f = _write(tmp_path / "x.py", "# just a comment\npass\n")
    result = trigger_with_fn.process([f])
    assert result == ""


def test_process_no_agent_fn(tmp_path):
    t = WatchAgentTrigger(project_dir=tmp_path, agent_fn=None)
    f = _write(tmp_path / "x.py", "# AI! do something\n")
    result = t.process([f])
    assert result == ""
