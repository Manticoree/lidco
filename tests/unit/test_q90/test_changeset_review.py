"""Tests for ChangesetReviewer — T585."""

import pytest
from pathlib import Path

from lidco.editing.changeset_review import (
    ChangesetReviewer,
    Changeset,
    FileChange,
    ChangesetDecision,
    ChangesetApplyResult,
)

OLD = "line1\nline2\nline3\n"
NEW = "line1\nline2 modified\nline3\nline4\n"


# ---------- collect ----------


def test_collect_basic():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"src/foo.py": (OLD, NEW)})
    assert cs.total_files == 1
    assert cs.changes[0].path == "src/foo.py"
    assert cs.changes[0].lines_added >= 1
    assert cs.changes[0].lines_removed >= 1


def test_collect_multiple_files():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect(
        {
            "a.py": ("hello\n", "hello world\n"),
            "b.py": ("x = 1\n", "x = 2\n"),
        }
    )
    assert cs.total_files == 2


def test_collect_empty():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({})
    assert cs.total_files == 0
    assert cs.changes == []


def test_collect_identical_content():
    """No real diff when old == new."""
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"same.py": ("abc\n", "abc\n")})
    # Should still have one FileChange but zero adds/removes
    assert cs.total_files == 1
    assert cs.changes[0].lines_added == 0
    assert cs.changes[0].lines_removed == 0


def test_collect_new_file():
    """Old content is empty string (new file)."""
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"new.py": ("", "print('hello')\n")})
    assert cs.total_files == 1
    assert cs.changes[0].lines_added >= 1
    assert cs.changes[0].lines_removed == 0


def test_collect_delete_file():
    """New content is empty string (file deleted)."""
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"old.py": ("print('hello')\n", "")})
    assert cs.total_files == 1
    assert cs.changes[0].lines_removed >= 1
    assert cs.changes[0].lines_added == 0


# ---------- format_summary ----------


def test_format_summary_contains_filename():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"src/foo.py": (OLD, NEW)})
    summary = reviewer.format_summary(cs)
    assert "src/foo.py" in summary


def test_format_summary_shows_stats():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"src/foo.py": (OLD, NEW)})
    summary = reviewer.format_summary(cs)
    assert "+" in summary or "-" in summary


def test_format_summary_shows_total_line():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect(
        {
            "a.py": ("a\n", "b\n"),
            "b.py": ("c\n", "d\n"),
        }
    )
    summary = reviewer.format_summary(cs)
    assert "2 files changed" in summary


def test_format_summary_empty_changeset():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({})
    summary = reviewer.format_summary(cs)
    assert "0 files changed" in summary


# ---------- format_full ----------


def test_format_full_contains_diff():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"src/foo.py": (OLD, NEW)})
    full = reviewer.format_full(cs)
    assert "src/foo.py" in full
    assert "@@" in full or "---" in full


def test_format_full_separator_per_file():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect(
        {
            "a.py": ("a\n", "b\n"),
            "b.py": ("c\n", "d\n"),
        }
    )
    full = reviewer.format_full(cs)
    assert "=== a.py ===" in full
    assert "=== b.py ===" in full


def test_format_full_empty_changeset():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({})
    full = reviewer.format_full(cs)
    assert full == ""


# ---------- apply_all ----------


def test_apply_all(tmp_path):
    f = tmp_path / "foo.py"
    f.write_text(OLD)
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({str(f): (OLD, NEW)})
    result = reviewer.apply_all(cs)
    assert result.applied_files == 1
    assert result.skipped_files == 0
    assert f.read_text() == NEW


def test_apply_all_multiple(tmp_path):
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("x = 1\n")
    f2.write_text("y = 1\n")
    reviewer = ChangesetReviewer()
    cs = reviewer.collect(
        {
            str(f1): ("x = 1\n", "x = 2\n"),
            str(f2): ("y = 1\n", "y = 2\n"),
        }
    )
    result = reviewer.apply_all(cs)
    assert result.applied_files == 2
    assert f1.read_text() == "x = 2\n"
    assert f2.read_text() == "y = 2\n"


# ---------- reject_all ----------


def test_reject_all(tmp_path):
    f = tmp_path / "foo.py"
    f.write_text(OLD)
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({str(f): (OLD, NEW)})
    result = reviewer.reject_all(cs)
    assert result.applied_files == 0
    assert result.skipped_files == 1
    assert f.read_text() == OLD  # unchanged


def test_reject_all_empty():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({})
    result = reviewer.reject_all(cs)
    assert result.applied_files == 0
    assert result.skipped_files == 0
    assert result.errors == []


# ---------- apply with selective decision ----------


def test_apply_with_decision_selective(tmp_path):
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("x = 1\n")
    f2.write_text("y = 1\n")
    reviewer = ChangesetReviewer()
    cs = reviewer.collect(
        {
            str(f1): ("x = 1\n", "x = 2\n"),
            str(f2): ("y = 1\n", "y = 2\n"),
        }
    )
    decision = ChangesetDecision(
        accepted_files={str(f1)},
        rejected_files={str(f2)},
        partial={},
    )
    result = reviewer.apply(cs, decision)
    assert result.applied_files == 1
    assert result.skipped_files == 1
    assert f1.read_text() == "x = 2\n"
    assert f2.read_text() == "y = 1\n"  # unchanged


def test_apply_file_not_in_decision_is_skipped(tmp_path):
    """Files not in accepted or rejected should be skipped."""
    f = tmp_path / "c.py"
    f.write_text("z = 1\n")
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({str(f): ("z = 1\n", "z = 2\n")})
    decision = ChangesetDecision(
        accepted_files=set(),
        rejected_files=set(),
        partial={},
    )
    result = reviewer.apply(cs, decision)
    assert result.skipped_files == 1
    assert f.read_text() == "z = 1\n"


def test_apply_error_on_bad_path():
    """Writing to a non-existent directory should produce an error, not crash."""
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"/nonexistent/dir/foo.py": ("a\n", "b\n")})
    decision = ChangesetDecision(
        accepted_files={"/nonexistent/dir/foo.py"},
        rejected_files=set(),
        partial={},
    )
    result = reviewer.apply(cs, decision)
    assert result.applied_files == 0
    assert len(result.errors) == 1


# ---------- hunk counting ----------


def test_hunk_count():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"foo.py": (OLD, NEW)})
    assert cs.changes[0].hunk_count >= 1


def test_total_hunks_sum():
    reviewer = ChangesetReviewer()
    cs = reviewer.collect(
        {
            "a.py": ("a\n", "b\n"),
            "b.py": ("c\n", "d\n"),
        }
    )
    assert cs.total_hunks == sum(c.hunk_count for c in cs.changes)


# ---------- internal helpers ----------


def test_count_hunks_multiple():
    """Diff with two separate changed regions should have 2 hunks."""
    old = "".join(f"line{i}\n" for i in range(20))
    new_lines = list(f"line{i}\n" for i in range(20))
    new_lines[2] = "CHANGED2\n"
    new_lines[17] = "CHANGED17\n"
    new = "".join(new_lines)
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"multi.py": (old, new)})
    assert cs.changes[0].hunk_count == 2


def test_count_additions_deletions_accurate():
    """Verify additions and deletions are counted properly."""
    old = "a\nb\nc\n"
    new = "a\nB\nc\nD\n"
    reviewer = ChangesetReviewer()
    cs = reviewer.collect({"x.py": (old, new)})
    ch = cs.changes[0]
    # b->B is one removal + one addition, D is one addition
    assert ch.lines_added >= 2
    assert ch.lines_removed >= 1


# ---------- partial hunk apply ----------


def test_apply_partial_hunks(tmp_path):
    """Apply only the first hunk of a two-hunk diff."""
    old_lines = [f"line{i}\n" for i in range(20)]
    new_lines = list(old_lines)
    new_lines[2] = "CHANGED2\n"
    new_lines[17] = "CHANGED17\n"
    old = "".join(old_lines)
    new = "".join(new_lines)

    f = tmp_path / "partial.py"
    f.write_text(old)

    reviewer = ChangesetReviewer()
    cs = reviewer.collect({str(f): (old, new)})
    assert cs.changes[0].hunk_count == 2

    decision = ChangesetDecision(
        accepted_files=set(),
        rejected_files=set(),
        partial={str(f): {0}},  # only first hunk
    )
    result = reviewer.apply(cs, decision)
    assert result.applied_files == 1
    content = f.read_text()
    assert "CHANGED2" in content
    assert "CHANGED17" not in content


def test_apply_partial_second_hunk_only(tmp_path):
    """Apply only the second hunk."""
    old_lines = [f"line{i}\n" for i in range(20)]
    new_lines = list(old_lines)
    new_lines[2] = "CHANGED2\n"
    new_lines[17] = "CHANGED17\n"
    old = "".join(old_lines)
    new = "".join(new_lines)

    f = tmp_path / "partial2.py"
    f.write_text(old)

    reviewer = ChangesetReviewer()
    cs = reviewer.collect({str(f): (old, new)})

    decision = ChangesetDecision(
        accepted_files=set(),
        rejected_files=set(),
        partial={str(f): {1}},  # only second hunk
    )
    result = reviewer.apply(cs, decision)
    assert result.applied_files == 1
    content = f.read_text()
    assert "CHANGED2" not in content
    assert "CHANGED17" in content


# ---------- dataclass defaults ----------


def test_file_change_fields():
    fc = FileChange(
        path="a.py",
        original="old",
        proposed="new",
        diff_text="diff",
        hunk_count=1,
        lines_added=2,
        lines_removed=1,
    )
    assert fc.path == "a.py"
    assert fc.hunk_count == 1


def test_changeset_decision_defaults():
    cd = ChangesetDecision(
        accepted_files=set(),
        rejected_files=set(),
        partial={},
    )
    assert len(cd.accepted_files) == 0


def test_apply_result_fields():
    ar = ChangesetApplyResult(applied_files=3, skipped_files=1, errors=["oops"])
    assert ar.applied_files == 3
    assert ar.errors == ["oops"]
