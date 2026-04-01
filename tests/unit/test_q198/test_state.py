"""Tests for OnboardingState, OnboardingStep, StepStatus — task 1105."""
from __future__ import annotations

import unittest

from lidco.onboarding.state import OnboardingState, OnboardingStep, StepStatus


class TestStepStatusEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(StepStatus.PENDING.value, "pending")
        self.assertEqual(StepStatus.DONE.value, "done")
        self.assertEqual(StepStatus.SKIPPED.value, "skipped")


class TestOnboardingStepFrozen(unittest.TestCase):
    def test_creation(self):
        s = OnboardingStep(name="detect", status=StepStatus.PENDING, completed_at=None)
        self.assertEqual(s.name, "detect")
        self.assertIsNone(s.completed_at)

    def test_frozen(self):
        s = OnboardingStep(name="detect", status=StepStatus.PENDING, completed_at=None)
        with self.assertRaises(AttributeError):
            s.name = "other"  # type: ignore[misc]


class TestOnboardingStateInit(unittest.TestCase):
    def test_empty(self):
        state = OnboardingState()
        self.assertEqual(state.steps, ())

    def test_with_steps(self):
        steps = (
            OnboardingStep("a", StepStatus.PENDING, None),
            OnboardingStep("b", StepStatus.DONE, "2026-01-01"),
        )
        state = OnboardingState(steps)
        self.assertEqual(len(state.steps), 2)


class TestMarkDone(unittest.TestCase):
    def test_marks_existing(self):
        s = OnboardingStep("a", StepStatus.PENDING, None)
        state = OnboardingState((s,))
        new_state = state.mark_done("a")
        self.assertIsNot(state, new_state)
        self.assertEqual(new_state.steps[0].status, StepStatus.DONE)
        self.assertIsNotNone(new_state.steps[0].completed_at)

    def test_original_unchanged(self):
        s = OnboardingStep("a", StepStatus.PENDING, None)
        state = OnboardingState((s,))
        state.mark_done("a")
        self.assertEqual(state.steps[0].status, StepStatus.PENDING)

    def test_adds_unknown_step(self):
        state = OnboardingState()
        new_state = state.mark_done("new_step")
        self.assertEqual(len(new_state.steps), 1)
        self.assertEqual(new_state.steps[0].name, "new_step")
        self.assertEqual(new_state.steps[0].status, StepStatus.DONE)

    def test_preserves_other_steps(self):
        steps = (
            OnboardingStep("a", StepStatus.PENDING, None),
            OnboardingStep("b", StepStatus.PENDING, None),
        )
        state = OnboardingState(steps)
        new_state = state.mark_done("a")
        self.assertEqual(new_state.steps[1].status, StepStatus.PENDING)


class TestMarkSkipped(unittest.TestCase):
    def test_marks_existing(self):
        s = OnboardingStep("a", StepStatus.PENDING, None)
        state = OnboardingState((s,))
        new_state = state.mark_skipped("a")
        self.assertEqual(new_state.steps[0].status, StepStatus.SKIPPED)

    def test_returns_new_state(self):
        s = OnboardingStep("a", StepStatus.PENDING, None)
        state = OnboardingState((s,))
        new_state = state.mark_skipped("a")
        self.assertIsNot(state, new_state)

    def test_adds_unknown_step(self):
        state = OnboardingState()
        new_state = state.mark_skipped("x")
        self.assertEqual(new_state.steps[0].status, StepStatus.SKIPPED)


class TestIsComplete(unittest.TestCase):
    def test_empty_is_complete(self):
        self.assertTrue(OnboardingState().is_complete)

    def test_all_done(self):
        steps = (
            OnboardingStep("a", StepStatus.DONE, "t"),
            OnboardingStep("b", StepStatus.SKIPPED, "t"),
        )
        self.assertTrue(OnboardingState(steps).is_complete)

    def test_pending_not_complete(self):
        steps = (
            OnboardingStep("a", StepStatus.DONE, "t"),
            OnboardingStep("b", StepStatus.PENDING, None),
        )
        self.assertFalse(OnboardingState(steps).is_complete)


class TestPending(unittest.TestCase):
    def test_returns_pending_names(self):
        steps = (
            OnboardingStep("a", StepStatus.DONE, "t"),
            OnboardingStep("b", StepStatus.PENDING, None),
            OnboardingStep("c", StepStatus.PENDING, None),
        )
        self.assertEqual(OnboardingState(steps).pending(), ("b", "c"))

    def test_empty_when_all_done(self):
        steps = (OnboardingStep("a", StepStatus.DONE, "t"),)
        self.assertEqual(OnboardingState(steps).pending(), ())


class TestProgress(unittest.TestCase):
    def test_empty_is_one(self):
        self.assertEqual(OnboardingState().progress(), 1.0)

    def test_none_done(self):
        steps = (
            OnboardingStep("a", StepStatus.PENDING, None),
            OnboardingStep("b", StepStatus.PENDING, None),
        )
        self.assertAlmostEqual(OnboardingState(steps).progress(), 0.0)

    def test_half_done(self):
        steps = (
            OnboardingStep("a", StepStatus.DONE, "t"),
            OnboardingStep("b", StepStatus.PENDING, None),
        )
        self.assertAlmostEqual(OnboardingState(steps).progress(), 0.5)

    def test_all_done(self):
        steps = (
            OnboardingStep("a", StepStatus.DONE, "t"),
            OnboardingStep("b", StepStatus.SKIPPED, "t"),
        )
        self.assertAlmostEqual(OnboardingState(steps).progress(), 1.0)
