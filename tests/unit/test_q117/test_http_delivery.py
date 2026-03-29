"""Tests for HttpHookDelivery (Task 720)."""
import io
import json
import unittest

from lidco.hooks.event_bus import HookEvent
from lidco.hooks.http_delivery import (
    HttpHookConfig,
    HttpHookDelivery,
    HttpDeliveryResult,
)


def _evt(**payload) -> HookEvent:
    return HookEvent(event_type="test", payload=payload)


class _MockResponse:
    """Mock urllib response."""

    def __init__(self, status=200, body="", headers=None):
        self.status = status
        self._body = body

    def getcode(self):
        return self.status

    def read(self):
        return self._body.encode("utf-8")


class TestHttpHookConfig(unittest.TestCase):
    def test_defaults(self):
        c = HttpHookConfig(url="http://example.com")
        self.assertEqual(c.method, "POST")
        self.assertEqual(c.headers, {})
        self.assertEqual(c.timeout_s, 5.0)
        self.assertEqual(c.retry_count, 2)

    def test_custom(self):
        c = HttpHookConfig(url="http://x", method="PUT", timeout_s=1.0, retry_count=0)
        self.assertEqual(c.method, "PUT")
        self.assertEqual(c.retry_count, 0)


class TestHttpDeliveryResult(unittest.TestCase):
    def test_success(self):
        r = HttpDeliveryResult(status_code=200, response_body="ok", success=True)
        self.assertTrue(r.success)
        self.assertEqual(r.error, "")

    def test_failure(self):
        r = HttpDeliveryResult(status_code=0, response_body="", success=False, error="timeout")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "timeout")


class TestDeliverSuccess(unittest.TestCase):
    def test_basic_delivery(self):
        mock = lambda req, timeout=5: _MockResponse(200, '{"ok":true}')
        config = HttpHookConfig(url="http://hook.example.com/endpoint")
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        result = delivery.deliver(_evt(msg="hi"))
        self.assertTrue(result.success)
        self.assertEqual(result.status_code, 200)

    def test_response_body_captured(self):
        mock = lambda req, timeout=5: _MockResponse(200, "response text")
        config = HttpHookConfig(url="http://x")
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        result = delivery.deliver(_evt())
        self.assertEqual(result.response_body, "response text")

    def test_sends_json_payload(self):
        captured = {}

        def mock(req, timeout=5):
            captured["body"] = req.data.decode("utf-8")
            captured["content_type"] = req.get_header("Content-type")
            return _MockResponse(200, "")

        config = HttpHookConfig(url="http://x")
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        delivery.deliver(_evt(key="value"))
        self.assertEqual(json.loads(captured["body"]), {"key": "value"})
        self.assertEqual(captured["content_type"], "application/json")

    def test_uses_configured_method(self):
        captured = {}

        def mock(req, timeout=5):
            captured["method"] = req.get_method()
            return _MockResponse(200, "")

        config = HttpHookConfig(url="http://x", method="PUT")
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        delivery.deliver(_evt())
        self.assertEqual(captured["method"], "PUT")

    def test_custom_headers_included(self):
        captured = {}

        def mock(req, timeout=5):
            captured["auth"] = req.get_header("Authorization")
            return _MockResponse(200, "")

        config = HttpHookConfig(url="http://x", headers={"Authorization": "Bearer tok"})
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        delivery.deliver(_evt())
        self.assertEqual(captured["auth"], "Bearer tok")

    def test_timeout_passed(self):
        captured = {}

        def mock(req, timeout=5):
            captured["timeout"] = timeout
            return _MockResponse(200, "")

        config = HttpHookConfig(url="http://x", timeout_s=2.5)
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        delivery.deliver(_evt())
        self.assertEqual(captured["timeout"], 2.5)


class TestDeliverFailure(unittest.TestCase):
    def test_network_error_returns_failure(self):
        def mock(req, timeout=5):
            raise ConnectionError("refused")

        config = HttpHookConfig(url="http://x", retry_count=0)
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        result = delivery.deliver(_evt())
        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 0)
        self.assertIn("refused", result.error)

    def test_never_raises(self):
        def mock(req, timeout=5):
            raise RuntimeError("boom")

        config = HttpHookConfig(url="http://x", retry_count=0)
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        # Should not raise
        result = delivery.deliver(_evt())
        self.assertFalse(result.success)

    def test_500_response(self):
        mock = lambda req, timeout=5: _MockResponse(500, "error")
        config = HttpHookConfig(url="http://x", retry_count=0)
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        result = delivery.deliver(_evt())
        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 500)


class TestRetry(unittest.TestCase):
    def test_retries_on_error(self):
        call_count = [0]

        def mock(req, timeout=5):
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("fail")
            return _MockResponse(200, "ok")

        config = HttpHookConfig(url="http://x", retry_count=2)
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        result = delivery.deliver(_evt())
        self.assertTrue(result.success)
        self.assertEqual(call_count[0], 3)

    def test_exhausts_retries(self):
        call_count = [0]

        def mock(req, timeout=5):
            call_count[0] += 1
            raise ConnectionError("always fail")

        config = HttpHookConfig(url="http://x", retry_count=2)
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        result = delivery.deliver(_evt())
        self.assertFalse(result.success)
        self.assertEqual(call_count[0], 3)  # 1 + 2 retries

    def test_zero_retries(self):
        call_count = [0]

        def mock(req, timeout=5):
            call_count[0] += 1
            raise ConnectionError("fail")

        config = HttpHookConfig(url="http://x", retry_count=0)
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        result = delivery.deliver(_evt())
        self.assertFalse(result.success)
        self.assertEqual(call_count[0], 1)

    def test_no_retry_on_success(self):
        call_count = [0]

        def mock(req, timeout=5):
            call_count[0] += 1
            return _MockResponse(200, "")

        config = HttpHookConfig(url="http://x", retry_count=3)
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        result = delivery.deliver(_evt())
        self.assertTrue(result.success)
        self.assertEqual(call_count[0], 1)


class TestAsHookHandler(unittest.TestCase):
    def test_returns_callable(self):
        config = HttpHookConfig(url="http://x")
        delivery = HttpHookDelivery(config, urlopen_fn=lambda r, timeout=5: _MockResponse(200, ""))
        handler = delivery.as_hook_handler()
        self.assertTrue(callable(handler))

    def test_handler_calls_deliver(self):
        delivered = []

        def mock(req, timeout=5):
            delivered.append(req.data)
            return _MockResponse(200, "")

        config = HttpHookConfig(url="http://x")
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        handler = delivery.as_hook_handler()
        handler(_evt(a=1))
        self.assertEqual(len(delivered), 1)

    def test_handler_does_not_raise(self):
        def mock(req, timeout=5):
            raise RuntimeError("fail")

        config = HttpHookConfig(url="http://x", retry_count=0)
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        handler = delivery.as_hook_handler()
        # Should not raise
        handler(_evt())


class TestEdgeCases(unittest.TestCase):
    def test_empty_payload(self):
        mock = lambda req, timeout=5: _MockResponse(200, "")
        config = HttpHookConfig(url="http://x")
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        result = delivery.deliver(HookEvent(event_type="t", payload={}))
        self.assertTrue(result.success)

    def test_large_payload(self):
        mock = lambda req, timeout=5: _MockResponse(200, "")
        config = HttpHookConfig(url="http://x")
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        big = {f"key_{i}": f"value_{i}" for i in range(1000)}
        result = delivery.deliver(HookEvent(event_type="t", payload=big))
        self.assertTrue(result.success)

    def test_special_chars_in_payload(self):
        captured = {}

        def mock(req, timeout=5):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _MockResponse(200, "")

        config = HttpHookConfig(url="http://x")
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        delivery.deliver(_evt(msg='hello "world" <>&'))
        self.assertEqual(captured["body"]["msg"], 'hello "world" <>&')


class TestDefaultUrlopen(unittest.TestCase):
    def test_default_urlopen_used(self):
        """Verify that without urlopen_fn, urllib.request.urlopen is the default."""
        config = HttpHookConfig(url="http://x")
        delivery = HttpHookDelivery(config)
        import urllib.request
        self.assertIs(delivery._urlopen_fn, urllib.request.urlopen)

    def test_unicode_payload(self):
        captured = {}

        def mock(req, timeout=5):
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return _MockResponse(200, "")

        config = HttpHookConfig(url="http://x")
        delivery = HttpHookDelivery(config, urlopen_fn=mock)
        delivery.deliver(_evt(msg="cafe\u0301"))
        self.assertIn("caf", captured["body"]["msg"])


if __name__ == "__main__":
    unittest.main()
