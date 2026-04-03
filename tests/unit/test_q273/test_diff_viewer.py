"""Tests for Q273 DiffViewer widget."""
from __future__ import annotations

import unittest

from lidco.widgets.diff_viewer import DiffHunk, DiffViewer


class TestDiffHunk(unittest.TestCase):
    def test_defaults(self):
        h = DiffHunk(id=0, old_start=1)
        assert h.status == "pending"
        assert h.old_lines == []
        assert h.new_lines == []


class TestDiffViewer(unittest.TestCase):
    def test_empty_init(self):
        dv = DiffViewer()
        assert dv.hunks() == []
        assert dv.stats() == {"accepted": 0, "rejected": 0, "pending": 0, "total": 0}

    def test_set_contents_creates_hunks(self):
        dv = DiffViewer()
        dv.set_contents("line1\nline2\nline3", "line1\nchanged\nline3")
        hunks = dv.hunks()
        assert len(hunks) >= 1
        assert hunks[0].status == "pending"

    def test_init_with_contents(self):
        dv = DiffViewer(old_content="a\nb", new_content="a\nc")
        assert len(dv.hunks()) >= 1

    def test_accept_hunk(self):
        dv = DiffViewer("a\nb", "a\nc")
        hunks = dv.hunks()
        assert dv.accept_hunk(hunks[0].id) is True
        assert hunks[0].status == "accepted"

    def test_reject_hunk(self):
        dv = DiffViewer("a\nb", "a\nc")
        hunks = dv.hunks()
        assert dv.reject_hunk(hunks[0].id) is True
        assert hunks[0].status == "rejected"

    def test_accept_nonexistent(self):
        dv = DiffViewer()
        assert dv.accept_hunk(999) is False

    def test_reject_nonexistent(self):
        dv = DiffViewer()
        assert dv.reject_hunk(999) is False

    def test_next_hunk(self):
        dv = DiffViewer("a\nb\nc", "x\nb\ny")
        h = dv.next_hunk()
        assert h is not None
        assert h.status == "pending"

    def test_next_hunk_empty(self):
        dv = DiffViewer("same", "same")
        assert dv.next_hunk() is None

    def test_prev_hunk(self):
        dv = DiffViewer("a\nb\nc", "x\ny\nz")
        # Advance cursor
        dv.next_hunk()
        dv.next_hunk()
        h = dv.prev_hunk()
        assert h is not None

    def test_apply_accepted(self):
        dv = DiffViewer("line1\nold\nline3", "line1\nnew\nline3")
        hunks = dv.hunks()
        assert len(hunks) >= 1
        dv.accept_hunk(hunks[0].id)
        result = dv.apply()
        assert "new" in result
        assert "old" not in result

    def test_apply_rejected_keeps_old(self):
        dv = DiffViewer("line1\nold\nline3", "line1\nnew\nline3")
        hunks = dv.hunks()
        dv.reject_hunk(hunks[0].id)
        result = dv.apply()
        assert "old" in result
        assert "new" not in result

    def test_stats(self):
        dv = DiffViewer("a\nb\nc", "x\ny\nz")
        hunks = dv.hunks()
        if len(hunks) >= 1:
            dv.accept_hunk(hunks[0].id)
        s = dv.stats()
        assert s["accepted"] >= 1
        assert s["total"] >= 1

    def test_render(self):
        dv = DiffViewer("a", "b")
        r = dv.render()
        assert "DiffViewer" in r
        assert "hunk" in r.lower()


if __name__ == "__main__":
    unittest.main()
