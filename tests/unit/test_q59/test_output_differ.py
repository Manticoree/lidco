"""Tests for Task 402 — OutputDiffer (src/lidco/tools/output_differ.py)."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lidco.tools.output_differ import DiffResult, OutputDiffer


# ── DiffResult ───────────────────────────────────────────────────────────────

class TestDiffResult:
    def test_fields(self):
        r = DiffResult(added_lines=3, removed_lines=1, diff_text="--- a\n+++ b\n", changed=True)
        assert r.added_lines == 3
        assert r.removed_lines == 1
        assert r.changed is True

    def test_frozen(self):
        r = DiffResult(added_lines=0, removed_lines=0, diff_text="", changed=False)
        with pytest.raises((AttributeError, TypeError)):
            r.changed = True  # type: ignore[misc]


# ── OutputDiffer.capture ──────────────────────────────────────────────────────

class TestOutputDifferCapture:
    def test_capture_returns_stdout(self):
        mock_proc = MagicMock()
        mock_proc.stdout = "captured output\n"
        mock_proc.returncode = 0
        with patch("subprocess.run", return_value=mock_proc):
            differ = OutputDiffer()
            output = differ.capture("echo captured output")
        assert output == "captured output\n"

    def test_capture_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 5)):
            differ = OutputDiffer()
            output = differ.capture("sleep 100", timeout=5)
        assert "timed out" in output

    def test_capture_exception(self):
        with patch("subprocess.run", side_effect=OSError("no shell")):
            differ = OutputDiffer()
            output = differ.capture("echo hi")
        assert "<error:" in output


# ── OutputDiffer.diff ─────────────────────────────────────────────────────────

class TestOutputDifferDiff:
    def test_identical_no_change(self):
        differ = OutputDiffer()
        result = differ.diff("hello\nworld\n", "hello\nworld\n")
        assert not result.changed
        assert result.added_lines == 0
        assert result.removed_lines == 0

    def test_added_lines(self):
        differ = OutputDiffer()
        result = differ.diff("line1\n", "line1\nline2\n")
        assert result.changed
        assert result.added_lines >= 1
        assert result.removed_lines == 0

    def test_removed_lines(self):
        differ = OutputDiffer()
        result = differ.diff("line1\nline2\n", "line1\n")
        assert result.changed
        assert result.removed_lines >= 1

    def test_modified_line(self):
        differ = OutputDiffer()
        result = differ.diff("hello\n", "world\n")
        assert result.changed
        assert result.added_lines >= 1
        assert result.removed_lines >= 1

    def test_diff_text_contains_markers(self):
        differ = OutputDiffer()
        result = differ.diff("old\n", "new\n")
        assert "---" in result.diff_text
        assert "+++" in result.diff_text

    def test_empty_both_no_change(self):
        differ = OutputDiffer()
        result = differ.diff("", "")
        assert not result.changed

    def test_empty_before(self):
        differ = OutputDiffer()
        result = differ.diff("", "new content\n")
        assert result.changed
        assert result.added_lines >= 1


# ── Integration: capture + diff ───────────────────────────────────────────────

class TestOutputDifferIntegration:
    def test_baseline_then_changed(self):
        call_count = 0
        outputs = ["version 1.0\n", "version 2.0\n"]

        def fake_run(*args, **kwargs):
            nonlocal call_count
            m = MagicMock()
            m.stdout = outputs[call_count]
            m.returncode = 0
            call_count += 1
            return m

        differ = OutputDiffer()
        with patch("subprocess.run", side_effect=fake_run):
            before = differ.capture("myapp --version")
            after = differ.capture("myapp --version")

        result = differ.diff(before, after)
        assert result.changed
        assert "1.0" in before
        assert "2.0" in after
