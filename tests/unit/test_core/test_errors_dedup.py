"""Tests for ErrorRecord tool_args / occurrence_count and ErrorHistory deduplication."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lidco.core.errors import (
    ErrorHistory,
    ErrorRecord,
    _compact_args,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _rec(
    *,
    error_type: str = "tool_error",
    tool_name: str = "file_read",
    file_hint: str | None = None,
    message: str = "something failed",
    tool_args: dict | None = None,
    occurrence_count: int = 1,
) -> ErrorRecord:
    return ErrorRecord(
        id="test",
        timestamp=datetime.now(timezone.utc),
        tool_name=tool_name,
        agent_name="coder",
        error_type=error_type,
        message=message,
        traceback_str=None,
        file_hint=file_hint,
        tool_args=tool_args,
        occurrence_count=occurrence_count,
    )


# ── _compact_args ─────────────────────────────────────────────────────────────


class TestCompactArgs:
    def test_short_values_unchanged(self):
        args = {"path": "/some/file.py", "offset": 10}
        result = _compact_args(args)
        assert result["path"] == "/some/file.py"
        assert result["offset"] == 10

    def test_long_string_truncated(self):
        long_val = "x" * 300
        result = _compact_args({"content": long_val}, max_val_len=200)
        assert len(result["content"]) < 280
        assert "..." in result["content"]
        assert "(300 chars)" in result["content"]

    def test_non_string_values_unchanged(self):
        args = {"count": 42, "flag": True, "data": [1, 2, 3]}
        result = _compact_args(args)
        assert result == args

    def test_empty_dict(self):
        assert _compact_args({}) == {}

    def test_custom_max_val_len(self):
        args = {"k": "ab" * 60}  # 120 chars
        result = _compact_args(args, max_val_len=50)
        assert "..." in result["k"]
        assert "(120 chars)" in result["k"]

    def test_exact_boundary_not_truncated(self):
        """A string exactly at max_val_len should NOT be truncated."""
        args = {"k": "a" * 200}
        result = _compact_args(args, max_val_len=200)
        assert "..." not in result["k"]
        assert result["k"] == "a" * 200

    def test_original_dict_not_mutated(self):
        long_val = "z" * 300
        args = {"content": long_val}
        _compact_args(args)
        assert args["content"] == long_val  # untouched


# ── ErrorRecord new fields ────────────────────────────────────────────────────


class TestErrorRecordNewFields:
    def test_tool_args_default_none(self):
        rec = _rec()
        assert rec.tool_args is None

    def test_occurrence_count_default_one(self):
        rec = _rec()
        assert rec.occurrence_count == 1

    def test_tool_args_stored(self):
        rec = _rec(tool_args={"path": "/foo.py", "offset": 5})
        assert rec.tool_args == {"path": "/foo.py", "offset": 5}

    def test_occurrence_count_stored(self):
        rec = _rec(occurrence_count=7)
        assert rec.occurrence_count == 7

    def test_frozen_no_mutation(self):
        rec = _rec()
        with pytest.raises(Exception):  # FrozenInstanceError (subclass of AttributeError)
            rec.occurrence_count = 99  # type: ignore


# ── ErrorHistory deduplication ────────────────────────────────────────────────


class TestErrorHistoryDeduplication:
    def test_first_append_always_stored(self):
        h = ErrorHistory()
        h.append(_rec(tool_name="bash", error_type="tool_error"))
        assert len(h) == 1

    def test_identical_consecutive_merges(self):
        """Three identical (error_type, tool_name, file_hint) records → 1 entry, count=3."""
        h = ErrorHistory()
        for _ in range(3):
            h.append(_rec(tool_name="bash", error_type="tool_error", file_hint="/f.py"))
        assert len(h) == 1
        assert h.get_recent(1)[0].occurrence_count == 3

    def test_different_tool_name_not_merged(self):
        h = ErrorHistory()
        h.append(_rec(tool_name="bash", error_type="tool_error"))
        h.append(_rec(tool_name="file_edit", error_type="tool_error"))
        assert len(h) == 2

    def test_different_error_type_not_merged(self):
        h = ErrorHistory()
        h.append(_rec(tool_name="bash", error_type="tool_error"))
        h.append(_rec(tool_name="bash", error_type="exception"))
        assert len(h) == 2

    def test_different_file_hint_not_merged(self):
        h = ErrorHistory()
        h.append(_rec(tool_name="bash", file_hint="/a.py"))
        h.append(_rec(tool_name="bash", file_hint="/b.py"))
        assert len(h) == 2

    def test_none_file_hint_merges(self):
        """Two records with file_hint=None dedup correctly."""
        h = ErrorHistory()
        h.append(_rec(tool_name="bash", error_type="tool_error", file_hint=None))
        h.append(_rec(tool_name="bash", error_type="tool_error", file_hint=None))
        assert len(h) == 1
        assert h.get_recent(1)[0].occurrence_count == 2

    def test_non_consecutive_not_merged(self):
        """Records A, B, A — the second A should NOT merge with the first."""
        h = ErrorHistory()
        h.append(_rec(tool_name="bash", error_type="tool_error"))
        h.append(_rec(tool_name="file_edit", error_type="tool_error"))
        h.append(_rec(tool_name="bash", error_type="tool_error"))
        assert len(h) == 3

    def test_merged_record_uses_latest_message(self):
        """The merged record keeps the original record's message (not incremented)."""
        h = ErrorHistory()
        h.append(_rec(tool_name="bash", error_type="tool_error", message="first"))
        h.append(_rec(tool_name="bash", error_type="tool_error", message="second"))
        rec = h.get_recent(1)[0]
        assert rec.occurrence_count == 2
        # message comes from the original (first) record
        assert rec.message == "first"

    def test_max_size_still_enforced(self):
        """Ring buffer capacity is respected even with dedup."""
        h = ErrorHistory(max_size=3)
        for i in range(5):
            h.append(_rec(tool_name=f"tool_{i}", error_type="tool_error"))
        assert len(h) == 3


# ── to_context_str with new fields ───────────────────────────────────────────


class TestToContextStrEnhancements:
    def test_shows_repeat_marker(self):
        h = ErrorHistory()
        for _ in range(4):
            h.append(_rec(tool_name="bash", error_type="tool_error", file_hint="/x.py"))
        result = h.to_context_str(n=1)
        assert "×4" in result

    def test_no_repeat_marker_for_count_one(self):
        h = ErrorHistory()
        h.append(_rec(tool_name="bash"))
        result = h.to_context_str(n=1)
        assert "×" not in result

    def test_shows_tool_args(self):
        h = ErrorHistory()
        h.append(_rec(tool_name="file_read", tool_args={"path": "/foo.py"}))
        result = h.to_context_str(n=1)
        assert "Args:" in result
        assert "/foo.py" in result

    def test_no_args_section_when_none(self):
        h = ErrorHistory()
        h.append(_rec(tool_name="bash", tool_args=None))
        result = h.to_context_str(n=1)
        assert "Args:" not in result

    def test_long_args_truncated_in_context(self):
        long_path = "x" * 400
        h = ErrorHistory()
        h.append(_rec(tool_name="file_read", tool_args={"path": long_path}))
        result = h.to_context_str(n=1)
        # 300 char cap + "..."
        assert "..." in result
