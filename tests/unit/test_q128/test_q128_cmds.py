"""Tests for lidco.cli.commands.q128_cmds."""
import asyncio
import json
import pytest


def _make_registry():
    from lidco.cli.commands.registry import CommandRegistry
    reg = CommandRegistry()
    import lidco.cli.commands.q128_cmds as mod
    mod._state.clear()
    mod.register(reg)
    return reg


def run(coro):
    return asyncio.run(coro)


class TestQ128Commands:
    def setup_method(self):
        self.reg = _make_registry()
        self.handler = self.reg.get("profile").handler

    def test_no_args_returns_usage(self):
        result = run(self.handler(""))
        assert "Usage" in result or "profile" in result.lower()

    def test_list_empty(self):
        result = run(self.handler("list"))
        assert "No profiles" in result

    def test_create_profile(self):
        result = run(self.handler("create myprofile"))
        assert "myprofile" in result

    def test_create_with_settings(self):
        result = run(self.handler('create dev {"debug": true}'))
        assert "dev" in result

    def test_list_shows_profile(self):
        run(self.handler("create dev"))
        result = run(self.handler("list"))
        assert "dev" in result

    def test_activate_profile(self):
        run(self.handler("create dev"))
        result = run(self.handler("activate dev"))
        assert "Activated" in result

    def test_activate_missing(self):
        result = run(self.handler("activate ghost"))
        assert "not found" in result.lower() or "error" in result.lower() or "ghost" in result.lower()

    def test_delete_profile(self):
        run(self.handler("create temp"))
        result = run(self.handler("delete temp"))
        assert "Deleted" in result or "temp" in result

    def test_delete_missing(self):
        result = run(self.handler("delete nope"))
        assert "not found" in result.lower() or "nope" in result

    def test_show_profile(self):
        run(self.handler("create show_test"))
        result = run(self.handler("show show_test"))
        assert "show_test" in result

    def test_show_missing(self):
        result = run(self.handler("show ghost"))
        assert "not found" in result.lower() or "ghost" in result

    def test_export_returns_json(self):
        run(self.handler("create export_me"))
        result = run(self.handler("export"))
        data = json.loads(result)
        assert isinstance(data, list)

    def test_import_profiles(self):
        data = json.dumps([
            {"name": "imported_a", "settings": {}, "description": "", "is_active": False, "created_at": ""}
        ])
        result = run(self.handler(f"import {data}"))
        assert "1" in result or "Imported" in result

    def test_activate_shows_active_in_list(self):
        run(self.handler("create active_one"))
        run(self.handler("activate active_one"))
        result = run(self.handler("list"))
        assert "*" in result

    def test_create_invalid_json_settings(self):
        result = run(self.handler("create bad {not_json}"))
        assert "Invalid" in result or "JSON" in result

    def test_create_no_name(self):
        result = run(self.handler("create"))
        assert "Usage" in result or "name" in result.lower()

    def test_profile_command_registered(self):
        assert self.reg.get("profile") is not None

    def test_multiple_profiles_in_list(self):
        run(self.handler("create aa"))
        run(self.handler("create bb"))
        result = run(self.handler("list"))
        assert "aa" in result
        assert "bb" in result

    def test_delete_then_list(self):
        run(self.handler("create to_delete"))
        run(self.handler("delete to_delete"))
        result = run(self.handler("list"))
        assert "to_delete" not in result

    def test_activate_no_name(self):
        result = run(self.handler("activate"))
        assert "Usage" in result or "name" in result.lower()

    def test_delete_no_name(self):
        result = run(self.handler("delete"))
        assert "Usage" in result or "name" in result.lower()
