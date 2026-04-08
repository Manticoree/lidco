"""Tests for lidco.cli.commands.q315_cmds — CLI wiring."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest import mock


def _sample_json() -> dict:
    return {
        "meta": {"timestamp": "2026-04-01T10:00:00"},
        "files": {
            "src/foo.py": {
                "executed_lines": [1, 2, 3, 4, 5, 6, 7, 8],
                "missing_lines": [9, 10],
                "functions": [
                    {"name": "fn_a", "start": 1, "end": 5, "hits": 3},
                    {"name": "fn_b", "start": 6, "end": 10, "hits": 0},
                ],
                "branches": [
                    {"line": 3, "branch": 0, "hits": 1},
                    {"line": 3, "branch": 1, "hits": 0},
                ],
            },
        },
    }


def _write_json(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    )
    json.dump(data, f)
    f.close()
    return f.name.replace("\\", "/")


class _FakeRegistry:
    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler: object) -> None:
        self.commands[name] = (desc, handler)


class TestRegisterQ315Commands(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q315_cmds import register_q315_commands

        self.registry = _FakeRegistry()
        register_q315_commands(self.registry)

    def test_all_commands_registered(self) -> None:
        expected = {
            "coverage-collect",
            "coverage-analyze",
            "coverage-report",
            "coverage-optimize",
        }
        self.assertEqual(set(self.registry.commands.keys()), expected)


class TestCoverageCollectHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q315_cmds import register_q315_commands

        self.registry = _FakeRegistry()
        register_q315_commands(self.registry)
        self.handler = self.registry.commands["coverage-collect"][1]

    def test_no_args(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_collect(self) -> None:
        path = _write_json(_sample_json())
        try:
            result = asyncio.run(self.handler(path))
            self.assertIn("Collected coverage", result)
            self.assertIn("Files: 1", result)
            self.assertIn("Line rate:", result)
        finally:
            os.unlink(path)

    def test_collect_with_compare(self) -> None:
        p1 = _write_json(_sample_json())
        p2 = _write_json(_sample_json())
        try:
            result = asyncio.run(self.handler(f"{p1} --compare {p2}"))
            self.assertIn("Delta", result)
            self.assertIn("Line rate change", result)
        finally:
            os.unlink(p1)
            os.unlink(p2)


class TestCoverageAnalyzeHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q315_cmds import register_q315_commands

        self.registry = _FakeRegistry()
        register_q315_commands(self.registry)
        self.handler = self.registry.commands["coverage-analyze"][1]

    def test_no_args(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_analyze(self) -> None:
        path = _write_json(_sample_json())
        try:
            result = asyncio.run(self.handler(path))
            self.assertIn("Coverage Analysis", result)
            self.assertIn("Overall risk:", result)
            self.assertIn("Uncovered functions:", result)
        finally:
            os.unlink(path)


class TestCoverageReportHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q315_cmds import register_q315_commands

        self.registry = _FakeRegistry()
        register_q315_commands(self.registry)
        self.handler = self.registry.commands["coverage-report"][1]

    def test_no_args(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_text_report(self) -> None:
        path = _write_json(_sample_json())
        try:
            result = asyncio.run(self.handler(path))
            self.assertIn("Coverage Report", result)
        finally:
            os.unlink(path)

    def test_json_report(self) -> None:
        path = _write_json(_sample_json())
        try:
            result = asyncio.run(self.handler(f"{path} --format json"))
            obj = json.loads(result)
            self.assertIn("overall", obj)
        finally:
            os.unlink(path)

    def test_html_report(self) -> None:
        path = _write_json(_sample_json())
        try:
            result = asyncio.run(self.handler(f"{path} --format html"))
            self.assertIn("<!DOCTYPE html>", result)
        finally:
            os.unlink(path)


class TestCoverageOptimizeHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q315_cmds import register_q315_commands

        self.registry = _FakeRegistry()
        register_q315_commands(self.registry)
        self.handler = self.registry.commands["coverage-optimize"][1]

    def test_no_args(self) -> None:
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_optimize(self) -> None:
        path = _write_json(_sample_json())
        try:
            result = asyncio.run(self.handler(path))
            self.assertIn("Optimization Plan", result)
            self.assertIn("Current line rate:", result)
        finally:
            os.unlink(path)

    def test_optimize_with_top(self) -> None:
        path = _write_json(_sample_json())
        try:
            result = asyncio.run(self.handler(f"{path} --top 1"))
            self.assertIn("Optimization Plan", result)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
