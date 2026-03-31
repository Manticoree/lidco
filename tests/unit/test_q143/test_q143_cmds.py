"""Tests for Q143 CLI commands — Task 851."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from lidco.cli.commands import q143_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ143Commands(unittest.TestCase):
    def setUp(self):
        q143_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q143_cmds.register(MockRegistry())
        self.handler = self.registered["diag"].handler

    def test_command_registered(self):
        self.assertIn("diag", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self):
        result = _run(self.handler("unknown"))
        self.assertIn("Usage", result)

    # --- env ---

    def test_env_default(self):
        result = _run(self.handler("env"))
        self.assertIn("Environment:", result)

    def test_env_python(self):
        result = _run(self.handler("env python"))
        self.assertIn("python_version", result)

    def test_env_python_custom_version(self):
        result = _run(self.handler("env python 3.0"))
        self.assertIn("[ok]", result)

    def test_env_var_missing_name(self):
        result = _run(self.handler("env var"))
        self.assertIn("Usage", result)

    def test_env_var_check(self):
        result = _run(self.handler("env var PATH"))
        # PATH is almost always set
        self.assertIn("PATH", result)

    def test_env_dir_missing_path(self):
        result = _run(self.handler("env dir"))
        self.assertIn("Usage", result)

    def test_env_dir_check(self):
        result = _run(self.handler("env dir /tmp"))
        self.assertIn("dir:/tmp", result)

    # --- deps ---

    def test_deps_default(self):
        result = _run(self.handler("deps"))
        self.assertIn("Dependencies:", result)

    def test_deps_custom_packages(self):
        result = _run(self.handler("deps os sys"))
        self.assertIn("Dependencies:", result)

    # --- bench ---

    def test_bench(self):
        result = _run(self.handler("bench"))
        self.assertIn("ops/s", result)
        self.assertIn("hashlib_md5", result)

    # --- system ---

    def test_system(self):
        result = _run(self.handler("system"))
        self.assertIn("System Report", result)
        self.assertIn("Python", result)
        self.assertIn("Platform", result)

    def test_system_contains_pid(self):
        result = _run(self.handler("system"))
        self.assertIn("PID", result)

    def test_system_contains_encoding(self):
        result = _run(self.handler("system"))
        self.assertIn("Encoding", result)

    def test_system_contains_timezone(self):
        result = _run(self.handler("system"))
        self.assertIn("Timezone", result)

    def test_system_contains_arch(self):
        result = _run(self.handler("system"))
        self.assertIn("Arch", result)

    def test_system_contains_cwd(self):
        result = _run(self.handler("system"))
        self.assertIn("CWD", result)

    def test_system_contains_cpus(self):
        result = _run(self.handler("system"))
        self.assertIn("CPUs", result)


if __name__ == "__main__":
    unittest.main()
