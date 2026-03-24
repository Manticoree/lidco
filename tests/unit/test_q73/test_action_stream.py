"""Tests for ActionStreamBuffer — T489."""
from __future__ import annotations
import time
import pytest
from lidco.context.action_stream import ActionEvent, ActionStreamBuffer, ActionType


class TestActionStreamBuffer:
    def test_record_and_len(self):
        buf = ActionStreamBuffer()
        buf.record(ActionEvent(type=ActionType.FILE_EDIT, target="a.py", summary="added func"))
        assert len(buf) == 1

    def test_maxlen_ring_behavior(self):
        buf = ActionStreamBuffer(maxlen=3)
        for i in range(5):
            buf.record_simple(ActionType.FILE_EDIT, f"f{i}.py", "edit")
        assert len(buf) == 3

    def test_format_context_header(self):
        buf = ActionStreamBuffer()
        buf.record_simple(ActionType.TEST_RUN, "pytest", "3 passed")
        ctx = buf.format_context()
        assert ctx.startswith("## Recent activity")

    def test_format_context_includes_events(self):
        buf = ActionStreamBuffer()
        buf.record_simple(ActionType.GIT_OP, "git commit", "committed fix")
        ctx = buf.format_context()
        assert "git commit" in ctx or "git_op" in ctx

    def test_format_context_empty(self):
        buf = ActionStreamBuffer()
        assert buf.format_context() == ""

    def test_format_context_limit(self):
        buf = ActionStreamBuffer()
        for i in range(10):
            buf.record_simple(ActionType.FILE_EDIT, f"f{i}.py", f"edit {i}")
        ctx = buf.format_context(limit=3)
        lines = [l for l in ctx.splitlines() if l.strip() and not l.startswith("##")]
        assert len(lines) <= 3

    def test_clear(self):
        buf = ActionStreamBuffer()
        buf.record_simple(ActionType.FILE_READ, "x.py", "read")
        buf.clear()
        assert len(buf) == 0

    def test_events_returns_list(self):
        buf = ActionStreamBuffer()
        buf.record_simple(ActionType.SHELL_CMD, "ls", "listed")
        events = buf.events()
        assert len(events) == 1
        assert events[0].target == "ls"

    def test_action_event_format_line(self):
        e = ActionEvent(type=ActionType.FILE_EDIT, target="a.py", summary="change", timestamp=time.time())
        line = e.format_line()
        assert "a.py" in line
        assert "change" in line
