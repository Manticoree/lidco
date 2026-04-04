"""Tests for WebhookServer (Q298)."""
import hashlib
import hmac
import unittest

from lidco.webhooks.server import WebhookServer, WebhookEvent


class TestWebhookServer(unittest.TestCase):
    def _make(self, **kw):
        return WebhookServer(**kw)

    # -- register_endpoint -------------------------------------------

    def test_register_endpoint_stores_handler(self):
        server = self._make()
        server.register_endpoint("/hook", lambda p, h: "ok")
        self.assertIn("/hook", server._endpoints)

    def test_register_endpoint_auto_prefix_slash(self):
        server = self._make()
        server.register_endpoint("hook", lambda p, h: "ok")
        self.assertIn("/hook", server._endpoints)

    # -- verify_signature -------------------------------------------

    def test_verify_signature_valid(self):
        secret = "mysecret"
        payload = '{"key":"value"}'
        sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(WebhookServer.verify_signature(payload, sig, secret))

    def test_verify_signature_invalid(self):
        self.assertFalse(WebhookServer.verify_signature("data", "badsig", "secret"))

    def test_verify_signature_empty_secret(self):
        self.assertFalse(WebhookServer.verify_signature("data", "sig", ""))

    def test_verify_signature_empty_signature(self):
        self.assertFalse(WebhookServer.verify_signature("data", "", "secret"))

    # -- receive ----------------------------------------------------

    def test_receive_ok(self):
        server = self._make()
        server.register_endpoint("/hook", lambda p, h: {"echo": p})
        result = server.receive("/hook", {"msg": "hi"})
        self.assertEqual(result["status"], "ok")
        self.assertIn("event_id", result)
        self.assertEqual(result["result"], {"echo": {"msg": "hi"}})

    def test_receive_no_handler_dead_letter(self):
        server = self._make()
        result = server.receive("/missing", {"x": 1})
        self.assertEqual(result["status"], "dead_letter")
        self.assertEqual(len(server.dead_letter()), 1)

    def test_receive_handler_exception_dead_letter(self):
        server = self._make()
        server.register_endpoint("/err", lambda p, h: 1 / 0)
        result = server.receive("/err", {})
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(server.dead_letter()), 1)

    def test_receive_auto_prefix(self):
        server = self._make()
        server.register_endpoint("/hook", lambda p, h: "ok")
        result = server.receive("hook", {"a": 1})
        self.assertEqual(result["status"], "ok")

    # -- pending / dead_letter -------------------------------------

    def test_pending_events_after_receive(self):
        server = self._make()
        server.register_endpoint("/a", lambda p, h: "ok")
        server.receive("/a", {})
        server.receive("/a", {"x": 1})
        self.assertEqual(len(server.pending_events()), 2)

    def test_max_pending_evicts_oldest(self):
        server = self._make(max_pending=2)
        server.register_endpoint("/a", lambda p, h: "ok")
        server.receive("/a", {"n": 1})
        server.receive("/a", {"n": 2})
        server.receive("/a", {"n": 3})
        pending = server.pending_events()
        self.assertEqual(len(pending), 2)
        self.assertEqual(pending[0].payload, {"n": 2})

    def test_clear_pending(self):
        server = self._make()
        server.register_endpoint("/a", lambda p, h: "ok")
        server.receive("/a", {})
        count = server.clear_pending()
        self.assertEqual(count, 1)
        self.assertEqual(len(server.pending_events()), 0)

    def test_clear_dead_letter(self):
        server = self._make()
        server.receive("/nope", {})
        count = server.clear_dead_letter()
        self.assertEqual(count, 1)
        self.assertEqual(len(server.dead_letter()), 0)

    def test_webhook_event_has_id_and_timestamp(self):
        server = self._make()
        server.register_endpoint("/a", lambda p, h: "ok")
        server.receive("/a", {})
        ev = server.pending_events()[0]
        self.assertTrue(len(ev.id) > 0)
        self.assertGreater(ev.timestamp, 0)


if __name__ == "__main__":
    unittest.main()
