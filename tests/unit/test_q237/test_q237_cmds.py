"""Tests for Q237 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from collections import namedtuple
from unittest.mock import patch

import lidco.cli.commands.q237_cmds as q237_mod
from lidco.cli.commands.registry import CommandRegistry


def _registry() -> CommandRegistry:
    reg = CommandRegistry.__new__(CommandRegistry)
    reg._commands = {}
    reg._session = None
    q237_mod.register(reg)
    return reg


class TestDoctorCmd(unittest.TestCase):
    def setUp(self):
        self.reg = _registry()
        self.handler = self.reg._commands["doctor"].handler

    @patch("lidco.doctor.system_checker.shutil.disk_usage",
           return_value=namedtuple("U", "total used free")(100e9, 50e9, 50e9))
    @patch("lidco.doctor.system_checker.shutil.which", return_value="/usr/bin/git")
    def test_doctor_runs(self, *_mocks):
        result = asyncio.run(self.handler(""))
        self.assertIn("[PASS]", result)

    def test_doctor_registered(self):
        self.assertIn("doctor", self.reg._commands)


class TestDoctorApiCmd(unittest.TestCase):
    def setUp(self):
        self.reg = _registry()
        self.handler = self.reg._commands["doctor-api"].handler

    def test_all_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            result = asyncio.run(self.handler(""))
        self.assertIn("[MISSING]", result)

    def test_with_key(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test1234"}, clear=True):
            result = asyncio.run(self.handler(""))
        self.assertIn("[VALID]", result)


class TestDoctorModelsCmd(unittest.TestCase):
    def setUp(self):
        self.reg = _registry()
        self.handler = self.reg._commands["doctor-models"].handler

    def test_default_medium(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Recommended (medium)", result)
        self.assertIn("[AVAILABLE]", result)

    def test_low_budget(self):
        result = asyncio.run(self.handler("low"))
        self.assertIn("Recommended (low)", result)


class TestDoctorEnvCmd(unittest.TestCase):
    def setUp(self):
        self.reg = _registry()
        self.handler = self.reg._commands["doctor-env"].handler

    def test_env_report(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Environment Report", result)
        self.assertIn("== Python ==", result)

    def test_has_os_section(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("== OS ==", result)
