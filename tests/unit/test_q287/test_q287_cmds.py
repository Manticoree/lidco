"""Tests for lidco.cli.commands.q287_cmds."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from lidco.cli.commands.q287_cmds import register_q287_commands


class _FakeRegistry:
    """Minimal registry that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ287Commands(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q287_commands(self.registry)

    def test_commands_registered(self):
        names = set(self.registry.commands.keys())
        self.assertIn("analyze-image", names)
        self.assertIn("gen-diagram", names)
        self.assertIn("transcribe", names)
        self.assertIn("analyze-pdf", names)

    # -- /analyze-image ---------------------------------------------------

    def test_analyze_image_empty(self):
        handler = self.registry.commands["analyze-image"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_analyze_image_default(self):
        handler = self.registry.commands["analyze-image"].handler
        with patch("os.path.getsize", return_value=2000):
            result = asyncio.run(handler("shot.png"))
        self.assertIn("Image", result)
        self.assertIn("Format", result)

    def test_analyze_image_detect(self):
        handler = self.registry.commands["analyze-image"].handler
        with patch("os.path.getsize", return_value=2000):
            result = asyncio.run(handler("ui.png detect"))
        self.assertIn("Detected", result)
        self.assertIn("button", result)

    def test_analyze_image_describe(self):
        handler = self.registry.commands["analyze-image"].handler
        with patch("os.path.getsize", return_value=500):
            result = asyncio.run(handler("x.png describe"))
        self.assertIn("screenshot", result)

    def test_analyze_image_diff(self):
        handler = self.registry.commands["analyze-image"].handler
        hashes = iter(["aaa", "bbb"])
        with patch("lidco.multimodal.image_analyzer.ImageAnalyzer._content_hash", side_effect=hashes):
            with patch("os.path.getsize", return_value=100):
                result = asyncio.run(handler("a.png diff b.png"))
        self.assertIn("Similarity", result)

    # -- /gen-diagram -----------------------------------------------------

    def test_gen_diagram_empty(self):
        handler = self.registry.commands["gen-diagram"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_gen_diagram_class(self):
        handler = self.registry.commands["gen-diagram"].handler
        result = asyncio.run(handler("class"))
        self.assertIn("classDiagram", result)

    def test_gen_diagram_sequence(self):
        handler = self.registry.commands["gen-diagram"].handler
        result = asyncio.run(handler("sequence"))
        self.assertIn("sequenceDiagram", result)

    def test_gen_diagram_arch(self):
        handler = self.registry.commands["gen-diagram"].handler
        result = asyncio.run(handler("arch"))
        self.assertIn("flowchart TD", result)

    # -- /transcribe ------------------------------------------------------

    def test_transcribe_empty(self):
        handler = self.registry.commands["transcribe"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_transcribe_full(self):
        handler = self.registry.commands["transcribe"].handler
        result = asyncio.run(handler("meeting.wav"))
        self.assertIn("Transcript", result)
        self.assertIn("Duration", result)

    def test_transcribe_actions(self):
        handler = self.registry.commands["transcribe"].handler
        result = asyncio.run(handler("meeting.wav actions"))
        self.assertIn("Action items", result)

    def test_transcribe_speakers(self):
        handler = self.registry.commands["transcribe"].handler
        result = asyncio.run(handler("call.mp3 speakers"))
        self.assertIn("Speakers", result)

    # -- /analyze-pdf -----------------------------------------------------

    def test_analyze_pdf_empty(self):
        handler = self.registry.commands["analyze-pdf"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_analyze_pdf_text(self):
        handler = self.registry.commands["analyze-pdf"].handler
        result = asyncio.run(handler("doc.pdf"))
        self.assertIn("Page 1", result)

    def test_analyze_pdf_tables(self):
        handler = self.registry.commands["analyze-pdf"].handler
        result = asyncio.run(handler("data.pdf tables"))
        self.assertIn("table", result.lower())

    def test_analyze_pdf_spec(self):
        handler = self.registry.commands["analyze-pdf"].handler
        result = asyncio.run(handler("api.pdf spec"))
        self.assertIn("Spec", result)

    def test_analyze_pdf_summary(self):
        handler = self.registry.commands["analyze-pdf"].handler
        result = asyncio.run(handler("report.pdf summary"))
        self.assertIn("Summary", result)

    def test_analyze_pdf_pages(self):
        handler = self.registry.commands["analyze-pdf"].handler
        result = asyncio.run(handler("big.pdf pages 2-3"))
        self.assertIn("Page 2", result)
        self.assertIn("Page 3", result)


if __name__ == "__main__":
    unittest.main()
