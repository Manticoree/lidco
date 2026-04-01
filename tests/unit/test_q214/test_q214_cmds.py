"""Tests for cli.commands.q214_cmds — /gen-test, /property-test, /mutate, /coverage-gaps."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock


class TestQ214Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q214_cmds

        q214_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"gen-test", "property-test", "mutate", "coverage-gaps"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_all_commands_have_descriptions(self):
        for name, cmd in self.registered.items():
            self.assertIsInstance(cmd.description, str)
            self.assertTrue(len(cmd.description) > 0)

    def test_gen_test_no_args(self):
        handler = self.registered["gen-test"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_gen_test_nonexistent_file(self):
        handler = self.registered["gen-test"].handler
        result = asyncio.run(handler("/nonexistent.py"))
        self.assertIn("File not found", result)

    def test_gen_test_with_file(self):
        handler = self.registered["gen-test"].handler
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
        f.write("def add(a: int, b: int) -> int:\n    return a + b\n")
        f.close()
        try:
            result = asyncio.run(handler(f.name))
            self.assertIn("Generated", result)
            self.assertIn("test cases", result)
        finally:
            os.unlink(f.name)

    def test_gen_test_with_function_filter(self):
        handler = self.registered["gen-test"].handler
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
        f.write("def add(a: int, b: int): pass\ndef sub(a: int, b: int): pass\n")
        f.close()
        try:
            result = asyncio.run(handler(f"{f.name} add"))
            self.assertIn("Generated", result)
        finally:
            os.unlink(f.name)

    def test_property_test_no_args(self):
        handler = self.registered["property-test"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_property_test_basic(self):
        handler = self.registered["property-test"].handler
        result = asyncio.run(handler("add a:int b:int"))
        self.assertIn("Property spec", result)
        self.assertIn("add", result)

    def test_mutate_no_args(self):
        handler = self.registered["mutate"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_mutate_nonexistent(self):
        handler = self.registered["mutate"].handler
        result = asyncio.run(handler("/nonexistent.py"))
        self.assertIn("File not found", result)

    def test_mutate_with_file(self):
        handler = self.registered["mutate"].handler
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
        f.write("def check(x):\n    if x > 0:\n        return x + 1\n    return 0\n")
        f.close()
        try:
            result = asyncio.run(handler(f.name))
            self.assertIn("Mutation Report", result)
        finally:
            os.unlink(f.name)

    def test_coverage_gaps_no_args(self):
        handler = self.registered["coverage-gaps"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_coverage_gaps_nonexistent(self):
        handler = self.registered["coverage-gaps"].handler
        result = asyncio.run(handler("/nonexistent.json"))
        self.assertIn("File not found", result)

    def test_coverage_gaps_with_file(self):
        handler = self.registered["coverage-gaps"].handler
        data = {
            "files": {
                "mod.py": {
                    "missing_lines": [5, 10],
                    "missing_branches": [],
                    "complexity": {},
                }
            }
        }
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, f)
        f.close()
        try:
            result = asyncio.run(handler(f.name))
            self.assertIn("Coverage Gaps", result)
        finally:
            os.unlink(f.name)

    def test_coverage_gaps_empty(self):
        handler = self.registered["coverage-gaps"].handler
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"files": {}}, f)
        f.close()
        try:
            result = asyncio.run(handler(f.name))
            self.assertIn("No coverage gaps", result)
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
