"""Tests for lidco.mentor.walkthrough — Code Walkthrough."""

from __future__ import annotations

import unittest

from lidco.mentor.walkthrough import (
    Bookmark,
    KeyConcept,
    Question,
    Walkthrough,
    WalkthroughManager,
    WalkthroughStep,
)


class TestWalkthrough(unittest.TestCase):
    """Tests for Walkthrough dataclass."""

    def test_empty_walkthrough(self) -> None:
        wt = Walkthrough(walkthrough_id="w1", title="Test")
        self.assertEqual(wt.total_steps, 0)
        self.assertFalse(wt.is_complete)
        self.assertAlmostEqual(wt.progress, 0.0)

    def test_progress(self) -> None:
        wt = Walkthrough(walkthrough_id="w1", title="Test")
        wt.steps = [
            WalkthroughStep(1, "S1", "D1"),
            WalkthroughStep(2, "S2", "D2"),
        ]
        wt.current_step = 1
        self.assertAlmostEqual(wt.progress, 0.5)

    def test_is_complete(self) -> None:
        wt = Walkthrough(walkthrough_id="w1", title="Test")
        wt.steps = [WalkthroughStep(1, "S1", "D1")]
        wt.current_step = 1
        self.assertTrue(wt.is_complete)

    def test_get_current_step(self) -> None:
        wt = Walkthrough(walkthrough_id="w1", title="Test")
        wt.steps = [WalkthroughStep(1, "S1", "D1")]
        wt.current_step = 0
        step = wt.get_current_step()
        self.assertIsNotNone(step)
        self.assertEqual(step.title, "S1")

    def test_get_current_step_out_of_range(self) -> None:
        wt = Walkthrough(walkthrough_id="w1", title="Test")
        self.assertIsNone(wt.get_current_step())


class TestWalkthroughManager(unittest.TestCase):
    """Tests for WalkthroughManager."""

    def test_create(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("My Walk", "Description")
        self.assertEqual(wt.title, "My Walk")
        self.assertEqual(wt.description, "Description")

    def test_get(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        self.assertEqual(mgr.get(wt.walkthrough_id), wt)

    def test_get_nonexistent(self) -> None:
        mgr = WalkthroughManager()
        self.assertIsNone(mgr.get("x"))

    def test_walkthroughs_list(self) -> None:
        mgr = WalkthroughManager()
        mgr.create("A")
        mgr.create("B")
        self.assertEqual(len(mgr.walkthroughs), 2)

    def test_remove(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("A")
        self.assertTrue(mgr.remove(wt.walkthrough_id))
        self.assertIsNone(mgr.get(wt.walkthrough_id))

    def test_remove_nonexistent(self) -> None:
        mgr = WalkthroughManager()
        self.assertFalse(mgr.remove("x"))

    def test_add_step(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        step = mgr.add_step(wt.walkthrough_id, "Step 1", "First step")
        self.assertIsNotNone(step)
        self.assertEqual(step.step_number, 1)
        self.assertEqual(wt.total_steps, 1)

    def test_add_step_nonexistent(self) -> None:
        mgr = WalkthroughManager()
        self.assertIsNone(mgr.add_step("x", "S", "D"))

    def test_add_step_with_file(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        step = mgr.add_step(
            wt.walkthrough_id, "Step", "Desc",
            file_path="main.py", line_start=1, line_end=10,
            code_snippet="print('hi')",
        )
        self.assertEqual(step.file_path, "main.py")
        self.assertEqual(step.code_snippet, "print('hi')")

    def test_add_concept(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        mgr.add_step(wt.walkthrough_id, "S1", "D1")
        concept = mgr.add_concept(wt.walkthrough_id, 1, "Loops", "Iteration pattern")
        self.assertIsNotNone(concept)
        self.assertEqual(concept.name, "Loops")
        self.assertEqual(len(wt.steps[0].concepts), 1)

    def test_add_concept_bad_step(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        self.assertIsNone(mgr.add_concept(wt.walkthrough_id, 99, "X", "Y"))

    def test_add_concept_bad_walkthrough(self) -> None:
        mgr = WalkthroughManager()
        self.assertIsNone(mgr.add_concept("x", 1, "X", "Y"))

    def test_add_question(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        mgr.add_step(wt.walkthrough_id, "S1", "D1")
        q = mgr.add_question(wt.walkthrough_id, 1, "What does this do?", hint="Look at line 5")
        self.assertIsNotNone(q)
        self.assertEqual(q.text, "What does this do?")

    def test_add_question_bad_step(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        self.assertIsNone(mgr.add_question(wt.walkthrough_id, 1, "Q"))

    def test_add_question_bad_walkthrough(self) -> None:
        mgr = WalkthroughManager()
        self.assertIsNone(mgr.add_question("x", 1, "Q"))

    def test_advance(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        mgr.add_step(wt.walkthrough_id, "S1", "D1")
        mgr.add_step(wt.walkthrough_id, "S2", "D2")
        step = mgr.advance(wt.walkthrough_id)
        self.assertIsNotNone(step)
        self.assertEqual(wt.current_step, 1)

    def test_advance_complete(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        mgr.add_step(wt.walkthrough_id, "S1", "D1")
        mgr.advance(wt.walkthrough_id)  # step 0->1, complete
        result = mgr.advance(wt.walkthrough_id)
        self.assertIsNone(result)

    def test_advance_nonexistent(self) -> None:
        mgr = WalkthroughManager()
        self.assertIsNone(mgr.advance("x"))

    def test_go_back(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        mgr.add_step(wt.walkthrough_id, "S1", "D1")
        mgr.add_step(wt.walkthrough_id, "S2", "D2")
        mgr.advance(wt.walkthrough_id)
        step = mgr.go_back(wt.walkthrough_id)
        self.assertIsNotNone(step)
        self.assertEqual(wt.current_step, 0)

    def test_go_back_at_start(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        mgr.add_step(wt.walkthrough_id, "S1", "D1")
        self.assertIsNone(mgr.go_back(wt.walkthrough_id))

    def test_go_back_nonexistent(self) -> None:
        mgr = WalkthroughManager()
        self.assertIsNone(mgr.go_back("x"))

    def test_go_to_step(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        mgr.add_step(wt.walkthrough_id, "S1", "D1")
        mgr.add_step(wt.walkthrough_id, "S2", "D2")
        mgr.add_step(wt.walkthrough_id, "S3", "D3")
        step = mgr.go_to_step(wt.walkthrough_id, 3)
        self.assertIsNotNone(step)
        self.assertEqual(step.title, "S3")

    def test_go_to_step_invalid(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        self.assertIsNone(mgr.go_to_step(wt.walkthrough_id, 1))

    def test_go_to_step_nonexistent(self) -> None:
        mgr = WalkthroughManager()
        self.assertIsNone(mgr.go_to_step("x", 1))

    def test_add_bookmark(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        bm = mgr.add_bookmark(wt.walkthrough_id, "Important", "main.py", 1, 10, note="Key section")
        self.assertIsNotNone(bm)
        self.assertEqual(bm.label, "Important")
        self.assertEqual(bm.note, "Key section")

    def test_add_bookmark_nonexistent(self) -> None:
        mgr = WalkthroughManager()
        self.assertIsNone(mgr.add_bookmark("x", "L", "f", 1, 2))

    def test_get_bookmarks(self) -> None:
        mgr = WalkthroughManager()
        wt = mgr.create("Test")
        mgr.add_bookmark(wt.walkthrough_id, "A", "f.py", 1, 5)
        mgr.add_bookmark(wt.walkthrough_id, "B", "g.py", 10, 20)
        bms = mgr.get_bookmarks(wt.walkthrough_id)
        self.assertEqual(len(bms), 2)

    def test_get_bookmarks_nonexistent(self) -> None:
        mgr = WalkthroughManager()
        self.assertEqual(mgr.get_bookmarks("x"), [])

    def test_unique_ids(self) -> None:
        mgr = WalkthroughManager()
        w1 = mgr.create("A")
        w2 = mgr.create("B")
        self.assertNotEqual(w1.walkthrough_id, w2.walkthrough_id)


if __name__ == "__main__":
    unittest.main()
