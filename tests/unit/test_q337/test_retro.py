"""Tests for lidco.productivity.retro — Retrospective."""

from __future__ import annotations

import datetime
import unittest

from lidco.productivity.retro import (
    ActionItem,
    RetroGenerator,
    RetroItem,
    Retrospective,
    SessionSummary,
)


class TestRetroItem(unittest.TestCase):
    def test_create(self) -> None:
        item = RetroItem(category="well", text="Good tests")
        self.assertEqual(item.category, "well")
        self.assertEqual(item.votes, 0)

    def test_with_votes(self) -> None:
        item = RetroItem(category="improve", text="Slow CI", votes=1)
        updated = item.with_votes(3)
        self.assertEqual(updated.votes, 3)
        self.assertEqual(item.votes, 1)  # original unchanged

    def test_frozen(self) -> None:
        item = RetroItem(category="well", text="x")
        with self.assertRaises(AttributeError):
            item.text = "y"  # type: ignore[misc]


class TestActionItem(unittest.TestCase):
    def test_create(self) -> None:
        ai = ActionItem(description="Fix CI", assignee="dev")
        self.assertEqual(ai.description, "Fix CI")
        self.assertFalse(ai.completed)

    def test_mark_complete(self) -> None:
        ai = ActionItem(description="Fix CI")
        completed = ai.mark_complete()
        self.assertTrue(completed.completed)
        self.assertFalse(ai.completed)  # original unchanged

    def test_with_due_date(self) -> None:
        ai = ActionItem(description="x", due_date=datetime.date(2026, 5, 1))
        self.assertEqual(ai.due_date, datetime.date(2026, 5, 1))


class TestSessionSummary(unittest.TestCase):
    def test_create(self) -> None:
        s = SessionSummary(
            session_id="s-1",
            start=datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2026, 1, 1, 11, 0, tzinfo=datetime.timezone.utc),
            commands_run=50,
            files_modified=10,
            errors_encountered=2,
            commits_made=5,
        )
        self.assertEqual(s.commands_run, 50)
        self.assertEqual(s.commits_made, 5)


class TestRetrospective(unittest.TestCase):
    def test_went_well_and_needs_improvement(self) -> None:
        retro = Retrospective(
            title="Sprint 1",
            date=datetime.date(2026, 4, 5),
            items=[
                RetroItem(category="well", text="Good coverage"),
                RetroItem(category="improve", text="Slow reviews"),
                RetroItem(category="well", text="Clean code"),
            ],
        )
        self.assertEqual(len(retro.went_well), 2)
        self.assertEqual(len(retro.needs_improvement), 1)

    def test_format_basic(self) -> None:
        retro = Retrospective(
            title="Sprint 1",
            date=datetime.date(2026, 4, 5),
            items=[
                RetroItem(category="well", text="Good coverage", votes=3),
                RetroItem(category="improve", text="Slow CI"),
            ],
            action_items=[
                ActionItem(description="Optimize CI", assignee="ops"),
            ],
        )
        text = retro.format()
        self.assertIn("Sprint 1", text)
        self.assertIn("Good coverage", text)
        self.assertIn("+3", text)
        self.assertIn("Slow CI", text)
        self.assertIn("Optimize CI", text)
        self.assertIn("@ops", text)

    def test_format_with_sessions(self) -> None:
        retro = Retrospective(
            title="Sprint",
            date=datetime.date(2026, 4, 5),
            sessions=[
                SessionSummary(
                    session_id="s1",
                    start=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
                    end=datetime.datetime(2026, 1, 1, 1, tzinfo=datetime.timezone.utc),
                    commands_run=10,
                    files_modified=5,
                    errors_encountered=1,
                    commits_made=3,
                ),
            ],
        )
        text = retro.format()
        self.assertIn("Sessions: 1", text)
        self.assertIn("10 commands", text)

    def test_format_empty_items(self) -> None:
        retro = Retrospective(title="Empty", date=datetime.date(2026, 4, 5))
        text = retro.format()
        self.assertIn("(no items)", text)

    def test_format_action_with_due_date(self) -> None:
        retro = Retrospective(
            title="T",
            date=datetime.date(2026, 4, 5),
            action_items=[
                ActionItem(
                    description="Do X",
                    due_date=datetime.date(2026, 5, 1),
                    completed=True,
                ),
            ],
        )
        text = retro.format()
        self.assertIn("[x]", text)
        self.assertIn("2026-05-01", text)


class TestRetroGenerator(unittest.TestCase):
    def test_add_item(self) -> None:
        gen = RetroGenerator()
        item = gen.add_item("well", "Good tests")
        self.assertEqual(item.category, "well")

    def test_add_item_invalid_category(self) -> None:
        gen = RetroGenerator()
        with self.assertRaises(ValueError):
            gen.add_item("bad", "text")

    def test_add_action(self) -> None:
        gen = RetroGenerator()
        action = gen.add_action("Fix CI", assignee="ops", due_date=datetime.date(2026, 5, 1))
        self.assertEqual(action.assignee, "ops")

    def test_vote(self) -> None:
        gen = RetroGenerator()
        gen.add_item("well", "Good")
        updated = gen.vote(0)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.votes, 1)

    def test_vote_twice(self) -> None:
        gen = RetroGenerator()
        gen.add_item("well", "Good")
        gen.vote(0)
        updated = gen.vote(0)
        self.assertEqual(updated.votes, 2)

    def test_vote_invalid_index(self) -> None:
        gen = RetroGenerator()
        self.assertIsNone(gen.vote(0))
        self.assertIsNone(gen.vote(-1))

    def test_generate_with_items(self) -> None:
        gen = RetroGenerator()
        gen.add_item("well", "Clean code")
        gen.add_item("improve", "Slow CI")
        gen.add_action("Optimize CI")
        retro = gen.generate(title="My Retro", date=datetime.date(2026, 4, 5))
        self.assertEqual(retro.title, "My Retro")
        self.assertEqual(len(retro.items), 2)
        self.assertEqual(len(retro.action_items), 1)

    def test_generate_auto_items_from_sessions(self) -> None:
        gen = RetroGenerator()
        gen.add_session(SessionSummary(
            session_id="s1",
            start=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2026, 1, 1, 1, tzinfo=datetime.timezone.utc),
            commands_run=100,
            files_modified=20,
            errors_encountered=10,
            commits_made=8,
        ))
        retro = gen.generate()
        # Should auto-generate items from session data
        self.assertTrue(len(retro.items) > 0)
        categories = {i.category for i in retro.items}
        self.assertIn("well", categories)  # commits > 0
        self.assertIn("improve", categories)  # errors > 5

    def test_generate_auto_items_no_errors(self) -> None:
        gen = RetroGenerator()
        gen.add_session(SessionSummary(
            session_id="s1",
            start=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2026, 1, 1, 1, tzinfo=datetime.timezone.utc),
            commands_run=10,
            files_modified=3,
            errors_encountered=0,
            commits_made=2,
        ))
        retro = gen.generate()
        texts = [i.text for i in retro.items]
        self.assertTrue(any("Zero errors" in t for t in texts))

    def test_clear(self) -> None:
        gen = RetroGenerator()
        gen.add_item("well", "X")
        gen.add_action("Y")
        gen.add_session(SessionSummary(
            session_id="s",
            start=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            end=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        ))
        gen.clear()
        retro = gen.generate()
        self.assertEqual(len(retro.items), 0)
        self.assertEqual(len(retro.action_items), 0)
        self.assertEqual(len(retro.sessions), 0)

    def test_generate_default_date(self) -> None:
        gen = RetroGenerator()
        retro = gen.generate()
        self.assertEqual(retro.date, datetime.date.today())


if __name__ == "__main__":
    unittest.main()
