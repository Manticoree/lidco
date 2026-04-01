"""Tests for computer_use.screenshot."""
from __future__ import annotations

import unittest

from lidco.computer_use.screenshot import ScreenRegion, ScreenshotAnalyzer, ScreenshotResult


class TestScreenshotCapture(unittest.TestCase):
    def setUp(self):
        self.analyzer = ScreenshotAnalyzer()

    def test_capture_full_screen(self):
        result = self.analyzer.capture()
        self.assertEqual(result.width, 1920)
        self.assertEqual(result.height, 1080)
        self.assertEqual(result.format, "png")

    def test_capture_region(self):
        region = ScreenRegion(x=10, y=20, width=200, height=100)
        result = self.analyzer.capture(region)
        self.assertEqual(result.width, 200)
        self.assertEqual(result.height, 100)
        self.assertIn(region, result.regions)

    def test_capture_has_timestamp(self):
        result = self.analyzer.capture()
        self.assertGreater(result.timestamp, 0)


class TestScreenshotExtractText(unittest.TestCase):
    def test_extract_text_returns_content(self):
        analyzer = ScreenshotAnalyzer()
        result = ScreenshotResult(width=100, height=100, text_content="Hello World")
        text = analyzer.extract_text(result)
        self.assertEqual(text, "Hello World")

    def test_extract_text_empty(self):
        analyzer = ScreenshotAnalyzer()
        result = ScreenshotResult(width=100, height=100)
        text = analyzer.extract_text(result)
        self.assertEqual(text, "")


class TestScreenshotFindElement(unittest.TestCase):
    def test_find_element_found(self):
        analyzer = ScreenshotAnalyzer()
        region = ScreenRegion(x=10, y=10, width=50, height=20)
        result = ScreenshotResult(
            width=100, height=100, text_content="Submit Button", regions=(region,)
        )
        found = analyzer.find_element(result, "Submit")
        self.assertIsNotNone(found)
        self.assertEqual(found, region)

    def test_find_element_not_found(self):
        analyzer = ScreenshotAnalyzer()
        result = ScreenshotResult(width=100, height=100, text_content="Hello")
        found = analyzer.find_element(result, "Cancel")
        self.assertIsNone(found)


class TestScreenshotCompare(unittest.TestCase):
    def test_compare_identical(self):
        analyzer = ScreenshotAnalyzer()
        r1 = ScreenshotResult(width=100, height=100, text_content="same")
        r2 = ScreenshotResult(width=100, height=100, text_content="same")
        self.assertEqual(analyzer.compare(r1, r2), 1.0)

    def test_compare_different_size(self):
        analyzer = ScreenshotAnalyzer()
        r1 = ScreenshotResult(width=100, height=100)
        r2 = ScreenshotResult(width=200, height=200)
        self.assertEqual(analyzer.compare(r1, r2), 0.0)

    def test_compare_partial_text(self):
        analyzer = ScreenshotAnalyzer()
        r1 = ScreenshotResult(width=100, height=100, text_content="hello world")
        r2 = ScreenshotResult(width=100, height=100, text_content="hello earth")
        score = analyzer.compare(r1, r2)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)


class TestScreenshotHistory(unittest.TestCase):
    def test_history_tracks_captures(self):
        analyzer = ScreenshotAnalyzer()
        analyzer.capture()
        analyzer.capture()
        self.assertEqual(len(analyzer.history()), 2)


if __name__ == "__main__":
    unittest.main()
