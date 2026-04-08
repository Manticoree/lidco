"""Tests for visual_test/capture.py — ScreenshotCapture."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lidco.visual_test.capture import (
    BUILTIN_DEVICES,
    CaptureOptions,
    CaptureResult,
    DeviceProfile,
    ScreenshotCapture,
    ViewportConfig,
    _sha256,
)


class TestViewportConfig(unittest.TestCase):
    def test_defaults(self):
        vp = ViewportConfig()
        self.assertEqual(vp.width, 1280)
        self.assertEqual(vp.height, 720)
        self.assertEqual(vp.device_scale_factor, 1.0)

    def test_custom(self):
        vp = ViewportConfig(width=800, height=600, device_scale_factor=2.0)
        self.assertEqual(vp.width, 800)
        self.assertEqual(vp.height, 600)
        self.assertEqual(vp.device_scale_factor, 2.0)

    def test_frozen(self):
        vp = ViewportConfig()
        with self.assertRaises(AttributeError):
            vp.width = 999  # type: ignore[misc]


class TestDeviceProfile(unittest.TestCase):
    def test_creation(self):
        dp = DeviceProfile(name="test", viewport=ViewportConfig())
        self.assertEqual(dp.name, "test")
        self.assertFalse(dp.is_mobile)
        self.assertFalse(dp.has_touch)
        self.assertEqual(dp.user_agent, "")

    def test_mobile_device(self):
        dp = DeviceProfile(
            name="phone", viewport=ViewportConfig(width=375, height=812),
            is_mobile=True, has_touch=True, user_agent="MobileUA",
        )
        self.assertTrue(dp.is_mobile)
        self.assertTrue(dp.has_touch)
        self.assertEqual(dp.user_agent, "MobileUA")


class TestCaptureOptions(unittest.TestCase):
    def test_defaults(self):
        opts = CaptureOptions()
        self.assertEqual(opts.url, "")
        self.assertEqual(opts.selector, "")
        self.assertIsNone(opts.device)
        self.assertFalse(opts.full_page)
        self.assertEqual(opts.timeout_ms, 30_000)

    def test_with_url(self):
        opts = CaptureOptions(url="https://example.com")
        self.assertEqual(opts.url, "https://example.com")


class TestCaptureResult(unittest.TestCase):
    def test_ok_when_no_error(self):
        r = CaptureResult(url="u", image_bytes=b"x", width=10, height=10, sha256="abc")
        self.assertTrue(r.ok)

    def test_not_ok_when_error(self):
        r = CaptureResult(url="u", image_bytes=b"", width=0, height=0, sha256="", error="fail")
        self.assertFalse(r.ok)


class TestBuiltinDevices(unittest.TestCase):
    def test_has_iphone(self):
        self.assertIn("iphone-14", BUILTIN_DEVICES)

    def test_has_desktop_hd(self):
        self.assertIn("desktop-hd", BUILTIN_DEVICES)

    def test_has_desktop_4k(self):
        self.assertIn("desktop-4k", BUILTIN_DEVICES)

    def test_has_ipad(self):
        self.assertIn("ipad-pro", BUILTIN_DEVICES)

    def test_iphone_is_mobile(self):
        self.assertTrue(BUILTIN_DEVICES["iphone-14"].is_mobile)

    def test_desktop_not_mobile(self):
        self.assertFalse(BUILTIN_DEVICES["desktop-hd"].is_mobile)


class TestSha256(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(_sha256(b"hello"), _sha256(b"hello"))

    def test_different_inputs(self):
        self.assertNotEqual(_sha256(b"a"), _sha256(b"b"))


class TestScreenshotCapture(unittest.TestCase):
    def test_init_default_dir(self):
        cap = ScreenshotCapture()
        self.assertEqual(cap.output_dir, Path(".lidco/screenshots"))

    def test_init_custom_dir(self):
        cap = ScreenshotCapture("/tmp/shots")
        self.assertEqual(cap.output_dir, Path("/tmp/shots"))

    def test_list_devices(self):
        cap = ScreenshotCapture()
        devices = cap.list_devices()
        self.assertIn("iphone-14", devices)
        self.assertEqual(devices, sorted(devices))

    def test_register_device(self):
        cap = ScreenshotCapture()
        custom = DeviceProfile(name="my-device", viewport=ViewportConfig(width=100, height=100))
        cap.register_device(custom)
        self.assertIn("my-device", cap.devices)

    def test_register_device_does_not_mutate_builtin(self):
        """Registering should not affect the BUILTIN_DEVICES dict."""
        cap = ScreenshotCapture()
        custom = DeviceProfile(name="custom99", viewport=ViewportConfig())
        cap.register_device(custom)
        self.assertNotIn("custom99", BUILTIN_DEVICES)

    @patch("lidco.visual_test.capture.sync_playwright", None)
    def test_capture_dry_run(self):
        cap = ScreenshotCapture()
        opts = CaptureOptions(url="https://example.com")
        result = cap.capture(opts)
        self.assertTrue(result.ok)
        self.assertEqual(result.url, "https://example.com")
        self.assertEqual(result.width, 1280)
        self.assertEqual(result.height, 720)
        self.assertGreater(len(result.image_bytes), 0)
        self.assertGreater(len(result.sha256), 0)

    @patch("lidco.visual_test.capture.sync_playwright", None)
    def test_capture_dry_run_with_device(self):
        cap = ScreenshotCapture()
        device = BUILTIN_DEVICES["iphone-14"]
        opts = CaptureOptions(url="https://m.example.com", device=device)
        result = cap.capture(opts)
        self.assertTrue(result.ok)
        self.assertEqual(result.width, 390)
        self.assertEqual(result.height, 844)
        self.assertEqual(result.device_name, "iphone-14")

    @patch("lidco.visual_test.capture.sync_playwright", None)
    def test_capture_multi_viewports(self):
        cap = ScreenshotCapture()
        viewports = [ViewportConfig(width=800, height=600), ViewportConfig(width=1024, height=768)]
        results = cap.capture_multi("https://example.com", viewports=viewports)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].width, 800)
        self.assertEqual(results[1].width, 1024)

    @patch("lidco.visual_test.capture.sync_playwright", None)
    def test_capture_multi_devices(self):
        cap = ScreenshotCapture()
        results = cap.capture_multi("https://example.com", device_names=["iphone-14", "desktop-hd"])
        self.assertEqual(len(results), 2)

    @patch("lidco.visual_test.capture.sync_playwright", None)
    def test_capture_multi_unknown_device(self):
        cap = ScreenshotCapture()
        results = cap.capture_multi("https://example.com", device_names=["nonexistent"])
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].ok)
        self.assertIn("Unknown device", results[0].error)

    def test_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            cap = ScreenshotCapture(output_dir=tmp)
            result = CaptureResult(
                url="https://example.com", image_bytes=b"PNG_DATA",
                width=100, height=100, sha256="abc123",
            )
            path = cap.save(result, "test_shot")
            self.assertTrue(path.exists())
            self.assertEqual(path.read_bytes(), b"PNG_DATA")
            meta_path = Path(tmp) / "test_shot.json"
            self.assertTrue(meta_path.exists())
            meta = json.loads(meta_path.read_text())
            self.assertEqual(meta["url"], "https://example.com")
            self.assertEqual(meta["sha256"], "abc123")

    @patch("lidco.visual_test.capture.sync_playwright", None)
    def test_capture_with_selector(self):
        cap = ScreenshotCapture()
        opts = CaptureOptions(url="https://example.com", selector="#main")
        result = cap.capture(opts)
        self.assertTrue(result.ok)
        self.assertEqual(result.selector, "#main")


if __name__ == "__main__":
    unittest.main()
