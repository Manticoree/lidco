"""Tests for ShortcutTrainer — Q271."""
from __future__ import annotations

import unittest

from lidco.shortcuts.registry import Shortcut, ShortcutRegistry
from lidco.shortcuts.trainer import ShortcutTrainer, TrainingProgress, QuizQuestion


class TestShortcutTrainer(unittest.TestCase):
    def setUp(self):
        self.reg = ShortcutRegistry()
        self.reg.register(Shortcut("ctrl+s", "save", "Save file"))
        self.reg.register(Shortcut("ctrl+z", "undo", "Undo"))
        self.reg.register(Shortcut("ctrl+c", "copy", "Copy"))
        self.trainer = ShortcutTrainer(self.reg)

    def test_generate_quiz(self):
        questions = self.trainer.generate_quiz(2)
        self.assertEqual(len(questions), 2)
        self.assertIsInstance(questions[0], QuizQuestion)

    def test_generate_quiz_caps_at_available(self):
        questions = self.trainer.generate_quiz(100)
        self.assertEqual(len(questions), 3)

    def test_generate_quiz_empty_registry(self):
        empty = ShortcutRegistry()
        t = ShortcutTrainer(empty)
        self.assertEqual(t.generate_quiz(), [])

    def test_answer_correct(self):
        result = self.trainer.answer("save", "ctrl+s")
        self.assertTrue(result)

    def test_answer_wrong(self):
        result = self.trainer.answer("save", "ctrl+z")
        self.assertFalse(result)

    def test_progress_tracked(self):
        self.trainer.answer("save", "ctrl+s")
        prog = self.trainer.progress("ctrl+s")
        self.assertEqual(len(prog), 1)
        self.assertEqual(prog[0].attempts, 1)
        self.assertEqual(prog[0].correct, 1)

    def test_progress_all(self):
        self.trainer.answer("save", "ctrl+s")
        self.trainer.answer("undo", "ctrl+z")
        self.assertEqual(len(self.trainer.progress()), 2)

    def test_accuracy(self):
        self.trainer.answer("save", "ctrl+s")  # correct
        self.trainer.answer("save", "wrong")    # wrong
        acc = self.trainer.accuracy()
        self.assertAlmostEqual(acc, 0.5, places=2)

    def test_accuracy_no_attempts(self):
        self.assertEqual(self.trainer.accuracy(), 0.0)

    def test_weakest(self):
        self.trainer.answer("save", "ctrl+s")  # correct
        self.trainer.answer("undo", "wrong")    # wrong
        weak = self.trainer.weakest(1)
        self.assertEqual(len(weak), 1)
        self.assertEqual(weak[0].shortcut_keys, "ctrl+z")

    def test_reset(self):
        self.trainer.answer("save", "ctrl+s")
        self.trainer.reset()
        self.assertEqual(len(self.trainer.progress()), 0)

    def test_summary(self):
        self.trainer.answer("save", "ctrl+s")
        s = self.trainer.summary()
        self.assertEqual(s["total_shortcuts"], 1)
        self.assertEqual(s["total_attempts"], 1)
        self.assertEqual(s["total_correct"], 1)


if __name__ == "__main__":
    unittest.main()
