"""Tests for lidco.tasks.output — TaskOutputManager."""
from __future__ import annotations

import json

from lidco.tasks.output import OutputLine, TaskOutputManager


class TestTaskOutputManager:
    def test_append_and_get_output(self):
        mgr = TaskOutputManager()
        mgr.append("t1", "hello")
        mgr.append("t1", "world")
        lines = mgr.get_output("t1")
        assert len(lines) == 2
        assert lines[0].content == "hello"
        assert lines[1].content == "world"

    def test_get_output_last_n(self):
        mgr = TaskOutputManager()
        for i in range(10):
            mgr.append("t1", f"line {i}")
        lines = mgr.get_output("t1", last_n=3)
        assert len(lines) == 3
        assert lines[0].content == "line 7"

    def test_tail(self):
        mgr = TaskOutputManager()
        for i in range(50):
            mgr.append("t1", f"line {i}")
        tail = mgr.tail("t1", n=5)
        assert len(tail) == 5
        assert tail[0].content == "line 45"

    def test_search(self):
        mgr = TaskOutputManager()
        mgr.append("t1", "error: something broke")
        mgr.append("t1", "info: all good")
        mgr.append("t1", "error: another one")
        results = mgr.search("t1", "error")
        assert len(results) == 2

    def test_export_text(self):
        mgr = TaskOutputManager()
        mgr.append("t1", "line1")
        mgr.append("t1", "line2")
        text = mgr.export("t1", format="text")
        assert text == "line1\nline2"

    def test_export_json(self):
        mgr = TaskOutputManager()
        mgr.append("t1", "hello")
        raw = mgr.export("t1", format="json")
        data = json.loads(raw)
        assert len(data) == 1
        assert data[0]["content"] == "hello"
        assert data[0]["task_id"] == "t1"

    def test_clear(self):
        mgr = TaskOutputManager()
        mgr.append("t1", "a")
        mgr.append("t1", "b")
        removed = mgr.clear("t1")
        assert removed == 2
        assert mgr.line_count("t1") == 0

    def test_line_count(self):
        mgr = TaskOutputManager()
        assert mgr.line_count("t1") == 0
        mgr.append("t1", "x")
        assert mgr.line_count("t1") == 1

    def test_stream_attribute(self):
        mgr = TaskOutputManager()
        mgr.append("t1", "err", stream="stderr")
        lines = mgr.get_output("t1")
        assert lines[0].stream == "stderr"

    def test_max_lines_eviction(self):
        mgr = TaskOutputManager(max_lines=5)
        for i in range(10):
            mgr.append("t1", f"line {i}")
        assert mgr.line_count("t1") == 5
        lines = mgr.get_output("t1")
        assert lines[0].content == "line 5"

    def test_get_output_empty(self):
        mgr = TaskOutputManager()
        assert mgr.get_output("nonexist") == []
