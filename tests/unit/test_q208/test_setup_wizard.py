"""Tests for lidco.bootstrap.setup_wizard — SetupWizard."""

from __future__ import annotations

import unittest

from lidco.bootstrap.setup_wizard import SetupConfig, SetupStep, SetupWizard


class TestSetupWizard(unittest.TestCase):
    def _make_wizard(self) -> SetupWizard:
        wiz = SetupWizard()
        wiz.add_step(SetupStep(name="api_key", description="Configure API key"))
        wiz.add_step(SetupStep(name="model", description="Choose model"))
        wiz.add_step(SetupStep(name="theme", description="Choose theme", required=False))
        return wiz

    def test_add_step(self) -> None:
        wiz = self._make_wizard()
        assert len(wiz.pending_steps()) == 3

    def test_complete_step(self) -> None:
        wiz = self._make_wizard()
        updated = wiz.complete_step("api_key")
        assert updated.completed is True
        assert len(wiz.completed_steps()) == 1
        assert len(wiz.pending_steps()) == 2

    def test_complete_step_not_found(self) -> None:
        wiz = SetupWizard()
        with self.assertRaises(KeyError):
            wiz.complete_step("nope")

    def test_skip_optional_step(self) -> None:
        wiz = self._make_wizard()
        updated = wiz.skip_step("theme")
        assert updated.completed is True

    def test_skip_required_step_raises(self) -> None:
        wiz = self._make_wizard()
        with self.assertRaises(ValueError):
            wiz.skip_step("api_key")

    def test_is_complete(self) -> None:
        wiz = self._make_wizard()
        assert not wiz.is_complete()
        wiz.complete_step("api_key")
        wiz.complete_step("model")
        # theme is optional, so wizard is complete
        assert wiz.is_complete()

    def test_pending_and_completed(self) -> None:
        wiz = self._make_wizard()
        wiz.complete_step("api_key")
        assert len(wiz.pending_steps()) == 2
        assert len(wiz.completed_steps()) == 1

    def test_set_api_key(self) -> None:
        wiz = self._make_wizard()
        wiz.set_api_key("sk-test-123")
        assert wiz.get_config().api_key == "sk-test-123"

    def test_set_model(self) -> None:
        wiz = self._make_wizard()
        wiz.set_model("gpt-4")
        assert wiz.get_config().model == "gpt-4"

    def test_default_config(self) -> None:
        wiz = SetupWizard()
        cfg = wiz.get_config()
        assert cfg.api_key == ""
        assert cfg.model == "claude-sonnet-4-6"
        assert cfg.preferences == {}

    def test_test_connection(self) -> None:
        wiz = SetupWizard()
        assert wiz.test_connection() is True

    def test_summary(self) -> None:
        wiz = self._make_wizard()
        s = wiz.summary()
        assert "0/3" in s
        wiz.complete_step("api_key")
        wiz.set_api_key("key")
        s2 = wiz.summary()
        assert "1/3" in s2
        assert "API key: configured" in s2


if __name__ == "__main__":
    unittest.main()
