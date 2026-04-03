"""Tests for Q272 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import CommandRegistry
from lidco.cli.commands.q272_cmds import register


def _run(coro):
    return asyncio.run(coro)


class TestA11yCmd(unittest.TestCase):
    def setUp(self):
        self.reg = CommandRegistry()
        register(self.reg)

    def test_status(self):
        out = _run(self.reg._commands["a11y"].handler("status"))
        self.assertIn("screen-reader", out)
        self.assertIn("high-contrast", out)

    def test_enable_disable(self):
        out = _run(self.reg._commands["a11y"].handler("enable high-contrast"))
        self.assertIn("enabled", out)
        out = _run(self.reg._commands["a11y"].handler("disable high-contrast"))
        self.assertIn("disabled", out)

    def test_unknown_feature(self):
        out = _run(self.reg._commands["a11y"].handler("enable nope"))
        self.assertIn("Unknown", out)


class TestHighContrastCmd(unittest.TestCase):
    def setUp(self):
        self.reg = CommandRegistry()
        register(self.reg)

    def test_enable(self):
        out = _run(self.reg._commands["high-contrast"].handler("enable"))
        self.assertIn("enabled", out)

    def test_check(self):
        out = _run(self.reg._commands["high-contrast"].handler("check #FFFFFF #000000"))
        self.assertIn("Ratio", out)
        self.assertIn("AA", out)

    def test_palette(self):
        out = _run(self.reg._commands["high-contrast"].handler("palette"))
        self.assertIn("text", out)


class TestReducedMotionCmd(unittest.TestCase):
    def setUp(self):
        self.reg = CommandRegistry()
        register(self.reg)

    def test_enable_disable(self):
        out = _run(self.reg._commands["reduced-motion"].handler("enable"))
        self.assertIn("enabled", out)
        out = _run(self.reg._commands["reduced-motion"].handler("disable"))
        self.assertIn("disabled", out)

    def test_preference(self):
        out = _run(self.reg._commands["reduced-motion"].handler("preference animations false"))
        self.assertIn("animations", out)


class TestVoiceCmd(unittest.TestCase):
    def setUp(self):
        self.reg = CommandRegistry()
        register(self.reg)

    def test_add_and_list(self):
        out = _run(self.reg._commands["voice"].handler("add save do_save editing"))
        self.assertIn("Registered", out)
        out = _run(self.reg._commands["voice"].handler("list"))
        self.assertIn("save", out)

    def test_match(self):
        _run(self.reg._commands["voice"].handler("add open open_file"))
        out = _run(self.reg._commands["voice"].handler("match open"))
        self.assertIn("Matched", out)


if __name__ == "__main__":
    unittest.main()
