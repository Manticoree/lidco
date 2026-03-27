"""Tests for src/lidco/composer/session.py."""
import tempfile
from pathlib import Path

import pytest

from lidco.composer.session import (
    ComposerError,
    ComposerPlan,
    ComposerSession,
    FileChange,
)


# ------------------------------------------------------------------ #
# FileChange tests                                                      #
# ------------------------------------------------------------------ #

class TestFileChange:
    def test_unified_diff_has_path(self):
        fc = FileChange("src/foo.py", "a = 1\n", "a = 2\n")
        diff = fc.unified_diff()
        assert "src/foo.py" in diff

    def test_unified_diff_empty_when_identical(self):
        fc = FileChange("x.py", "same\n", "same\n")
        assert fc.unified_diff() == ""

    def test_lines_added(self):
        fc = FileChange("f.py", "a\nb\n", "a\nb\nc\n")
        assert fc.lines_added() >= 1

    def test_lines_removed(self):
        fc = FileChange("f.py", "a\nb\nc\n", "a\nb\n")
        assert fc.lines_removed() >= 1

    def test_is_creation_true(self):
        fc = FileChange("new.py", "", "content\n")
        assert fc.is_creation() is True

    def test_is_creation_false(self):
        fc = FileChange("old.py", "old\n", "new\n")
        assert fc.is_creation() is False

    def test_is_deletion_true(self):
        fc = FileChange("gone.py", "something\n", "")
        assert fc.is_deletion() is True

    def test_is_deletion_false(self):
        fc = FileChange("f.py", "a\n", "b\n")
        assert fc.is_deletion() is False

    def test_description_default(self):
        fc = FileChange("f.py", "a", "b")
        assert fc.description == ""

    def test_description_custom(self):
        fc = FileChange("f.py", "a", "b", description="fix typo")
        assert fc.description == "fix typo"


# ------------------------------------------------------------------ #
# ComposerPlan tests                                                   #
# ------------------------------------------------------------------ #

class TestComposerPlan:
    def test_add_change(self):
        plan = ComposerPlan(goal="test")
        fc = FileChange("a.py", "", "x\n")
        plan.add_change(fc)
        assert len(plan.changes) == 1

    def test_files_affected(self):
        plan = ComposerPlan(goal="test")
        plan.add_change(FileChange("a.py", "", "x"))
        plan.add_change(FileChange("b.py", "", "y"))
        assert set(plan.files_affected()) == {"a.py", "b.py"}

    def test_summary_contains_goal(self):
        plan = ComposerPlan(goal="refactor foo")
        plan.add_change(FileChange("f.py", "old", "new"))
        summary = plan.summary()
        assert "refactor foo" in summary

    def test_summary_contains_file_count(self):
        plan = ComposerPlan(goal="g")
        plan.add_change(FileChange("f.py", "", "x"))
        assert "1" in plan.summary()

    def test_preview_contains_goal(self):
        plan = ComposerPlan(goal="my goal")
        plan.add_change(FileChange("f.py", "a\n", "b\n"))
        assert "my goal" in plan.preview()

    def test_empty_plan_preview(self):
        plan = ComposerPlan(goal="empty")
        preview = plan.preview()
        assert "empty" in preview


# ------------------------------------------------------------------ #
# ComposerSession tests                                                #
# ------------------------------------------------------------------ #

class TestComposerSession:
    def test_create_plan_returns_plan(self):
        session = ComposerSession()
        plan = session.create_plan("my goal", [])
        assert isinstance(plan, ComposerPlan)
        assert plan.goal == "my goal"

    def test_create_plan_empty_goal_raises(self):
        session = ComposerSession()
        with pytest.raises(ComposerError):
            session.create_plan("   ", [])

    def test_current_plan_after_create(self):
        session = ComposerSession()
        plan = session.create_plan("g", [])
        assert session.current_plan is plan

    def test_add_change_without_plan_raises(self):
        session = ComposerSession()
        with pytest.raises(ComposerError):
            session.add_change(FileChange("f.py", "", "x"))

    def test_add_change_appends(self):
        session = ComposerSession()
        session.create_plan("g", [])
        session.add_change(FileChange("f.py", "", "x"))
        assert len(session.current_plan.changes) == 1

    def test_preview_no_plan(self):
        session = ComposerSession()
        assert "no plan" in session.preview()

    def test_summary_no_plan(self):
        session = ComposerSession()
        assert "no plan" in session.summary()

    def test_apply_no_plan_raises(self):
        session = ComposerSession()
        with pytest.raises(ComposerError):
            session.apply()

    def test_apply_dry_run_returns_paths(self):
        session = ComposerSession()
        changes = [FileChange("a.py", "", "x\n"), FileChange("b.py", "", "y\n")]
        session.create_plan("test", changes)
        written = session.apply(dry_run=True)
        assert set(written) == {"a.py", "b.py"}

    def test_apply_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ComposerSession(root=tmpdir)
            session.create_plan("g", [FileChange("x.py", "", "content")])
            session.apply(dry_run=True)
            assert not (Path(tmpdir) / "x.py").exists()

    def test_apply_writes_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ComposerSession(root=tmpdir)
            session.create_plan("g", [FileChange("x.py", "", "hello\n")])
            session.apply()
            content = (Path(tmpdir) / "x.py").read_text()
            assert content == "hello\n"

    def test_apply_twice_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ComposerSession(root=tmpdir)
            session.create_plan("g", [FileChange("x.py", "", "a")])
            session.apply()
            with pytest.raises(ComposerError):
                session.apply()

    def test_rollback_restores_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original = "original content\n"
            target = Path(tmpdir) / "x.py"
            target.write_text(original)
            session = ComposerSession(root=tmpdir)
            session.create_plan("g", [FileChange("x.py", original, "new content\n")])
            session.apply()
            session.rollback()
            assert target.read_text() == original

    def test_rollback_nothing_to_rollback_raises(self):
        session = ComposerSession()
        with pytest.raises(ComposerError):
            session.rollback()

    def test_history_tracks_applied_plans(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ComposerSession(root=tmpdir)
            session.create_plan("first", [FileChange("a.py", "", "a")])
            session.apply()
            session.create_plan("second", [FileChange("b.py", "", "b")])
            session.apply()
            assert "first" in session.history()
            assert "second" in session.history()

    def test_add_change_after_apply_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            session = ComposerSession(root=tmpdir)
            session.create_plan("g", [])
            session.apply()
            with pytest.raises(ComposerError):
                session.add_change(FileChange("f.py", "", "x"))
