"""Tests for WebhookClient (Q298)."""
import hashlib
import hmac
import json
import unittest
from unittest.mock import MagicMock, patch

from lidco.webhooks.client import WebhookClient, DeliveryRecord


class TestWebhookClient(unittest.TestCase):
    def _make(self, **kw):
        return WebhookClient(**kw)

    # -- sign_payload --------------------------------------------

    def test_sign_payload_deterministic(self):
        payload = {"key": "value"}
        secret = "s3cret"
        sig1 = WebhookClient.sign_payload(payload, secret)
        sig2 = WebhookClient.sign_payload(payload, secret)
        self.assertEqual(sig1, sig2)

    def test_sign_payload_different_secrets(self):
        payload = {"a": 1}
        sig1 = WebhookClient.sign_payload(payload, "secret1")
        sig2 = WebhookClient.sign_payload(payload, "secret2")
        self.assertNotEqual(sig1, sig2)

    def test_sign_payload_matches_hmac(self):
        payload = {"x": "y"}
        secret = "mysecret"
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(WebhookClient.sign_payload(payload, secret), expected)

    # -- send (mocked) -------------------------------------------

    @patch("lidco.webhooks.client.urllib.request.urlopen")
    def test_send_success(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b'{"ok":true}'
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        client = self._make()
        result = client.send("http://example.com/hook", {"msg": "hi"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["body"], '{"ok":true}')

    @patch("lidco.webhooks.client.urllib.request.urlopen")
    def test_send_failure(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("connection refused")
        client = self._make()
        result = client.send("http://example.com/hook", {})
        self.assertEqual(result["status"], "error")
        self.assertIn("connection refused", result["error"])

    @patch("lidco.webhooks.client.urllib.request.urlopen")
    def test_send_with_secret_adds_signature(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"{}"
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        client = self._make(default_secret="key123")
        result = client.send("http://example.com/hook", {"a": 1})
        self.assertTrue(len(result["signature"]) > 0)

    @patch("lidco.webhooks.client.urllib.request.urlopen")
    def test_send_no_secret_empty_signature(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"{}"
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        client = self._make()
        result = client.send("http://example.com/hook", {})
        self.assertEqual(result["signature"], "")

    # -- delivery_log --------------------------------------------

    @patch("lidco.webhooks.client.urllib.request.urlopen")
    def test_delivery_log_records(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"{}"
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        client = self._make()
        client.send("http://a.com", {})
        client.send("http://b.com", {})
        self.assertEqual(len(client.delivery_log()), 2)

    @patch("lidco.webhooks.client.urllib.request.urlopen")
    def test_clear_log(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b"{}"
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        client = self._make()
        client.send("http://a.com", {})
        count = client.clear_log()
        self.assertEqual(count, 1)
        self.assertEqual(len(client.delivery_log()), 0)

    # -- with_retry (mocked) ------------------------------------

    @patch("lidco.webhooks.client.urllib.request.urlopen")
    def test_with_retry_succeeds_first_try(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = b'{"ok":1}'
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        client = self._make()
        result = client.with_retry("http://a.com", {}, max_retries=3)
        self.assertEqual(result["status"], "ok")

    @patch("lidco.webhooks.client.time.sleep")
    @patch("lidco.webhooks.client.urllib.request.urlopen")
    def test_with_retry_retries_on_failure(self, mock_urlopen, mock_sleep):
        mock_urlopen.side_effect = Exception("fail")
        client = self._make()
        result = client.with_retry("http://a.com", {}, max_retries=3)
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(client.delivery_log()), 3)

    # -- DeliveryRecord -----------------------------------------

    def test_delivery_record_auto_timestamp(self):
        r = DeliveryRecord(url="http://a.com", payload={}, status="ok")
        self.assertGreater(r.timestamp, 0)


if __name__ == "__main__":
    unittest.main()
