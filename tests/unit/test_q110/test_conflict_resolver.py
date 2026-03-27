"""Tests for src/lidco/git/conflict_resolver.py."""
import pytest

from lidco.git.conflict_resolver import (
    Conflict, ConflictError, ConflictResolver, ConflictType, Resolution, ResolveResult,
)

_SIMPLE_CONFLICT = """\
line before
<<<<<<< HEAD
our version
=======
their version
>>>>>>> feature/x
line after
"""

_IDENTICAL_CONFLICT = """\
<<<<<<< HEAD
same line
=======
same line
>>>>>>> other
"""

_EMPTY_OURS = """\
<<<<<<< HEAD
=======
new line added
>>>>>>> feature/y
"""

_TWO_CONFLICTS = """\
<<<<<<< HEAD
version A
=======
version B
>>>>>>> dev
middle line
<<<<<<< HEAD
value 1
=======
value 2
>>>>>>> dev
"""

_NO_CONFLICT = "just a regular file\nno markers here\n"


class TestConflict:
    def test_conflict_type_identical(self):
        c = Conflict(0, "HEAD", "feat", ["same"], ["same"])
        assert c.conflict_type == ConflictType.IDENTICAL

    def test_conflict_type_ours_only(self):
        c = Conflict(0, "HEAD", "feat", ["our line"], [""])
        assert c.conflict_type == ConflictType.OURS_ONLY

    def test_conflict_type_theirs_only(self):
        c = Conflict(0, "HEAD", "feat", [""], ["their line"])
        assert c.conflict_type == ConflictType.THEIRS_ONLY

    def test_conflict_type_complex(self):
        c = Conflict(0, "HEAD", "feat", ["a", "b"], ["c", "d"])
        assert c.conflict_type == ConflictType.COMPLEX

    def test_suggested_resolution_identical(self):
        c = Conflict(0, "HEAD", "feat", ["x"], ["x"])
        assert c.suggested_resolution() == Resolution.OURS

    def test_suggested_resolution_complex(self):
        c = Conflict(0, "HEAD", "feat", ["a"], ["b"])
        assert c.suggested_resolution() == Resolution.MANUAL

    def test_resolve_ours(self):
        c = Conflict(0, "HEAD", "feat", ["our"], ["their"])
        assert c.resolve(Resolution.OURS) == ["our"]

    def test_resolve_theirs(self):
        c = Conflict(0, "HEAD", "feat", ["our"], ["their"])
        assert c.resolve(Resolution.THEIRS) == ["their"]

    def test_resolve_both(self):
        c = Conflict(0, "HEAD", "feat", ["our"], ["their"])
        assert c.resolve(Resolution.BOTH) == ["our", "their"]

    def test_resolve_manual_raises(self):
        c = Conflict(0, "HEAD", "feat", ["a"], ["b"])
        with pytest.raises(ConflictError):
            c.resolve(Resolution.MANUAL)

    def test_summary_contains_info(self):
        c = Conflict(0, "HEAD", "feat", ["a"], ["b"], start_line=3)
        s = c.summary()
        assert "Conflict" in s or "conflict" in s


class TestConflictResolver:
    def test_has_conflicts_true(self):
        r = ConflictResolver()
        assert r.has_conflicts(_SIMPLE_CONFLICT) is True

    def test_has_conflicts_false(self):
        r = ConflictResolver()
        assert r.has_conflicts(_NO_CONFLICT) is False

    def test_parse_finds_conflict(self):
        r = ConflictResolver()
        conflicts = r.parse(_SIMPLE_CONFLICT)
        assert len(conflicts) == 1

    def test_parse_labels(self):
        r = ConflictResolver()
        conflicts = r.parse(_SIMPLE_CONFLICT)
        c = conflicts[0]
        assert "HEAD" in c.ours_label
        assert "feature/x" in c.theirs_label

    def test_parse_ours_lines(self):
        r = ConflictResolver()
        conflicts = r.parse(_SIMPLE_CONFLICT)
        assert "our version" in conflicts[0].ours_lines

    def test_parse_theirs_lines(self):
        r = ConflictResolver()
        conflicts = r.parse(_SIMPLE_CONFLICT)
        assert "their version" in conflicts[0].theirs_lines

    def test_parse_two_conflicts(self):
        r = ConflictResolver()
        conflicts = r.parse(_TWO_CONFLICTS)
        assert len(conflicts) == 2

    def test_parse_no_conflict(self):
        r = ConflictResolver()
        assert r.parse(_NO_CONFLICT) == []

    def test_count(self):
        r = ConflictResolver()
        assert r.count(_TWO_CONFLICTS) == 2
        assert r.count(_NO_CONFLICT) == 0

    def test_auto_resolve_no_conflicts(self):
        r = ConflictResolver()
        result = r.auto_resolve(_NO_CONFLICT)
        assert result.content == _NO_CONFLICT
        assert result.resolved == 0

    def test_auto_resolve_identical(self):
        r = ConflictResolver()
        result = r.auto_resolve(_IDENTICAL_CONFLICT)
        assert "same line" in result.content
        assert "<<<<<<" not in result.content

    def test_auto_resolve_removes_markers(self):
        r = ConflictResolver()
        result = r.auto_resolve(_SIMPLE_CONFLICT)
        assert "<<<<<<" not in result.content
        assert "=======" not in result.content
        assert ">>>>>>>" not in result.content

    def test_auto_resolve_theirs_only(self):
        r = ConflictResolver()
        result = r.auto_resolve(_EMPTY_OURS)
        assert "new line added" in result.content

    def test_auto_resolve_all_resolved(self):
        r = ConflictResolver()
        result = r.auto_resolve(_IDENTICAL_CONFLICT)
        assert result.all_resolved is True

    def test_resolve_result_summary(self):
        r = ConflictResolver()
        result = r.auto_resolve(_IDENTICAL_CONFLICT)
        s = result.summary()
        assert "Resolved" in s or "resolved" in s

    def test_diff_summary(self):
        r = ConflictResolver()
        conflicts = r.parse(_TWO_CONFLICTS)
        s = r.diff_summary(conflicts)
        assert s["total"] == 2
        assert "by_type" in s
        assert "auto_resolvable" in s

    def test_resolve_conflict_by_index_ours(self):
        r = ConflictResolver()
        result = r.resolve_conflict(_SIMPLE_CONFLICT, 0, Resolution.OURS)
        assert "our version" in result
        assert "<<<<<<" not in result

    def test_resolve_conflict_by_index_theirs(self):
        r = ConflictResolver()
        result = r.resolve_conflict(_SIMPLE_CONFLICT, 0, Resolution.THEIRS)
        assert "their version" in result

    def test_resolve_conflict_out_of_range(self):
        r = ConflictResolver()
        with pytest.raises(ConflictError):
            r.resolve_conflict(_SIMPLE_CONFLICT, 99, Resolution.OURS)
