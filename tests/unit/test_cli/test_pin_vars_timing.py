"""Tests for /pin (#173), /vars (#174), /timing (#175)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 173: /pin ────────────────────────────────────────────────────────────

class TestPinCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("pin") is not None

    def test_default_pins_empty(self):
        reg = _make_registry()
        assert reg._pins == []

    def test_no_arg_shows_empty_message(self):
        reg = _make_registry()
        result = _run(reg.get("pin").handler())
        assert "не" in result.lower() or "no" in result.lower() or "закреплённых" in result

    def test_add_pin(self):
        reg = _make_registry()
        _run(reg.get("pin").handler(arg="add always use type hints"))
        assert len(reg._pins) == 1
        assert "always use type hints" in reg._pins[0]

    def test_add_returns_confirmation(self):
        reg = _make_registry()
        result = _run(reg.get("pin").handler(arg="add use asyncio"))
        assert "1" in result or "закреплена" in result.lower()

    def test_add_multiple_pins(self):
        reg = _make_registry()
        _run(reg.get("pin").handler(arg="add first note"))
        _run(reg.get("pin").handler(arg="add second note"))
        assert len(reg._pins) == 2

    def test_list_shows_all_pins(self):
        reg = _make_registry()
        reg._pins = ["alpha note", "beta note"]
        result = _run(reg.get("pin").handler())
        assert "alpha" in result
        assert "beta" in result

    def test_list_subcommand(self):
        reg = _make_registry()
        reg._pins = ["hello world"]
        result = _run(reg.get("pin").handler(arg="list"))
        assert "hello world" in result

    def test_del_removes_pin(self):
        reg = _make_registry()
        reg._pins = ["alpha", "beta", "gamma"]
        _run(reg.get("pin").handler(arg="del 2"))
        assert reg._pins == ["alpha", "gamma"]

    def test_del_returns_confirmation(self):
        reg = _make_registry()
        reg._pins = ["something to remove"]
        result = _run(reg.get("pin").handler(arg="del 1"))
        assert "1" in result or "удалена" in result.lower()

    def test_del_invalid_index(self):
        reg = _make_registry()
        reg._pins = ["only"]
        result = _run(reg.get("pin").handler(arg="del 5"))
        assert "не существует" in result or "not" in result.lower() or "5" in result

    def test_del_non_numeric(self):
        reg = _make_registry()
        reg._pins = ["x"]
        result = _run(reg.get("pin").handler(arg="del abc"))
        assert "неверный" in result.lower() or "invalid" in result.lower() or "number" in result.lower() or "abc" in result

    def test_clear_removes_all(self):
        reg = _make_registry()
        reg._pins = ["a", "b", "c"]
        _run(reg.get("pin").handler(arg="clear"))
        assert reg._pins == []

    def test_clear_returns_count(self):
        reg = _make_registry()
        reg._pins = ["x", "y"]
        result = _run(reg.get("pin").handler(arg="clear"))
        assert "2" in result

    def test_bare_text_adds_pin(self):
        reg = _make_registry()
        _run(reg.get("pin").handler(arg="use snake_case everywhere"))
        assert len(reg._pins) == 1
        assert "snake_case" in reg._pins[0]

    def test_empty_add_rejected(self):
        reg = _make_registry()
        result = _run(reg.get("pin").handler(arg="add"))
        # Should warn about empty content
        assert "пуст" in result.lower() or "empty" in result.lower() or "текст" in result.lower()


# ── Task 174: /vars ───────────────────────────────────────────────────────────

class TestVarsCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("vars") is not None

    def test_default_vars_empty(self):
        reg = _make_registry()
        assert reg._vars == {}

    def test_no_arg_shows_empty_message(self):
        reg = _make_registry()
        result = _run(reg.get("vars").handler())
        assert "не определены" in result or "not" in result.lower() or "empty" in result.lower()

    def test_set_var(self):
        reg = _make_registry()
        _run(reg.get("vars").handler(arg="set LANG python"))
        assert reg._vars.get("LANG") == "python"

    def test_set_returns_confirmation(self):
        reg = _make_registry()
        result = _run(reg.get("vars").handler(arg="set ENV prod"))
        assert "ENV" in result or "env" in result.lower()

    def test_set_stores_uppercase_key(self):
        reg = _make_registry()
        _run(reg.get("vars").handler(arg="set lang python"))
        assert "LANG" in reg._vars

    def test_set_multiword_value(self):
        reg = _make_registry()
        _run(reg.get("vars").handler(arg="set GREETING hello world"))
        assert reg._vars["GREETING"] == "hello world"

    def test_list_shows_vars(self):
        reg = _make_registry()
        reg._vars = {"FOO": "bar", "BAZ": "qux"}
        result = _run(reg.get("vars").handler())
        assert "FOO" in result
        assert "BAZ" in result

    def test_list_subcommand(self):
        reg = _make_registry()
        reg._vars = {"X": "1"}
        result = _run(reg.get("vars").handler(arg="list"))
        assert "X" in result

    def test_del_removes_var(self):
        reg = _make_registry()
        reg._vars = {"A": "1", "B": "2"}
        _run(reg.get("vars").handler(arg="del A"))
        assert "A" not in reg._vars
        assert "B" in reg._vars

    def test_del_nonexistent_var(self):
        reg = _make_registry()
        result = _run(reg.get("vars").handler(arg="del GHOST"))
        assert "не найдена" in result or "not found" in result.lower() or "GHOST" in result

    def test_clear_removes_all(self):
        reg = _make_registry()
        reg._vars = {"A": "1", "B": "2"}
        _run(reg.get("vars").handler(arg="clear"))
        assert reg._vars == {}

    def test_clear_returns_count(self):
        reg = _make_registry()
        reg._vars = {"A": "1", "B": "2"}
        result = _run(reg.get("vars").handler(arg="clear"))
        assert "2" in result

    def test_invalid_name_rejected(self):
        reg = _make_registry()
        result = _run(reg.get("vars").handler(arg="set foo-bar value"))
        # Hyphen not allowed
        assert "недопустим" in result.lower() or "invalid" in result.lower() or "недопустимые" in result

    def test_set_no_value_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("vars").handler(arg="set ONLYNAME"))
        assert "использование" in result.lower() or "usage" in result.lower() or "NAME" in result


# ── Task 175: /timing ─────────────────────────────────────────────────────────

class TestTimingCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("timing") is not None

    def test_default_turn_times_empty(self):
        reg = _make_registry()
        # Q54/366: _turn_times is now a bounded deque — falsy when empty
        assert len(reg._turn_times) == 0

    def test_no_turns_shows_message(self):
        reg = _make_registry()
        result = _run(reg.get("timing").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "ещё" in result

    def test_shows_turn_count(self):
        reg = _make_registry()
        reg._turn_times = [1.0, 2.0, 3.0]
        result = _run(reg.get("timing").handler())
        assert "3" in result

    def test_shows_average(self):
        reg = _make_registry()
        reg._turn_times = [1.0, 3.0]
        result = _run(reg.get("timing").handler())
        assert "2.0" in result or "среднее" in result.lower()

    def test_shows_min_max(self):
        reg = _make_registry()
        reg._turn_times = [1.5, 4.5, 2.0]
        result = _run(reg.get("timing").handler())
        assert "1.5" in result
        assert "4.5" in result

    def test_shows_total(self):
        reg = _make_registry()
        reg._turn_times = [2.0, 3.0]
        result = _run(reg.get("timing").handler())
        assert "5.0" in result

    def test_few_turns_shows_per_turn(self):
        reg = _make_registry()
        reg._turn_times = [1.0, 2.0, 3.0]
        result = _run(reg.get("timing").handler())
        # With 3 turns (≤10) should show individual timings
        assert "Ход 1" in result or "1:" in result or "1.0" in result

    def test_all_flag_forces_full_output(self):
        reg = _make_registry()
        reg._turn_times = [float(i) for i in range(1, 16)]  # 15 turns
        result = _run(reg.get("timing").handler(arg="all"))
        # Should show all 15 turns
        assert "15" in result

    def test_many_turns_shows_hint(self):
        reg = _make_registry()
        reg._turn_times = [1.0] * 15
        result = _run(reg.get("timing").handler())
        # More than 10 turns — should hint about /timing all
        assert "all" in result or "все" in result.lower() or "15" in result

    def test_single_turn(self):
        reg = _make_registry()
        reg._turn_times = [3.7]
        result = _run(reg.get("timing").handler())
        assert "3.7" in result
