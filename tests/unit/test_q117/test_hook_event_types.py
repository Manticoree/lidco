"""Tests for hook event types (Task 718)."""
import dataclasses
import unittest

from lidco.hooks.event_types import (
    InstructionsLoadedEvent,
    CwdChangedEvent,
    FileChangedEvent,
    TaskCreatedEvent,
    TaskCompletedEvent,
    ElicitationEvent,
    ElicitationResultEvent,
    PostCompactEvent,
    PreCompactEvent,
    WorktreeCreateEvent,
    WorktreeRemoveEvent,
    UserPromptSubmitEvent,
    to_hook_event,
)


ALL_EVENT_CLASSES = [
    InstructionsLoadedEvent,
    CwdChangedEvent,
    FileChangedEvent,
    TaskCreatedEvent,
    TaskCompletedEvent,
    ElicitationEvent,
    ElicitationResultEvent,
    PostCompactEvent,
    PreCompactEvent,
    WorktreeCreateEvent,
    WorktreeRemoveEvent,
    UserPromptSubmitEvent,
]


class TestInstantiation(unittest.TestCase):
    def test_all_instantiate_with_defaults(self):
        for cls in ALL_EVENT_CLASSES:
            with self.subTest(cls=cls.__name__):
                obj = cls()
                self.assertIsNotNone(obj)

    def test_all_have_event_type(self):
        for cls in ALL_EVENT_CLASSES:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(hasattr(cls, "event_type"))
                self.assertIsInstance(cls.event_type, str)
                self.assertGreater(len(cls.event_type), 0)

    def test_all_are_frozen(self):
        for cls in ALL_EVENT_CLASSES:
            with self.subTest(cls=cls.__name__):
                obj = cls()
                with self.assertRaises(dataclasses.FrozenInstanceError):
                    obj.frozen_test_attr = "should fail"  # type: ignore[attr-defined]


class TestInstructionsLoadedEvent(unittest.TestCase):
    def test_default_files_loaded(self):
        e = InstructionsLoadedEvent()
        self.assertEqual(e.files_loaded, ())

    def test_custom_files_loaded(self):
        e = InstructionsLoadedEvent(files_loaded=("a.md", "b.md"))
        self.assertEqual(e.files_loaded, ("a.md", "b.md"))

    def test_event_type(self):
        self.assertEqual(InstructionsLoadedEvent.event_type, "InstructionsLoaded")


class TestCwdChangedEvent(unittest.TestCase):
    def test_defaults(self):
        e = CwdChangedEvent()
        self.assertEqual(e.old_path, "")
        self.assertEqual(e.new_path, "")

    def test_custom(self):
        e = CwdChangedEvent(old_path="/a", new_path="/b")
        self.assertEqual(e.old_path, "/a")
        self.assertEqual(e.new_path, "/b")


class TestFileChangedEvent(unittest.TestCase):
    def test_default_change_type(self):
        e = FileChangedEvent()
        self.assertEqual(e.change_type, "modified")

    def test_custom(self):
        e = FileChangedEvent(path="/x.py", change_type="created")
        self.assertEqual(e.path, "/x.py")
        self.assertEqual(e.change_type, "created")


class TestTaskEvents(unittest.TestCase):
    def test_task_created_defaults(self):
        e = TaskCreatedEvent()
        self.assertEqual(e.task_id, "")
        self.assertEqual(e.task_title, "")

    def test_task_completed_defaults(self):
        e = TaskCompletedEvent()
        self.assertTrue(e.success)

    def test_task_completed_failure(self):
        e = TaskCompletedEvent(task_id="t1", success=False)
        self.assertFalse(e.success)


class TestElicitationEvents(unittest.TestCase):
    def test_elicitation_defaults(self):
        e = ElicitationEvent()
        self.assertEqual(e.server_name, "")
        self.assertEqual(e.fields, ())

    def test_elicitation_result_defaults(self):
        e = ElicitationResultEvent()
        self.assertEqual(e.values, ())


class TestCompactEvents(unittest.TestCase):
    def test_pre_compact(self):
        e = PreCompactEvent(current_turns=10)
        self.assertEqual(e.current_turns, 10)

    def test_post_compact(self):
        e = PostCompactEvent(turns_compacted=5)
        self.assertEqual(e.turns_compacted, 5)


class TestWorktreeEvents(unittest.TestCase):
    def test_create(self):
        e = WorktreeCreateEvent(path="/wt", branch="feat")
        self.assertEqual(e.path, "/wt")
        self.assertEqual(e.branch, "feat")

    def test_remove(self):
        e = WorktreeRemoveEvent(path="/wt")
        self.assertEqual(e.path, "/wt")


class TestUserPromptSubmitEvent(unittest.TestCase):
    def test_defaults(self):
        e = UserPromptSubmitEvent()
        self.assertEqual(e.text, "")
        self.assertEqual(e.session_id, "")

    def test_custom(self):
        e = UserPromptSubmitEvent(text="hello", session_id="s1")
        self.assertEqual(e.text, "hello")


class TestToHookEvent(unittest.TestCase):
    def test_converts_instructions_loaded(self):
        evt = InstructionsLoadedEvent(files_loaded=("a.md",))
        he = to_hook_event(evt)
        self.assertEqual(he.event_type, "InstructionsLoaded")
        self.assertIn("files_loaded", he.payload)

    def test_converts_cwd_changed(self):
        evt = CwdChangedEvent(old_path="/a", new_path="/b")
        he = to_hook_event(evt)
        self.assertEqual(he.event_type, "CwdChanged")
        self.assertEqual(he.payload["old_path"], "/a")

    def test_converts_file_changed(self):
        evt = FileChangedEvent(path="/x.py", change_type="deleted")
        he = to_hook_event(evt)
        self.assertEqual(he.payload["path"], "/x.py")
        self.assertEqual(he.payload["change_type"], "deleted")

    def test_converts_user_prompt(self):
        evt = UserPromptSubmitEvent(text="hi", session_id="s")
        he = to_hook_event(evt)
        self.assertEqual(he.payload["text"], "hi")

    def test_hook_event_has_timestamp(self):
        evt = TaskCreatedEvent(task_id="t1")
        he = to_hook_event(evt)
        self.assertIsInstance(he.timestamp, float)

    def test_hook_event_has_event_id(self):
        evt = TaskCreatedEvent()
        he = to_hook_event(evt)
        self.assertIsInstance(he.event_id, str)


if __name__ == "__main__":
    unittest.main()
