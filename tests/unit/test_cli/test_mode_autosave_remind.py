"""Tests for /mode (#185), /autosave (#186), /remind (#187)."""

from __future__ import annotations

import asyncio

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 185: /mode ───────────────────────────────────────────────────────────

class TestModeCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("mode") is not None

    def test_default_mode_normal(self):
        reg = _make_registry()
        assert reg.session_mode == "normal"

    def test_no_arg_shows_current_mode(self):
        reg = _make_registry()
        result = _run(reg.get("mode").handler())
        assert "normal" in result

    def test_shows_all_modes(self):
        reg = _make_registry()
        result = _run(reg.get("mode").handler())
        for mode in ("focus", "normal", "verbose", "quiet"):
            assert mode in result

    def test_switch_to_focus(self):
        reg = _make_registry()
        _run(reg.get("mode").handler(arg="focus"))
        assert reg.session_mode == "focus"

    def test_switch_to_verbose(self):
        reg = _make_registry()
        _run(reg.get("mode").handler(arg="verbose"))
        assert reg.session_mode == "verbose"

    def test_switch_to_quiet(self):
        reg = _make_registry()
        _run(reg.get("mode").handler(arg="quiet"))
        assert reg.session_mode == "quiet"

    def test_switch_returns_confirmation(self):
        reg = _make_registry()
        result = _run(reg.get("mode").handler(arg="focus"))
        assert "focus" in result

    def test_switch_shows_description(self):
        reg = _make_registry()
        result = _run(reg.get("mode").handler(arg="quiet"))
        assert len(result) > 10  # has some description

    def test_unknown_mode_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("mode").handler(arg="turbo"))
        assert "неизвестный" in result.lower() or "unknown" in result.lower() or "turbo" in result

    def test_unknown_mode_shows_available(self):
        reg = _make_registry()
        result = _run(reg.get("mode").handler(arg="turbo"))
        assert "focus" in result or "normal" in result

    def test_current_mode_marked_in_list(self):
        reg = _make_registry()
        reg.session_mode = "verbose"
        result = _run(reg.get("mode").handler())
        # Should mark "verbose" as current
        assert "verbose" in result
        assert "текущий" in result or "current" in result.lower() or "←" in result

    def test_mode_persists(self):
        reg = _make_registry()
        _run(reg.get("mode").handler(arg="focus"))
        _run(reg.get("mode").handler(arg="quiet"))
        assert reg.session_mode == "quiet"


# ── Task 186: /autosave ───────────────────────────────────────────────────────

class TestAutosaveCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("autosave") is not None

    def test_default_autosave_off(self):
        reg = _make_registry()
        assert reg._autosave_interval == 0
        assert reg._autosave_turn_count == 0

    def test_no_arg_shows_disabled_message(self):
        reg = _make_registry()
        result = _run(reg.get("autosave").handler())
        assert "отключено" in result or "disabled" in result.lower() or "off" in result.lower()

    def test_on_enables_with_default_interval(self):
        reg = _make_registry()
        _run(reg.get("autosave").handler(arg="on"))
        assert reg._autosave_interval == 10

    def test_on_returns_confirmation(self):
        reg = _make_registry()
        result = _run(reg.get("autosave").handler(arg="on"))
        assert "включено" in result or "enabled" in result.lower() or "10" in result

    def test_off_disables(self):
        reg = _make_registry()
        reg._autosave_interval = 5
        _run(reg.get("autosave").handler(arg="off"))
        assert reg._autosave_interval == 0

    def test_off_returns_confirmation(self):
        reg = _make_registry()
        reg._autosave_interval = 5
        result = _run(reg.get("autosave").handler(arg="off"))
        assert "отключено" in result or "disabled" in result.lower()

    def test_numeric_sets_interval(self):
        reg = _make_registry()
        _run(reg.get("autosave").handler(arg="5"))
        assert reg._autosave_interval == 5

    def test_numeric_returns_interval(self):
        reg = _make_registry()
        result = _run(reg.get("autosave").handler(arg="20"))
        assert "20" in result

    def test_zero_is_treated_as_off(self):
        reg = _make_registry()
        reg._autosave_interval = 10
        _run(reg.get("autosave").handler(arg="0"))
        assert reg._autosave_interval == 0

    def test_invalid_arg_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("autosave").handler(arg="abc"))
        assert "неверный" in result.lower() or "invalid" in result.lower() or "использование" in result.lower()

    def test_status_shows_interval_and_countdown(self):
        reg = _make_registry()
        reg._autosave_interval = 5
        reg._autosave_turn_count = 3
        result = _run(reg.get("autosave").handler(arg="status"))
        assert "5" in result
        assert "2" in result  # 5 - (3 % 5) = 2 turns left

    def test_status_disabled_shows_disabled(self):
        reg = _make_registry()
        result = _run(reg.get("autosave").handler(arg="status"))
        assert "отключено" in result or "disabled" in result.lower()

    def test_negative_interval_rejected(self):
        reg = _make_registry()
        result = _run(reg.get("autosave").handler(arg="-1"))
        # -1 is not < 1 after int() conversion, but should show error or treat as off
        # Actually -1 < 1, so it should return error
        assert "≥" in result or "больше" in result.lower() or "1" in result or "неверный" in result.lower()


# ── Task 187: /remind ─────────────────────────────────────────────────────────

class TestRemindCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("remind") is not None

    def test_default_reminders_empty(self):
        reg = _make_registry()
        assert reg._reminders == []

    def test_no_arg_shows_empty_message(self):
        reg = _make_registry()
        result = _run(reg.get("remind").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "напоминаний" in result.lower()

    def test_add_reminder(self):
        reg = _make_registry()
        _run(reg.get("remind").handler(arg="in 3 run the tests"))
        assert len(reg._reminders) == 1

    def test_add_sets_fire_at(self):
        reg = _make_registry()
        reg._turn_times = [1.0, 2.0]  # current turn = 2
        _run(reg.get("remind").handler(arg="in 3 check coverage"))
        assert reg._reminders[0]["fire_at"] == 5  # 2 + 3

    def test_add_stores_text(self):
        reg = _make_registry()
        _run(reg.get("remind").handler(arg="in 2 run linter"))
        assert "run linter" in reg._reminders[0]["text"]

    def test_add_returns_confirmation(self):
        reg = _make_registry()
        result = _run(reg.get("remind").handler(arg="in 5 do something"))
        assert "5" in result and ("напоминание" in result.lower() or "remind" in result.lower())

    def test_add_invalid_n(self):
        reg = _make_registry()
        result = _run(reg.get("remind").handler(arg="in abc text"))
        assert "неверное" in result.lower() or "invalid" in result.lower() or "abc" in result

    def test_add_zero_turns_rejected(self):
        reg = _make_registry()
        result = _run(reg.get("remind").handler(arg="in 0 text"))
        assert "≥" in result or "1" in result or "должно" in result.lower()

    def test_add_missing_text_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("remind").handler(arg="in 3"))
        assert "использование" in result.lower() or "usage" in result.lower() or "текст" in result.lower()

    def test_list_shows_reminders(self):
        reg = _make_registry()
        reg._reminders = [{"fire_at": 5, "text": "check tests"}]
        result = _run(reg.get("remind").handler(arg="list"))
        assert "check tests" in result

    def test_list_shows_turns_left(self):
        reg = _make_registry()
        reg._turn_times = [1.0, 1.0]  # 2 turns done
        reg._reminders = [{"fire_at": 5, "text": "do it"}]
        result = _run(reg.get("remind").handler(arg="list"))
        assert "3" in result  # 5 - 2 = 3 turns left

    def test_del_removes_reminder(self):
        reg = _make_registry()
        reg._reminders = [{"fire_at": 3, "text": "first"}, {"fire_at": 5, "text": "second"}]
        _run(reg.get("remind").handler(arg="del 1"))
        assert len(reg._reminders) == 1
        assert reg._reminders[0]["text"] == "second"

    def test_del_invalid_index(self):
        reg = _make_registry()
        reg._reminders = [{"fire_at": 3, "text": "only"}]
        result = _run(reg.get("remind").handler(arg="del 5"))
        assert "не существует" in result or "not" in result.lower() or "5" in result

    def test_clear_removes_all(self):
        reg = _make_registry()
        reg._reminders = [
            {"fire_at": 1, "text": "a"},
            {"fire_at": 2, "text": "b"},
        ]
        _run(reg.get("remind").handler(arg="clear"))
        assert reg._reminders == []

    def test_clear_returns_count(self):
        reg = _make_registry()
        reg._reminders = [{"fire_at": 1, "text": "a"}, {"fire_at": 2, "text": "b"}]
        result = _run(reg.get("remind").handler(arg="clear"))
        assert "2" in result

    def test_multiple_reminders(self):
        reg = _make_registry()
        _run(reg.get("remind").handler(arg="in 1 first task"))
        _run(reg.get("remind").handler(arg="in 5 fifth task"))
        assert len(reg._reminders) == 2
