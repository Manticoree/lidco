"""Tests for ToastManager (Task 868)."""
from __future__ import annotations

import time
import unittest

from lidco.alerts.toast_manager import Toast, ToastManager


class TestToast(unittest.TestCase):
    def test_dataclass_defaults(self):
        t = Toast(message="hi", level="info")
        self.assertEqual(t.message, "hi")
        self.assertEqual(t.duration, 3.0)
        self.assertFalse(t.expired)

    def test_custom_duration(self):
        t = Toast(message="x", level="error", duration=10.0)
        self.assertEqual(t.duration, 10.0)


class TestToastManager(unittest.TestCase):
    def setUp(self):
        self.mgr = ToastManager(default_duration=3.0)

    def test_show_returns_toast(self):
        t = self.mgr.show("hello")
        self.assertIsInstance(t, Toast)
        self.assertEqual(t.message, "hello")
        self.assertEqual(t.level, "info")

    def test_show_custom_level(self):
        t = self.mgr.show("msg", level="error")
        self.assertEqual(t.level, "error")

    def test_show_custom_duration(self):
        t = self.mgr.show("msg", duration=10.0)
        self.assertEqual(t.duration, 10.0)

    def test_show_default_duration(self):
        t = self.mgr.show("msg")
        self.assertEqual(t.duration, 3.0)

    def test_active_non_expired(self):
        self.mgr.show("a")
        self.mgr.show("b")
        self.assertEqual(len(self.mgr.active()), 2)

    def test_active_excludes_expired(self):
        t = self.mgr.show("a")
        t.expired = True
        self.assertEqual(len(self.mgr.active()), 0)

    def test_expire_old(self):
        t = self.mgr.show("msg", duration=0.0)
        t.timestamp = time.time() - 1.0  # ensure elapsed
        self.mgr.expire_old()
        self.assertTrue(t.expired)

    def test_expire_old_keeps_fresh(self):
        t = self.mgr.show("msg", duration=999.0)
        self.mgr.expire_old()
        self.assertFalse(t.expired)

    def test_dismiss_by_index(self):
        self.mgr.show("a")
        self.mgr.show("b")
        result = self.mgr.dismiss(0)
        self.assertTrue(result)
        self.assertEqual(len(self.mgr.active()), 1)

    def test_dismiss_invalid_index(self):
        self.assertFalse(self.mgr.dismiss(99))

    def test_dismiss_all(self):
        self.mgr.show("a")
        self.mgr.show("b")
        self.mgr.dismiss_all()
        self.assertEqual(len(self.mgr.active()), 0)

    def test_render_info(self):
        t = Toast(message="hello", level="info", duration=3.0)
        result = self.mgr.render(t)
        self.assertEqual(result, "[INFO] hello (3s)")

    def test_render_warning(self):
        t = Toast(message="caution", level="warning", duration=5.0)
        result = self.mgr.render(t)
        self.assertEqual(result, "[WARNING] caution (5s)")

    def test_render_error(self):
        t = Toast(message="fail", level="error", duration=2.0)
        result = self.mgr.render(t)
        self.assertEqual(result, "[ERROR] fail (2s)")

    def test_render_success(self):
        t = Toast(message="done", level="success", duration=1.0)
        result = self.mgr.render(t)
        self.assertEqual(result, "[SUCCESS] done (1s)")

    def test_history_includes_all(self):
        self.mgr.show("a")
        self.mgr.show("b")
        self.mgr.dismiss(0)
        self.assertEqual(len(self.mgr.history), 2)

    def test_history_empty(self):
        self.assertEqual(len(self.mgr.history), 0)

    def test_custom_default_duration(self):
        mgr = ToastManager(default_duration=10.0)
        t = mgr.show("msg")
        self.assertEqual(t.duration, 10.0)

    def test_dismiss_negative_index(self):
        self.mgr.show("a")
        self.assertFalse(self.mgr.dismiss(-1))


if __name__ == "__main__":
    unittest.main()
