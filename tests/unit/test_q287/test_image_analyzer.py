"""Tests for lidco.multimodal.image_analyzer."""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from lidco.multimodal.image_analyzer import (
    ImageAnalyzer,
    AnalysisResult,
    DiffResult,
    UIElement,
)


class TestImageAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = ImageAnalyzer(use_pil=False)

    # -- analyze ----------------------------------------------------------

    def test_analyze_returns_result(self):
        with patch("os.path.getsize", return_value=4096):
            result = self.analyzer.analyze("shot.png")
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.path, "shot.png")
        self.assertGreater(result.width, 0)
        self.assertGreater(result.height, 0)

    def test_analyze_png_labels(self):
        with patch("os.path.getsize", return_value=1000):
            result = self.analyzer.analyze("test.png")
        self.assertIn("screenshot", result.labels)
        self.assertIn("has-content", result.labels)

    def test_analyze_jpg_labels(self):
        with patch("os.path.getsize", return_value=500):
            result = self.analyzer.analyze("photo.jpg")
        self.assertIn("photo", result.labels)

    def test_analyze_empty_path_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.analyze("")

    def test_analyze_confidence(self):
        with patch("os.path.getsize", return_value=100):
            result = self.analyzer.analyze("x.png")
        self.assertGreater(result.confidence, 0)

    # -- detect_elements --------------------------------------------------

    def test_detect_elements_returns_list(self):
        with patch("os.path.getsize", return_value=2000):
            elements = self.analyzer.detect_elements("ui.png")
        self.assertIsInstance(elements, list)
        self.assertGreater(len(elements), 0)
        self.assertIsInstance(elements[0], UIElement)

    def test_detect_elements_has_button(self):
        with patch("os.path.getsize", return_value=2000):
            elements = self.analyzer.detect_elements("ui.png")
        kinds = [e.kind for e in elements]
        self.assertIn("button", kinds)

    def test_detect_elements_empty_path_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.detect_elements("")

    # -- diff_screenshots -------------------------------------------------

    def test_diff_identical(self):
        with patch("builtins.open", MagicMock()):
            with patch("lidco.multimodal.image_analyzer.ImageAnalyzer._content_hash", return_value="abc"):
                with patch("os.path.getsize", return_value=100):
                    diff = self.analyzer.diff_screenshots("a.png", "b.png")
        self.assertIsInstance(diff, DiffResult)
        self.assertEqual(diff.similarity, 1.0)
        self.assertEqual(len(diff.changed_regions), 0)

    def test_diff_different(self):
        hashes = iter(["abc", "def"])
        with patch("lidco.multimodal.image_analyzer.ImageAnalyzer._content_hash", side_effect=hashes):
            with patch("os.path.getsize", return_value=100):
                diff = self.analyzer.diff_screenshots("a.png", "b.png")
        self.assertLess(diff.similarity, 1.0)
        self.assertGreater(len(diff.changed_regions), 0)

    def test_diff_empty_paths_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.diff_screenshots("", "b.png")
        with self.assertRaises(ValueError):
            self.analyzer.diff_screenshots("a.png", "")

    # -- describe ---------------------------------------------------------

    def test_describe_png(self):
        with patch("os.path.getsize", return_value=500):
            desc = self.analyzer.describe("shot.png")
        self.assertIn("screenshot", desc)
        self.assertIn("shot.png", desc)

    def test_describe_jpg(self):
        with patch("os.path.getsize", return_value=500):
            desc = self.analyzer.describe("photo.jpg")
        self.assertIn("image", desc)

    def test_describe_empty_path_raises(self):
        with self.assertRaises(ValueError):
            self.analyzer.describe("")

    # -- PIL integration --------------------------------------------------

    def test_with_pil(self):
        mock_img = MagicMock()
        mock_img.width = 1920
        mock_img.height = 1080
        mock_img.format = "PNG"
        mock_img.mode = "RGBA"
        with patch("lidco.multimodal.image_analyzer.Image") as mock_pil:
            mock_pil.open.return_value = mock_img
            analyzer = ImageAnalyzer(use_pil=True)
            # Force _use_pil to True since Image mock is truthy
            analyzer._use_pil = True
            result = analyzer.analyze("hd.png")
        self.assertEqual(result.width, 1920)
        self.assertEqual(result.height, 1080)


if __name__ == "__main__":
    unittest.main()
