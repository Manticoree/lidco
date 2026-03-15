"""Tests for Q42 — TestFirstEnforcer (Task 291)."""
from __future__ import annotations

import pytest

from lidco.tdd.test_first import (
    TestFirstEnforcer,
    TestFirstViolation,
    _is_impl_file,
    _is_test_file,
)


class TestFileClassification:
    def test_test_file_patterns(self):
        assert _is_test_file("tests/test_foo.py")
        assert _is_test_file("tests/unit/test_auth.py")
        assert _is_test_file("test_utils.py")
        assert _is_test_file("src/foo_test.py")

    def test_impl_file_patterns(self):
        assert _is_impl_file("src/auth.py")
        assert _is_impl_file("src/mypackage/utils.py")
        assert _is_impl_file("lib/helpers.py")
        assert _is_impl_file("app/models.py")

    def test_test_file_not_impl(self):
        assert not _is_impl_file("tests/test_foo.py")
        assert not _is_impl_file("tests/unit/test_auth.py")

    def test_non_python_files_ignored(self):
        assert not _is_impl_file("README.md")
        assert not _is_test_file("README.md")


class TestTestFirstEnforcer:
    def test_no_violation_when_test_first(self):
        enforcer = TestFirstEnforcer()
        enforcer.on_tool_call("file_write", {"path": "tests/test_foo.py", "content": ""})
        enforcer.on_tool_call("file_write", {"path": "src/foo.py", "content": ""})
        assert not enforcer.has_violation()

    def test_violation_when_impl_before_test(self):
        enforcer = TestFirstEnforcer()
        enforcer.on_tool_call("file_write", {"path": "src/auth.py", "content": ""})
        assert enforcer.has_violation()

    def test_violation_message_contains_path(self):
        enforcer = TestFirstEnforcer()
        enforcer.on_tool_call("file_write", {"path": "src/auth.py", "content": ""})
        msg = enforcer.violation_message()
        assert "src/auth.py" in msg

    def test_block_mode_raises(self):
        enforcer = TestFirstEnforcer(mode="block")
        with pytest.raises(TestFirstViolation):
            enforcer.on_tool_call("file_write", {"path": "src/auth.py", "content": ""})

    def test_disabled_no_violation(self):
        enforcer = TestFirstEnforcer(enabled=False)
        enforcer.on_tool_call("file_write", {"path": "src/auth.py", "content": ""})
        assert not enforcer.has_violation()

    def test_set_enabled(self):
        enforcer = TestFirstEnforcer(enabled=False)
        enforcer.set_enabled(True)
        enforcer.on_tool_call("file_write", {"path": "src/auth.py", "content": ""})
        assert enforcer.has_violation()

    def test_set_mode_warn(self):
        enforcer = TestFirstEnforcer()
        enforcer.set_mode("warn")
        assert enforcer._mode == "warn"

    def test_set_mode_invalid_raises(self):
        enforcer = TestFirstEnforcer()
        with pytest.raises(ValueError):
            enforcer.set_mode("strict")

    def test_reset_turn_clears_state(self):
        enforcer = TestFirstEnforcer()
        enforcer.on_tool_call("file_write", {"path": "src/auth.py", "content": ""})
        assert enforcer.has_violation()
        enforcer.reset_turn()
        assert not enforcer.has_violation()

    def test_non_write_tools_ignored(self):
        enforcer = TestFirstEnforcer()
        enforcer.on_tool_call("bash", {"command": "python src/auth.py"})
        assert not enforcer.has_violation()

    def test_all_violations_accumulates(self):
        enforcer = TestFirstEnforcer()
        enforcer.on_tool_call("file_write", {"path": "src/a.py", "content": ""})
        enforcer.reset_turn()
        enforcer.on_tool_call("file_write", {"path": "src/b.py", "content": ""})
        assert len(enforcer.all_violations()) == 2

    def test_no_path_no_violation(self):
        enforcer = TestFirstEnforcer()
        enforcer.on_tool_call("file_write", {})  # no path key
        assert not enforcer.has_violation()

    def test_violation_only_in_current_turn(self):
        enforcer = TestFirstEnforcer()
        enforcer.on_tool_call("file_write", {"path": "src/a.py", "content": ""})
        enforcer.reset_turn()
        # New turn: write test first, then impl — no violation
        enforcer.on_tool_call("file_write", {"path": "tests/test_a.py", "content": ""})
        enforcer.on_tool_call("file_write", {"path": "src/a.py", "content": ""})
        assert not enforcer.has_violation()
