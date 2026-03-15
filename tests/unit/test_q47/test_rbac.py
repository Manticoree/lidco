"""Tests for RBAC — Task 325."""

from __future__ import annotations

import pytest

from lidco.security.rbac import ROLES, AccessDecision, RBACEngine, RBACManager


# ---------------------------------------------------------------------------
# RBACEngine — basic access
# ---------------------------------------------------------------------------

class TestRBACEngineBasic:
    def test_invalid_role_raises(self):
        with pytest.raises(ValueError, match="Unknown role"):
            RBACEngine("superuser")

    def test_admin_allows_all_tools(self):
        engine = RBACEngine("admin")
        decision = engine.is_allowed("bash", args={"command": "ls"})
        assert decision.allowed is True

    def test_viewer_allows_read_file(self):
        engine = RBACEngine("viewer")
        decision = engine.is_allowed("read_file")
        assert decision.allowed is True

    def test_viewer_blocks_write_file(self):
        engine = RBACEngine("viewer")
        decision = engine.is_allowed("write_file")
        assert decision.allowed is False

    def test_editor_allows_write_file(self):
        engine = RBACEngine("editor")
        decision = engine.is_allowed("write_file")
        assert decision.allowed is True

    def test_editor_allows_viewer_tools(self):
        engine = RBACEngine("editor")
        decision = engine.is_allowed("read_file")
        assert decision.allowed is True

    def test_editor_blocks_unknown_tool(self):
        engine = RBACEngine("editor")
        decision = engine.is_allowed("delete_database")
        assert decision.allowed is False


# ---------------------------------------------------------------------------
# RBACEngine — bash command inspection
# ---------------------------------------------------------------------------

class TestRBACEngineBashCommand:
    def test_editor_blocks_rm_rf(self):
        engine = RBACEngine("editor")
        decision = engine.is_allowed("bash", args={"command": "rm -rf /tmp/test"})
        assert decision.allowed is False
        assert "rm -rf" in decision.reason

    def test_editor_allows_safe_command(self):
        engine = RBACEngine("editor")
        decision = engine.is_allowed("bash", args={"command": "pytest tests/"})
        assert decision.allowed is True

    def test_editor_blocks_sudo(self):
        engine = RBACEngine("editor")
        decision = engine.is_allowed("bash", args={"command": "sudo apt install pkg"})
        assert decision.allowed is False

    def test_admin_allows_rm_rf(self):
        engine = RBACEngine("admin")
        decision = engine.is_allowed("bash", args={"command": "rm -rf /tmp"})
        assert decision.allowed is True

    def test_viewer_blocks_bash_entirely(self):
        engine = RBACEngine("viewer")
        decision = engine.is_allowed("bash", args={"command": "ls"})
        assert decision.allowed is False

    def test_bash_without_args_allowed_for_editor(self):
        engine = RBACEngine("editor")
        decision = engine.is_allowed("bash")
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# RBACEngine.allowed_tools()
# ---------------------------------------------------------------------------

class TestRBACEngineAllowedTools:
    def test_viewer_tools_subset_of_editor(self):
        viewer_tools = RBACEngine("viewer").allowed_tools()
        editor_tools = RBACEngine("editor").allowed_tools()
        # viewer tools should all be in editor tools
        assert viewer_tools.issubset(editor_tools)

    def test_admin_returns_wildcard(self):
        tools = RBACEngine("admin").allowed_tools()
        assert "*" in tools


# ---------------------------------------------------------------------------
# AccessDecision
# ---------------------------------------------------------------------------

class TestAccessDecision:
    def test_allowed(self):
        d = AccessDecision(allowed=True, role="editor", tool_name="bash")
        assert d.allowed is True

    def test_denied_with_reason(self):
        d = AccessDecision(allowed=False, role="viewer", tool_name="bash", reason="no bash")
        assert d.reason == "no bash"


# ---------------------------------------------------------------------------
# RBACManager
# ---------------------------------------------------------------------------

class TestRBACManager:
    def test_unknown_user_gets_default_role(self):
        mgr = RBACManager(default_role="viewer")
        assert mgr.get_role("unknown_user") == "viewer"

    def test_set_and_get_role(self):
        mgr = RBACManager()
        mgr.set_role("alice", "editor")
        assert mgr.get_role("alice") == "editor"

    def test_invalid_role_raises(self):
        mgr = RBACManager()
        with pytest.raises(ValueError):
            mgr.set_role("bob", "superuser")

    def test_invalid_default_role_raises(self):
        with pytest.raises(ValueError):
            RBACManager(default_role="owner")

    def test_remove_user(self):
        mgr = RBACManager()
        mgr.set_role("alice", "admin")
        assert mgr.remove_user("alice") is True
        # Falls back to default
        assert mgr.get_role("alice") == "viewer"

    def test_remove_missing_returns_false(self):
        mgr = RBACManager()
        assert mgr.remove_user("ghost") is False

    def test_engine_for_user(self):
        mgr = RBACManager()
        mgr.set_role("alice", "admin")
        engine = mgr.engine_for("alice")
        assert engine.role == "admin"

    def test_list_users_sorted(self):
        mgr = RBACManager()
        mgr.set_role("charlie", "viewer")
        mgr.set_role("alice", "admin")
        mgr.set_role("bob", "editor")
        names = [u.username for u in mgr.list_users()]
        assert names == sorted(names)
