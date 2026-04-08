"""Tests for lidco.cli.commands.q331_cmds -- /skills, /learning-path, /practice, /learning-progress."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q331_cmds import register_q331_commands


class _FakeRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler: object) -> None:
        self.commands[name] = (desc, handler)


class TestRegisterQ331Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _FakeRegistry()
        register_q331_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        for name in ("skills", "learning-path", "practice", "learning-progress"):
            self.assertIn(name, self.registry.commands, f"/{name} not registered")

    # -- /skills -------------------------------------------------------

    def test_skills_no_args(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_skills_add(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("add python language"))
        self.assertIn("Added skill", result)
        self.assertIn("python", result)

    def test_skills_add_default_category(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("add rust"))
        self.assertIn("rust", result)
        self.assertIn("language", result)

    def test_skills_list(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("list"))
        self.assertIn("No skills", result)

    def test_skills_record(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("record python 50"))
        self.assertIn("Recorded", result)

    def test_skills_record_no_name(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("record"))
        self.assertIn("Usage", result)

    def test_skills_top(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("top"))
        self.assertIn("No skills", result)

    def test_skills_weak(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("weak"))
        self.assertIn("No weak skills", result)

    def test_skills_snapshot(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("snapshot"))
        self.assertIn("Snapshot", result)

    def test_skills_growth_no_name(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("growth"))
        self.assertIn("Usage", result)

    def test_skills_growth(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("growth python"))
        self.assertIn("No growth data", result)

    def test_skills_unknown(self) -> None:
        _, handler = self.registry.commands["skills"]
        result = asyncio.run(handler("foobar"))
        self.assertIn("Unknown", result)

    # -- /learning-path ------------------------------------------------

    def test_learning_path_no_args(self) -> None:
        _, handler = self.registry.commands["learning-path"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_learning_path_generate(self) -> None:
        _, handler = self.registry.commands["learning-path"]
        result = asyncio.run(handler("generate python,go"))
        self.assertIn("Path", result)
        self.assertIn("python", result.lower())

    def test_learning_path_generate_no_skills(self) -> None:
        _, handler = self.registry.commands["learning-path"]
        result = asyncio.run(handler("generate"))
        self.assertIn("Usage", result)

    def test_learning_path_show(self) -> None:
        _, handler = self.registry.commands["learning-path"]
        result = asyncio.run(handler("show"))
        self.assertIn("no steps", result)

    def test_learning_path_complete(self) -> None:
        _, handler = self.registry.commands["learning-path"]
        result = asyncio.run(handler("complete 0"))
        self.assertIn("Marked step", result)

    def test_learning_path_next(self) -> None:
        _, handler = self.registry.commands["learning-path"]
        result = asyncio.run(handler("next"))
        self.assertIn("No active path", result)

    def test_learning_path_unknown(self) -> None:
        _, handler = self.registry.commands["learning-path"]
        result = asyncio.run(handler("xyz"))
        self.assertIn("Unknown", result)

    # -- /practice -----------------------------------------------------

    def test_practice_no_args(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_practice_list_empty(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler("list"))
        self.assertIn("No exercises", result)

    def test_practice_generate(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler('generate singleton "class S: pass"'))
        self.assertIn("Generated exercise", result)

    def test_practice_generate_no_args(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler("generate"))
        self.assertIn("Usage", result)

    def test_practice_show_missing(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler("show missing"))
        self.assertIn("not found", result)

    def test_practice_show_no_id(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler("show"))
        self.assertIn("Usage", result)

    def test_practice_submit_missing(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler("submit missing code"))
        self.assertIn("FAILED", result)

    def test_practice_submit_no_args(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler("submit"))
        self.assertIn("Usage", result)

    def test_practice_stats(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler("stats"))
        self.assertIn("Exercises", result)

    def test_practice_unknown(self) -> None:
        _, handler = self.registry.commands["practice"]
        result = asyncio.run(handler("xyz"))
        self.assertIn("Unknown", result)

    # -- /learning-progress --------------------------------------------

    def test_progress_no_args(self) -> None:
        _, handler = self.registry.commands["learning-progress"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_progress_summary(self) -> None:
        _, handler = self.registry.commands["learning-progress"]
        result = asyncio.run(handler("summary"))
        self.assertIn("Total XP", result)

    def test_progress_day(self) -> None:
        _, handler = self.registry.commands["learning-progress"]
        result = asyncio.run(handler("day 2026-04-01 3 50"))
        self.assertIn("Recorded", result)
        self.assertIn("2026-04-01", result)

    def test_progress_day_no_date(self) -> None:
        _, handler = self.registry.commands["learning-progress"]
        result = asyncio.run(handler("day"))
        self.assertIn("Usage", result)

    def test_progress_achievements(self) -> None:
        _, handler = self.registry.commands["learning-progress"]
        result = asyncio.run(handler("achievements"))
        self.assertIn("No achievements", result)

    def test_progress_streak(self) -> None:
        _, handler = self.registry.commands["learning-progress"]
        result = asyncio.run(handler("streak 2026-04-01,2026-04-02"))
        self.assertIn("streak", result)

    def test_progress_streak_no_dates(self) -> None:
        _, handler = self.registry.commands["learning-progress"]
        result = asyncio.run(handler("streak"))
        self.assertIn("Usage", result)

    def test_progress_unknown(self) -> None:
        _, handler = self.registry.commands["learning-progress"]
        result = asyncio.run(handler("xyz"))
        self.assertIn("Unknown", result)


if __name__ == "__main__":
    unittest.main()
