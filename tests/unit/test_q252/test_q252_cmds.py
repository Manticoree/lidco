"""Tests for lidco.cli.commands.q252_cmds."""
from __future__ import annotations

import asyncio

from lidco.cli.commands.registry import CommandRegistry
from lidco.cli.commands.q252_cmds import register


def _run(coro):
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    reg = CommandRegistry()
    register(reg)
    return reg


class TestGenerateCommand:
    """Tests for /generate."""

    def test_registered(self) -> None:
        reg = _make_registry()
        assert reg.get("generate") is not None

    def test_help(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("generate").handler(""))
        assert "Usage" in result

    def test_register_subcommand(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("generate").handler("register greeting py Hello {{name}}"))
        assert "Registered" in result

    def test_register_missing_args(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("generate").handler("register foo"))
        assert "Usage" in result

    def test_list_empty(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("generate").handler("list"))
        assert "No templates" in result

    def test_render_subcommand(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("generate").handler("render mytemplate"))
        assert "Usage" in result


class TestScaffoldCommand:
    """Tests for /scaffold."""

    def test_registered(self) -> None:
        reg = _make_registry()
        assert reg.get("scaffold") is not None

    def test_help(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("scaffold").handler(""))
        assert "Usage" in result

    def test_create_api(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("scaffold").handler("create api myproject"))
        assert "Generated" in result
        assert "myproject" in result

    def test_create_unknown(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("scaffold").handler("create badtype proj"))
        assert "Unknown project type" in result

    def test_preview(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("scaffold").handler("preview cli mycli"))
        assert "mycli" in result

    def test_create_missing_args(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("scaffold").handler("create api"))
        # single word after type => works (name = "api" with no second arg triggers usage)
        # actually "create api" => tokens = ["api"], len < 2 => Usage
        assert "Usage" in result


class TestCrudCommand:
    """Tests for /crud."""

    def test_registered(self) -> None:
        reg = _make_registry()
        assert reg.get("crud") is not None

    def test_help(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("crud").handler(""))
        assert "Usage" in result

    def test_generate(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("crud").handler("User email:str age:int"))
        assert "Generated 3 files" in result
        assert "model.py" in result

    def test_generate_no_fields(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("crud").handler("Item"))
        assert "Generated 3 files" in result

    def test_field_without_type(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("crud").handler("Thing name"))
        assert "Generated 3 files" in result


class TestMigrationCommand:
    """Tests for /generate-migration."""

    def test_registered(self) -> None:
        reg = _make_registry()
        assert reg.get("generate-migration") is not None

    def test_help(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("generate-migration").handler(""))
        assert "Usage" in result

    def test_create_table(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("generate-migration").handler("create_table users"))
        assert "upgrade" in result
        assert "users" in result

    def test_add_column(self) -> None:
        reg = _make_registry()
        result = _run(reg.get("generate-migration").handler("add_column users email str"))
        assert "add_column" in result
        assert "email" in result
