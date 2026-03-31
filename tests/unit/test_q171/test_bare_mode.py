"""Tests for BareMode — Q171 task 967."""
from __future__ import annotations

import unittest

from lidco.modes.bare_mode import BareMode, BareConfig


class TestBareConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = BareConfig()
        self.assertTrue(cfg.skip_hooks)
        self.assertTrue(cfg.skip_plugins)
        self.assertTrue(cfg.skip_skills)
        self.assertTrue(cfg.skip_mcp)
        self.assertTrue(cfg.minimal_context)

    def test_custom(self):
        cfg = BareConfig(skip_hooks=False, skip_mcp=False)
        self.assertFalse(cfg.skip_hooks)
        self.assertFalse(cfg.skip_mcp)
        self.assertTrue(cfg.skip_plugins)


class TestBareModeActivation(unittest.TestCase):
    def setUp(self):
        self.bm = BareMode()

    def test_initially_inactive(self):
        self.assertFalse(self.bm.is_active)

    def test_activate_default(self):
        self.bm.activate()
        self.assertTrue(self.bm.is_active)

    def test_activate_with_config(self):
        cfg = BareConfig(skip_hooks=False)
        self.bm.activate(cfg)
        self.assertTrue(self.bm.is_active)
        self.assertFalse(self.bm.get_config().skip_hooks)

    def test_deactivate(self):
        self.bm.activate()
        self.bm.deactivate()
        self.assertFalse(self.bm.is_active)

    def test_deactivate_clears_timestamp(self):
        self.bm.activate()
        self.bm.deactivate()
        summary = self.bm.perf_summary()
        self.assertFalse(summary["active"])


class TestBareModeSkip(unittest.TestCase):
    def setUp(self):
        self.bm = BareMode()

    def test_should_skip_inactive(self):
        self.assertFalse(self.bm.should_skip("hooks"))

    def test_should_skip_hooks(self):
        self.bm.activate()
        self.assertTrue(self.bm.should_skip("hooks"))

    def test_should_skip_plugins(self):
        self.bm.activate()
        self.assertTrue(self.bm.should_skip("plugins"))

    def test_should_skip_skills(self):
        self.bm.activate()
        self.assertTrue(self.bm.should_skip("skills"))

    def test_should_skip_mcp(self):
        self.bm.activate()
        self.assertTrue(self.bm.should_skip("mcp"))

    def test_should_skip_context(self):
        self.bm.activate()
        self.assertTrue(self.bm.should_skip("context"))

    def test_should_skip_unknown(self):
        self.bm.activate()
        self.assertFalse(self.bm.should_skip("unknown_feature"))

    def test_should_skip_partial_config(self):
        cfg = BareConfig(skip_hooks=False, skip_mcp=True)
        self.bm.activate(cfg)
        self.assertFalse(self.bm.should_skip("hooks"))
        self.assertTrue(self.bm.should_skip("mcp"))


class TestBareModePerfSummary(unittest.TestCase):
    def test_summary_inactive(self):
        bm = BareMode()
        s = bm.perf_summary()
        self.assertFalse(s["active"])
        self.assertEqual(s["skipped_count"], 0)

    def test_summary_active(self):
        bm = BareMode()
        bm.activate()
        s = bm.perf_summary()
        self.assertTrue(s["active"])
        self.assertGreater(s["skipped_count"], 0)
        self.assertIn("hooks", s["skipped_features"])
        self.assertIsInstance(s["config"], dict)
        self.assertGreaterEqual(s["elapsed"], 0)

    def test_summary_config_keys(self):
        bm = BareMode()
        bm.activate()
        cfg = bm.perf_summary()["config"]
        for key in ("skip_hooks", "skip_plugins", "skip_skills", "skip_mcp", "minimal_context"):
            self.assertIn(key, cfg)


if __name__ == "__main__":
    unittest.main()
