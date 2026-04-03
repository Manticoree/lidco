"""Tests for Q259 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q259_cmds as q259_mod


def _run(coro):
    return asyncio.run(coro)


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        q259_mod._state.clear()
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q259_mod.register(reg)
        self.roles = reg._commands["roles"].handler
        self.permissions = reg._commands["permissions"].handler
        self.policy = reg._commands["policy"].handler
        self.auth = reg._commands["auth"].handler


class TestRolesCmd(_CmdTestBase):
    def test_list(self):
        result = _run(self.roles("list"))
        self.assertIn("admin", result)
        self.assertIn("developer", result)

    def test_create(self):
        result = _run(self.roles("create tester QA role"))
        self.assertIn("Created role: tester", result)

    def test_create_no_name(self):
        result = _run(self.roles("create"))
        self.assertIn("Usage", result)

    def test_info(self):
        result = _run(self.roles("info admin"))
        self.assertIn("admin", result)
        self.assertIn("Permissions", result)

    def test_info_not_found(self):
        result = _run(self.roles("info ghost"))
        self.assertIn("not found", result)

    def test_delete_builtin(self):
        result = _run(self.roles("delete admin"))
        self.assertIn("Cannot delete", result)

    def test_unknown_subcommand(self):
        result = _run(self.roles("xyz"))
        self.assertIn("Usage", result)


class TestPermissionsCmd(_CmdTestBase):
    def test_check(self):
        result = _run(self.permissions("check guest read"))
        self.assertIn("ALLOWED", result)

    def test_check_denied(self):
        result = _run(self.permissions("check guest tool.use"))
        self.assertIn("DENIED", result)

    def test_assign(self):
        result = _run(self.permissions("assign alice admin"))
        self.assertIn("Assigned", result)

    def test_history_empty(self):
        result = _run(self.permissions("history"))
        self.assertIn("No permission checks", result)

    def test_unknown(self):
        result = _run(self.permissions(""))
        self.assertIn("Usage", result)


class TestPolicyCmd(_CmdTestBase):
    def test_list_empty(self):
        result = _run(self.policy("list"))
        self.assertIn("No policies", result)

    def test_add_and_list(self):
        _run(self.policy("add mypol allow"))
        result = _run(self.policy("list"))
        self.assertIn("mypol", result)

    def test_eval(self):
        _run(self.policy("add catch_all allow"))
        result = _run(self.policy('eval {"role": "admin"}'))
        self.assertIn("allow", result)

    def test_eval_bad_json(self):
        result = _run(self.policy("eval {broken"))
        self.assertIn("Invalid JSON", result)

    def test_remove(self):
        _run(self.policy("add temp deny"))
        result = _run(self.policy("remove temp"))
        self.assertIn("Removed", result)


class TestAuthCmd(_CmdTestBase):
    def test_login(self):
        result = _run(self.auth("login alice admin"))
        self.assertIn("Token:", result)
        self.assertIn("alice", result)

    def test_login_default_role(self):
        result = _run(self.auth("login bob"))
        self.assertIn("viewer", result)

    def test_validate(self):
        result = _run(self.auth("login alice"))
        token = result.split("Token: ")[1].split("\n")[0]
        val = _run(self.auth(f"validate {token}"))
        self.assertIn("Valid", val)

    def test_validate_invalid(self):
        result = _run(self.auth("validate bogus"))
        self.assertIn("invalid", result)

    def test_logout(self):
        result = _run(self.auth("login alice"))
        token = result.split("Token: ")[1].split("\n")[0]
        logout = _run(self.auth(f"logout {token}"))
        self.assertIn("revoked", logout)

    def test_sessions(self):
        _run(self.auth("login alice"))
        result = _run(self.auth("sessions"))
        self.assertIn("alice", result)

    def test_unknown(self):
        result = _run(self.auth(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
