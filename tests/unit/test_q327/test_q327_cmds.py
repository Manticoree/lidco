"""Tests for lidco.cli.commands.q327_cmds — CLI commands."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest import mock

from lidco.cli.commands.q327_cmds import register_q327_commands


def _safe(path: str) -> str:
    """Convert Windows backslashes to forward slashes for shlex compatibility."""
    return path.replace("\\", "/")


class _FakeRegistry:
    """Minimal registry for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = (description, handler)


class TestQ327Commands(unittest.TestCase):
    """Tests for Q327 CLI command registration and handlers."""

    def setUp(self) -> None:
        self.registry = _FakeRegistry()
        register_q327_commands(self.registry)

    # -- Registration ------------------------------------------------------

    def test_all_commands_registered(self) -> None:
        expected = {"parse-log", "correlate-logs", "log-anomaly", "log-dashboard"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    # -- /parse-log --------------------------------------------------------

    def test_parse_log_no_args(self) -> None:
        handler = self.registry.commands["parse-log"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_parse_log_file_not_found(self) -> None:
        handler = self.registry.commands["parse-log"][1]
        result = asyncio.run(handler("/nonexistent/file.log"))
        self.assertIn("not found", result.lower())

    def test_parse_log_file(self) -> None:
        handler = self.registry.commands["parse-log"][1]
        content = "\n".join([
            json.dumps({"timestamp": "t1", "level": "INFO", "message": "hello"}),
            json.dumps({"timestamp": "t2", "level": "ERROR", "message": "fail"}),
        ])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            path = _safe(f.name)
        try:
            result = asyncio.run(handler(path))
            self.assertIn("Parsed", result)
            self.assertIn("2", result)
        finally:
            os.unlink(path)

    def test_parse_log_inline_text(self) -> None:
        handler = self.registry.commands["parse-log"][1]
        text = json.dumps({"timestamp": "t", "level": "INFO", "message": "hi"})
        result = asyncio.run(handler(f"--text {text}"))
        self.assertIn("Parsed", result)

    def test_parse_log_format_file_not_found(self) -> None:
        handler = self.registry.commands["parse-log"][1]
        result = asyncio.run(handler("--format json /nonexistent.log"))
        self.assertIn("not found", result.lower())

    # -- /correlate-logs ---------------------------------------------------

    def test_correlate_logs_no_args(self) -> None:
        handler = self.registry.commands["correlate-logs"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_correlate_logs_file_not_found(self) -> None:
        handler = self.registry.commands["correlate-logs"][1]
        result = asyncio.run(handler("/nonexistent/file.log"))
        self.assertIn("not found", result.lower())

    def test_correlate_logs_file(self) -> None:
        handler = self.registry.commands["correlate-logs"][1]
        content = "\n".join([
            json.dumps({"timestamp": "t1", "level": "INFO", "message": "a", "service": "api", "trace_id": "abc"}),
            json.dumps({"timestamp": "t2", "level": "INFO", "message": "b", "service": "db", "trace_id": "abc"}),
        ])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            path = _safe(f.name)
        try:
            result = asyncio.run(handler(path))
            self.assertIn("Traces:", result)
        finally:
            os.unlink(path)

    def test_correlate_logs_timeline_no_file(self) -> None:
        handler = self.registry.commands["correlate-logs"][1]
        result = asyncio.run(handler("timeline /nonexistent.log"))
        self.assertIn("not found", result.lower())

    def test_correlate_logs_root_cause_no_file(self) -> None:
        handler = self.registry.commands["correlate-logs"][1]
        result = asyncio.run(handler("root-cause /nonexistent.log abc"))
        self.assertIn("not found", result.lower())

    def test_correlate_logs_root_cause_missing_args(self) -> None:
        handler = self.registry.commands["correlate-logs"][1]
        result = asyncio.run(handler("root-cause"))
        self.assertIn("Usage", result)

    # -- /log-anomaly ------------------------------------------------------

    def test_log_anomaly_no_args(self) -> None:
        handler = self.registry.commands["log-anomaly"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_log_anomaly_file_not_found(self) -> None:
        handler = self.registry.commands["log-anomaly"][1]
        result = asyncio.run(handler("/nonexistent/file.log"))
        self.assertIn("not found", result.lower())

    def test_log_anomaly_file(self) -> None:
        handler = self.registry.commands["log-anomaly"][1]
        content = json.dumps({"timestamp": "t1", "level": "ERROR", "message": "boom"})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            path = _safe(f.name)
        try:
            result = asyncio.run(handler(path))
            self.assertIn("Entries:", result)
        finally:
            os.unlink(path)

    def test_log_anomaly_baseline_file_not_found(self) -> None:
        handler = self.registry.commands["log-anomaly"][1]
        result = asyncio.run(handler("--baseline /nonexistent.log /also_nonexistent.log"))
        self.assertIn("not found", result.lower())

    # -- /log-dashboard ----------------------------------------------------

    def test_log_dashboard_no_args(self) -> None:
        handler = self.registry.commands["log-dashboard"][1]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_log_dashboard_file_not_found(self) -> None:
        handler = self.registry.commands["log-dashboard"][1]
        result = asyncio.run(handler("/nonexistent/file.log"))
        self.assertIn("not found", result.lower())

    def test_log_dashboard_file(self) -> None:
        handler = self.registry.commands["log-dashboard"][1]
        content = "\n".join([
            json.dumps({"timestamp": "2026-01-01T12:00:00", "level": "INFO", "message": "ok", "service": "api"}),
            json.dumps({"timestamp": "2026-01-01T12:01:00", "level": "ERROR", "message": "fail", "service": "api"}),
        ])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            path = _safe(f.name)
        try:
            result = asyncio.run(handler(path))
            self.assertIn("Log Dashboard", result)
            self.assertIn("Errors:", result)
        finally:
            os.unlink(path)

    def test_log_dashboard_export_not_found(self) -> None:
        handler = self.registry.commands["log-dashboard"][1]
        result = asyncio.run(handler("export /nonexistent.log"))
        self.assertIn("not found", result.lower())

    def test_log_dashboard_drill_down_not_found(self) -> None:
        handler = self.registry.commands["log-dashboard"][1]
        result = asyncio.run(handler("drill-down /nonexistent.log --service api"))
        self.assertIn("not found", result.lower())

    def test_log_dashboard_export_json(self) -> None:
        handler = self.registry.commands["log-dashboard"][1]
        content = json.dumps({"timestamp": "t", "level": "INFO", "message": "ok"})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            path = _safe(f.name)
        try:
            result = asyncio.run(handler(f"export {path} --json"))
            parsed = json.loads(result)
            self.assertEqual(parsed["total_entries"], 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
