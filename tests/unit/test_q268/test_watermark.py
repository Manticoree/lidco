"""Tests for WatermarkEngine."""
from __future__ import annotations

import unittest

from lidco.dlp.watermark import Watermark, WatermarkEngine


class TestWatermark(unittest.TestCase):
    def test_frozen(self):
        w = Watermark(id="a", source="b", timestamp=1.0, signature="c")
        with self.assertRaises(AttributeError):
            w.id = "x"  # type: ignore[misc]


class TestWatermarkEngine(unittest.TestCase):
    def test_embed_returns_watermark(self):
        engine = WatermarkEngine()
        code, wm = engine.embed("print('hello')")
        self.assertIsInstance(wm, Watermark)
        self.assertEqual(wm.source, "lidco")
        self.assertGreater(len(code), len("print('hello')"))

    def test_detect_after_embed(self):
        engine = WatermarkEngine()
        code, wm = engine.embed("x = 1")
        detected = engine.detect(code)
        self.assertIsNotNone(detected)
        self.assertEqual(detected.id, wm.id)
        self.assertEqual(detected.source, wm.source)

    def test_detect_no_watermark(self):
        engine = WatermarkEngine()
        self.assertIsNone(engine.detect("plain code"))

    def test_verify_valid(self):
        engine = WatermarkEngine()
        code, wm = engine.embed("y = 2")
        self.assertTrue(engine.verify(code, wm))

    def test_verify_invalid(self):
        engine = WatermarkEngine()
        code, wm = engine.embed("z = 3")
        fake = Watermark(id="fake", source=wm.source, timestamp=wm.timestamp, signature="bad")
        self.assertFalse(engine.verify(code, fake))

    def test_strip(self):
        engine = WatermarkEngine()
        original = "def foo(): pass"
        code, _wm = engine.embed(original)
        stripped = engine.strip(code)
        self.assertEqual(stripped, original)

    def test_strip_no_watermark(self):
        engine = WatermarkEngine()
        self.assertEqual(engine.strip("clean"), "clean")

    def test_create_signature_deterministic(self):
        engine = WatermarkEngine(secret="test")
        sig1 = engine.create_signature("src", 100.0)
        sig2 = engine.create_signature("src", 100.0)
        self.assertEqual(sig1, sig2)

    def test_summary(self):
        engine = WatermarkEngine()
        engine.embed("a")
        s = engine.summary()
        self.assertEqual(s["embedded"], 1)
        self.assertEqual(s["detected"], 0)

    def test_different_secrets_different_signatures(self):
        e1 = WatermarkEngine(secret="s1")
        e2 = WatermarkEngine(secret="s2")
        sig1 = e1.create_signature("src", 100.0)
        sig2 = e2.create_signature("src", 100.0)
        self.assertNotEqual(sig1, sig2)


if __name__ == "__main__":
    unittest.main()
