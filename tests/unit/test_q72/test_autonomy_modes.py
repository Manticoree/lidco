"""Tests for AutonomyController — T483."""
from __future__ import annotations
import pytest
from lidco.confidence.autonomy import AutonomyController, AutonomyMode


class TestAutonomyController:
    def test_default_supervised(self):
        ctrl = AutonomyController()
        assert ctrl.mode == AutonomyMode.SUPERVISED

    def test_autonomous_threshold_zero(self):
        ctrl = AutonomyController(AutonomyMode.AUTONOMOUS)
        assert ctrl.threshold == 0.0

    def test_supervised_threshold_07(self):
        ctrl = AutonomyController(AutonomyMode.SUPERVISED)
        assert ctrl.threshold == 0.7

    def test_interactive_threshold_09(self):
        ctrl = AutonomyController(AutonomyMode.INTERACTIVE)
        assert ctrl.threshold == 0.9

    def test_set_mode_string(self):
        ctrl = AutonomyController()
        ctrl.set_mode("autonomous")
        assert ctrl.mode == AutonomyMode.AUTONOMOUS

    def test_set_mode_enum(self):
        ctrl = AutonomyController()
        ctrl.set_mode(AutonomyMode.INTERACTIVE)
        assert ctrl.threshold == 0.9

    def test_should_ask_autonomous_never(self):
        ctrl = AutonomyController(AutonomyMode.AUTONOMOUS)
        assert not ctrl.should_ask(0.0)
        assert not ctrl.should_ask(0.5)

    def test_should_ask_interactive_always_risky(self):
        ctrl = AutonomyController(AutonomyMode.INTERACTIVE)
        assert ctrl.should_ask(0.85)
        assert not ctrl.should_ask(0.95)

    def test_display_name(self):
        ctrl = AutonomyController(AutonomyMode.SUPERVISED)
        assert ctrl.display_name() == "SUPERVISED"
