"""Tests for /env (#238), /template (#239), /alias (#240)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 238: /env ────────────────────────────────────────────────────────────

class TestEnvvarsCommand:
    def test_registered(self):
        assert _make_registry().get("envvars") is not None

    def test_lists_env_vars(self):
        result = _run(_make_registry().get("envvars").handler())
        assert isinstance(result, str) and len(result) > 0

    def test_shows_existing_var(self):
        os.environ["_TEST_LIDCO_VAR"] = "hello_world"
        try:
            result = _run(_make_registry().get("envvars").handler(arg="_TEST_LIDCO_VAR"))
            assert "hello_world" in result
        finally:
            del os.environ["_TEST_LIDCO_VAR"]

    def test_missing_var_shows_warning(self):
        result = _run(_make_registry().get("envvars").handler(arg="_LIDCO_NONEXISTENT_XYZ"))
        assert "не установлена" in result or "not" in result.lower()

    def test_set_var(self):
        result = _run(_make_registry().get("envvars").handler(arg="_LIDCO_SET_TEST=myvalue"))
        try:
            assert "myvalue" in result or "✓" in result
            assert os.environ.get("_LIDCO_SET_TEST") == "myvalue"
        finally:
            os.environ.pop("_LIDCO_SET_TEST", None)

    def test_unset_var(self):
        os.environ["_LIDCO_UNSET_ME"] = "bye"
        result = _run(_make_registry().get("envvars").handler(arg="unset _LIDCO_UNSET_ME"))
        assert "_LIDCO_UNSET_ME" not in os.environ
        assert "удалена" in result or "removed" in result.lower() or "✓" in result

    def test_unset_missing_shows_warning(self):
        result = _run(_make_registry().get("envvars").handler(arg="unset _LIDCO_NEVER_SET_XYZ"))
        assert "не установлена" in result or "not" in result.lower()

    def test_filter_finds_match(self):
        os.environ["_LIDCO_FILTER_TARGET"] = "find_me"
        try:
            result = _run(_make_registry().get("envvars").handler(arg="--filter _LIDCO_FILTER"))
            assert "_LIDCO_FILTER_TARGET" in result
        finally:
            del os.environ["_LIDCO_FILTER_TARGET"]

    def test_filter_no_match(self):
        result = _run(_make_registry().get("envvars").handler(arg="--filter __XYZZY_NO_MATCH__"))
        assert "нет" in result.lower() or "no" in result.lower()

    def test_export_format(self):
        os.environ["_LIDCO_EXPORT_VAR"] = "exported"
        try:
            result = _run(_make_registry().get("envvars").handler(arg="--export"))
            assert "export" in result
        finally:
            del os.environ["_LIDCO_EXPORT_VAR"]

    def test_list_shows_total_count(self):
        result = _run(_make_registry().get("envvars").handler())
        # Should mention number of vars
        import re
        assert re.search(r"\d+", result)

    def test_set_invalid_name_shows_error(self):
        result = _run(_make_registry().get("envvars").handler(arg="123INVALID=value"))
        assert "некорректн" in result.lower() or "invalid" in result.lower()

    def test_unset_no_name_shows_error(self):
        result = _run(_make_registry().get("envvars").handler(arg="unset"))
        assert "укажите" in result.lower() or "name" in result.lower()

    def test_shows_commands_hint(self):
        result = _run(_make_registry().get("envvars").handler())
        assert "filter" in result.lower() or "export" in result.lower()


# ── Task 239: /template ───────────────────────────────────────────────────────

class TestScaffoldCommand:
    def test_registered(self):
        assert _make_registry().get("scaffold") is not None

    def test_list_shows_templates(self):
        result = _run(_make_registry().get("scaffold").handler())
        assert "class" in result
        assert "function" in result
        assert "test" in result

    def test_shows_template_count(self):
        result = _run(_make_registry().get("scaffold").handler())
        import re
        nums = re.findall(r"\d+", result)
        assert any(int(n) >= 5 for n in nums)

    def test_show_class_template(self):
        result = _run(_make_registry().get("scaffold").handler(arg="class"))
        assert "class" in result
        assert "```" in result

    def test_show_function_template(self):
        result = _run(_make_registry().get("scaffold").handler(arg="function"))
        assert "def" in result

    def test_show_test_template(self):
        result = _run(_make_registry().get("scaffold").handler(arg="test"))
        assert "pytest" in result or "test" in result.lower()

    def test_show_dataclass_template(self):
        result = _run(_make_registry().get("scaffold").handler(arg="dataclass"))
        assert "@dataclass" in result

    def test_show_cli_template(self):
        result = _run(_make_registry().get("scaffold").handler(arg="cli"))
        assert "argparse" in result or "main" in result

    def test_show_fastapi_template(self):
        result = _run(_make_registry().get("scaffold").handler(arg="fastapi"))
        assert "FastAPI" in result or "fastapi" in result.lower()

    def test_unknown_template_shows_error(self):
        result = _run(_make_registry().get("scaffold").handler(arg="xyzzy_unknown"))
        assert "не найден" in result or "not found" in result.lower()

    def test_creates_file(self, tmp_path):
        out = tmp_path / "myclass.py"
        result = _run(_make_registry().get("scaffold").handler(arg=f"class {out}"))
        assert out.exists()
        assert "class" in out.read_text().lower()

    def test_created_file_shown_in_result(self, tmp_path):
        out = tmp_path / "myfunc.py"
        result = _run(_make_registry().get("scaffold").handler(arg=f"function {out}"))
        assert "myf" in result or str(out) in result or "✅" in result

    def test_existing_file_rejected(self, tmp_path):
        out = tmp_path / "exists.py"
        out.write_text("x = 1\n")
        result = _run(_make_registry().get("scaffold").handler(arg=f"class {out}"))
        assert "уже существует" in result or "exists" in result.lower()

    def test_substitution_applied(self, tmp_path):
        out = tmp_path / "animal.py"
        result = _run(_make_registry().get("scaffold").handler(arg=f"class {out} Name=Animal"))
        content = out.read_text()
        assert "Animal" in content

    def test_test_template_has_pytest(self, tmp_path):
        out = tmp_path / "test_foo.py"
        _run(_make_registry().get("scaffold").handler(arg=f"test {out}"))
        content = out.read_text()
        assert "pytest" in content

    def test_list_subcommand(self):
        result = _run(_make_registry().get("scaffold").handler(arg="list"))
        assert "class" in result and "function" in result


# ── Task 240: /alias ──────────────────────────────────────────────────────────

class TestAliasCommand:
    def test_registered(self):
        assert _make_registry().get("alias") is not None

    def test_no_aliases_shows_message(self):
        reg = _make_registry()
        result = _run(reg.get("alias").handler())
        assert "не определены" in result or "псевдоним" in result.lower() or "no" in result.lower()

    def test_create_alias(self):
        reg = _make_registry()
        result = _run(reg.get("alias").handler(arg="gs=/git status"))
        assert "✓" in result or "создан" in result.lower()

    def test_alias_in_memory(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="myalias /lint src/"))
        result = _run(reg.get("alias").handler())
        assert "myalias" in result

    def test_list_shows_alias(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="testalias=/coverage"))
        result = _run(reg.get("alias").handler(arg="list"))
        assert "testalias" in result

    def test_stored_in_lidco_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="fa=/find src"))
        alias_file = tmp_path / ".lidco" / "aliases.json"
        assert alias_file.exists()
        data = json.loads(alias_file.read_text())
        assert "fa" in data
        assert data["fa"] == "/find src"

    def test_del_alias(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="todel=/something"))
        result = _run(reg.get("alias").handler(arg="del todel"))
        assert "✓" in result or "удалён" in result.lower()

    def test_del_removes_from_memory(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="gone=/thing"))
        _run(reg.get("alias").handler(arg="del gone"))
        result = _run(reg.get("alias").handler())
        assert "gone" not in result

    def test_del_nonexistent_shows_warning(self):
        reg = _make_registry()
        result = _run(reg.get("alias").handler(arg="del nonexistent_alias_xyz"))
        assert "не найден" in result or "not found" in result.lower()

    def test_run_shows_command(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="runme=/lint src/"))
        result = _run(reg.get("alias").handler(arg="run runme"))
        assert "/lint src/" in result or "lint" in result

    def test_run_unknown_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("alias").handler(arg="run xyzzy_ghost"))
        assert "не найден" in result or "not found" in result.lower()

    def test_show_alias(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="viewer=/head main.py 20"))
        result = _run(reg.get("alias").handler(arg="show viewer"))
        assert "/head main.py 20" in result

    def test_clear_removes_all(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="a1=/cmd1"))
        _run(reg.get("alias").handler(arg="a2=/cmd2"))
        _run(reg.get("alias").handler(arg="clear"))
        result = _run(reg.get("alias").handler())
        assert "a1" not in result
        assert "a2" not in result

    def test_invalid_name_eq_syntax_shows_error(self):
        reg = _make_registry()
        # Name with special chars (! is not in [A-Za-z0-9_-])
        result = _run(reg.get("alias").handler(arg="bad!name=/cmd"))
        assert "некорректн" in result.lower() or "✓" not in result

    def test_unknown_subcommand_shows_help(self):
        reg = _make_registry()
        # Single word that's not a known subcommand and not in _aliases
        result = _run(reg.get("alias").handler(arg="xyzzy_unknown_alias_sub"))
        assert "не найден" in result or "псевдоним" in result.lower()

    def test_multiple_aliases_listed(self):
        reg = _make_registry()
        _run(reg.get("alias").handler(arg="alpha=/cmd1"))
        _run(reg.get("alias").handler(arg="beta=/cmd2"))
        _run(reg.get("alias").handler(arg="gamma=/cmd3"))
        result = _run(reg.get("alias").handler())
        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result
