"""Tests for MobileBridge — Q189, task 1058."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.remote.mobile_bridge import MobileBridge, PairingCode, PermissionResponse
from lidco.remote.session_server import ServerInfo


def _make_info() -> ServerInfo:
    return ServerInfo(host="localhost", port=9000, token="tok", url="ws://localhost:9000")


class TestPairingCode(unittest.TestCase):
    def test_frozen(self):
        pc = PairingCode(code="ABC-DEF", expires_at=1.0, url="ws://x")
        with self.assertRaises(AttributeError):
            pc.code = "X"  # type: ignore[misc]

    def test_fields(self):
        pc = PairingCode(code="A", expires_at=2.0, url="u")
        self.assertEqual(pc.code, "A")
        self.assertEqual(pc.expires_at, 2.0)
        self.assertEqual(pc.url, "u")


class TestPermissionResponse(unittest.TestCase):
    def test_frozen(self):
        pr = PermissionResponse(granted=True, reason="ok")
        with self.assertRaises(AttributeError):
            pr.granted = False  # type: ignore[misc]

    def test_fields(self):
        pr = PermissionResponse(granted=False, reason="denied")
        self.assertFalse(pr.granted)
        self.assertEqual(pr.reason, "denied")


class TestMobileBridge(unittest.TestCase):
    def test_init(self):
        bridge = MobileBridge(_make_info())
        self.assertFalse(bridge._paired)

    def test_generate_pairing_code(self):
        bridge = MobileBridge(_make_info())
        pc = bridge.generate_pairing_code()
        self.assertIsInstance(pc, PairingCode)
        self.assertIn("-", pc.code)
        self.assertGreater(pc.expires_at, time.time())
        self.assertIn("pair?code=", pc.url)

    def test_verify_valid_code(self):
        bridge = MobileBridge(_make_info())
        pc = bridge.generate_pairing_code()
        self.assertTrue(bridge.verify_pairing(pc.code))
        self.assertTrue(bridge._paired)

    def test_verify_invalid_code(self):
        bridge = MobileBridge(_make_info())
        self.assertFalse(bridge.verify_pairing("INVALID"))

    def test_verify_expired_code(self):
        bridge = MobileBridge(_make_info())
        pc = bridge.generate_pairing_code()
        # Manually expire
        expired = PairingCode(code=pc.code, expires_at=time.time() - 1, url=pc.url)
        bridge._active_codes[pc.code] = expired
        self.assertFalse(bridge.verify_pairing(pc.code))

    def test_send_notification_not_paired(self):
        bridge = MobileBridge(_make_info())
        self.assertFalse(bridge.send_notification("Title", "Body"))

    def test_send_notification_paired(self):
        bridge = MobileBridge(_make_info())
        pc = bridge.generate_pairing_code()
        bridge.verify_pairing(pc.code)
        self.assertTrue(bridge.send_notification("Alert", "Something happened"))
        self.assertEqual(len(bridge._notifications), 1)

    def test_relay_permission_not_paired(self):
        bridge = MobileBridge(_make_info())
        resp = bridge.relay_permission("delete file?")
        self.assertIsInstance(resp, PermissionResponse)
        self.assertFalse(resp.granted)
        self.assertEqual(resp.reason, "Not paired")

    def test_relay_permission_paired(self):
        bridge = MobileBridge(_make_info())
        pc = bridge.generate_pairing_code()
        bridge.verify_pairing(pc.code)
        resp = bridge.relay_permission("run command?")
        self.assertTrue(resp.granted)
        self.assertIn("User approved", resp.reason)

    def test_verify_removes_code(self):
        bridge = MobileBridge(_make_info())
        pc = bridge.generate_pairing_code()
        bridge.verify_pairing(pc.code)
        # Second verify should fail since code was consumed
        self.assertFalse(bridge.verify_pairing(pc.code))

    def test_multiple_notifications(self):
        bridge = MobileBridge(_make_info())
        pc = bridge.generate_pairing_code()
        bridge.verify_pairing(pc.code)
        bridge.send_notification("A", "1")
        bridge.send_notification("B", "2")
        self.assertEqual(len(bridge._notifications), 2)

    def test_pairing_ttl_default(self):
        self.assertEqual(MobileBridge.PAIRING_TTL, 300.0)

    def test_code_format(self):
        bridge = MobileBridge(_make_info())
        pc = bridge.generate_pairing_code()
        parts = pc.code.split("-")
        self.assertEqual(len(parts), 2)
        self.assertEqual(len(parts[0]), 3)
        self.assertEqual(len(parts[1]), 3)


if __name__ == "__main__":
    unittest.main()
