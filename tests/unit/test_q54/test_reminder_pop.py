"""Q54/361 — Reminder pop index bug fix."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


def _make_commands_with_reminders(reminders: list[dict]) -> "CommandRegistry":
    from lidco.cli.commands import CommandRegistry
    cr = CommandRegistry()
    cr._reminders = list(reminders)
    cr._turn_times.extend([0.1] * 5)  # 5 turns elapsed
    return cr


def _fire_reminders(cr) -> None:
    """Replicate the reminder-firing logic from app.py (Q54/361 version)."""
    current_turn = len(cr._turn_times)
    fired_set: set[int] = set()
    for ri, rem in enumerate(cr._reminders):
        if current_turn >= rem["fire_at"]:
            fired_set.add(ri)
    if fired_set:
        cr._reminders = [r for i, r in enumerate(cr._reminders) if i not in fired_set]


class TestReminderPop:
    def test_single_reminder_fires_and_removed(self):
        cr = _make_commands_with_reminders([{"fire_at": 3, "text": "hello"}])
        _fire_reminders(cr)
        assert cr._reminders == []

    def test_two_reminders_fire_simultaneously(self):
        cr = _make_commands_with_reminders([
            {"fire_at": 2, "text": "first"},
            {"fire_at": 4, "text": "second"},
        ])
        _fire_reminders(cr)
        assert cr._reminders == []

    def test_three_reminders_fire_simultaneously(self):
        cr = _make_commands_with_reminders([
            {"fire_at": 1, "text": "a"},
            {"fire_at": 2, "text": "b"},
            {"fire_at": 5, "text": "c"},
        ])
        _fire_reminders(cr)
        assert cr._reminders == []

    def test_future_reminder_stays(self):
        cr = _make_commands_with_reminders([
            {"fire_at": 3, "text": "past"},
            {"fire_at": 99, "text": "future"},
        ])
        _fire_reminders(cr)
        assert len(cr._reminders) == 1
        assert cr._reminders[0]["text"] == "future"

    def test_no_reminders_no_error(self):
        cr = _make_commands_with_reminders([])
        _fire_reminders(cr)
        assert cr._reminders == []

    def test_no_due_reminders_unchanged(self):
        cr = _make_commands_with_reminders([
            {"fire_at": 100, "text": "later"},
        ])
        _fire_reminders(cr)
        assert len(cr._reminders) == 1
