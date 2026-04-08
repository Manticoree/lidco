"""Tests for Q309 CLI commands."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class _FakeRegistry:
    """Minimal registry to capture registrations."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = handler


def _build_registry() -> _FakeRegistry:
    from lidco.cli.commands.q309_cmds import register_q309_commands
    reg = _FakeRegistry()
    register_q309_commands(reg)
    return reg


class TestQ309Registration(unittest.TestCase):
    def test_registers_visual_capture(self):
        reg = _build_registry()
        self.assertIn("visual-capture", reg.commands)

    def test_registers_visual_diff(self):
        reg = _build_registry()
        self.assertIn("visual-diff", reg.commands)

    def test_registers_visual_baseline(self):
        reg = _build_registry()
        self.assertIn("visual-baseline", reg.commands)

    def test_registers_visual_report(self):
        reg = _build_registry()
        self.assertIn("visual-report", reg.commands)

    def test_four_commands_registered(self):
        reg = _build_registry()
        self.assertEqual(len(reg.commands), 4)


class TestVisualCaptureHandler(unittest.TestCase):
    def test_no_args_shows_usage(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-capture"](""))
        self.assertIn("Usage", result)

    def test_devices_subcommand(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-capture"]("devices"))
        self.assertIn("iphone-14", result)
        self.assertIn("desktop-hd", result)

    @patch("lidco.visual_test.capture.sync_playwright", None)
    def test_capture_url_dry_run(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-capture"]("https://example.com"))
        self.assertIn("Captured", result)
        self.assertIn("https://example.com", result)
        self.assertIn("SHA256", result)


class TestVisualDiffHandler(unittest.TestCase):
    def test_no_args_shows_usage(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-diff"](""))
        self.assertIn("Usage", result)

    def test_one_arg_shows_usage(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-diff"]("file1.png"))
        self.assertIn("Usage", result)

    def test_missing_baseline(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-diff"]("/nonexistent/a.png /nonexistent/b.png"))
        self.assertIn("not found", result.lower())

    def test_compare_identical_files(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(bytes([100, 100, 100, 255] * 4))
            f.flush()
            path = f.name
        try:
            reg = _build_registry()
            # Use forward slashes + quoting so shlex.split works on Windows
            fwd = path.replace("\\", "/")
            result = asyncio.run(reg.commands["visual-diff"](f'"{fwd}" "{fwd}"'))
            self.assertIn("MATCH", result)
        finally:
            Path(path).unlink(missing_ok=True)


class TestVisualBaselineHandler(unittest.TestCase):
    def test_no_args_shows_usage(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-baseline"](""))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lidco.visual_test.baseline.BaselineManager.__init__",
                        lambda self, **kw: setattr(self, '_storage_dir', Path(tmp)) or
                        setattr(self, '_entries', {}) or setattr(self, '_pending', [])):
                reg = _build_registry()
                result = asyncio.run(reg.commands["visual-baseline"]("list"))
                self.assertIn("No baselines", result)

    def test_pending_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lidco.visual_test.baseline.BaselineManager.__init__",
                        lambda self, **kw: setattr(self, '_storage_dir', Path(tmp)) or
                        setattr(self, '_entries', {}) or setattr(self, '_pending', [])):
                reg = _build_registry()
                result = asyncio.run(reg.commands["visual-baseline"]("pending"))
                self.assertIn("No pending", result)

    def test_unknown_subcommand(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-baseline"]("unknown"))
        self.assertIn("Unknown subcommand", result)

    def test_store_missing_file(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-baseline"]("store test main /nonexistent.png"))
        self.assertIn("not found", result.lower())


class TestVisualReportHandler(unittest.TestCase):
    def test_no_args_shows_usage(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-report"](""))
        self.assertIn("Usage", result)

    def test_summary(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-report"]("summary"))
        self.assertIn("Total: 0", result)

    def test_generate(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("lidco.visual_test.report.ReportConfig.__init__",
                        return_value=None) as mock_init:
                # Just test that generate doesn't crash with defaults
                reg = _build_registry()
                result = asyncio.run(reg.commands["visual-report"]("generate"))
                self.assertIn("Report generated", result)

    def test_json_export(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-report"]("json"))
        self.assertIn("JSON report saved", result)

    def test_unknown_subcommand(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-report"]("unknown"))
        self.assertIn("Unknown subcommand", result)

    def test_generate_with_ci_flag(self):
        reg = _build_registry()
        result = asyncio.run(reg.commands["visual-report"]("generate --ci"))
        self.assertIn("CI exit code", result)


if __name__ == "__main__":
    unittest.main()
