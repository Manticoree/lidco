"""Tests for Q212 CLI commands."""
from __future__ import annotations

import asyncio
import os
import tempfile
import unittest


def _run(coro):
    return asyncio.run(coro)


class _FakeRegistry:
    def __init__(self):
        self.cmds: dict = {}

    def register(self, cmd):
        self.cmds[cmd.name] = cmd


def _get_handlers():
    from lidco.cli.commands.q212_cmds import register
    reg = _FakeRegistry()
    register(reg)
    return reg.cmds


class TestDetectRefactorCommand(unittest.TestCase):
    def test_no_args(self):
        cmds = _get_handlers()
        result = _run(cmds["detect-refactor"].handler(""))
        self.assertIn("Usage", result)

    def test_with_long_method_file(self):
        cmds = _get_handlers()
        body = "\n".join(f"    x = {i}" for i in range(60))
        src = f"def big():\n{body}\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            f.flush()
            path = f.name
        try:
            result = _run(cmds["detect-refactor"].handler(path))
            self.assertIn("long_method", result)
        finally:
            os.unlink(path)


class TestExtractCommand(unittest.TestCase):
    def test_no_args(self):
        cmds = _get_handlers()
        result = _run(cmds["extract"].handler(""))
        self.assertIn("Usage", result)

    def test_extract_from_file(self):
        cmds = _get_handlers()
        src = "a = 1\nb = 2\nc = 3\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(src)
            f.flush()
            path = f.name
        try:
            result = _run(cmds["extract"].handler(f"{path} 2 2 helper"))
            self.assertIn("---", result)
        finally:
            os.unlink(path)


class TestRenameSymbolCommand(unittest.TestCase):
    def test_no_args(self):
        cmds = _get_handlers()
        result = _run(cmds["rename-symbol"].handler(""))
        self.assertIn("Usage", result)


class TestInlineCommand(unittest.TestCase):
    def test_no_args(self):
        cmds = _get_handlers()
        result = _run(cmds["inline"].handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
