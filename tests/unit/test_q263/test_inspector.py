"""Tests for RequestInspector (Q263)."""
from __future__ import annotations

import unittest

from lidco.netsec.inspector import InspectedRequest, RequestInspector


class TestInspectedRequest(unittest.TestCase):
    def test_frozen(self):
        r = InspectedRequest(id="abc", url="http://x.com", method="GET", host="x.com", timestamp=0.0)
        with self.assertRaises(AttributeError):
            r.url = "http://y.com"  # type: ignore[misc]

    def test_defaults(self):
        r = InspectedRequest(id="1", url="http://a.com", method="GET", host="a.com", timestamp=1.0)
        self.assertFalse(r.blocked)
        self.assertEqual(r.reason, "")


class TestInspectBasic(unittest.TestCase):
    def test_inspect_allowed(self):
        inspector = RequestInspector()
        req = inspector.inspect("https://api.openai.com/v1/chat")
        self.assertFalse(req.blocked)
        self.assertEqual(req.host, "api.openai.com")
        self.assertEqual(req.method, "GET")

    def test_inspect_blocked(self):
        inspector = RequestInspector(blocked_hosts=["evil.com"])
        req = inspector.inspect("https://evil.com/steal")
        self.assertTrue(req.blocked)
        self.assertIn("evil.com", req.reason)

    def test_inspect_method(self):
        inspector = RequestInspector()
        req = inspector.inspect("https://example.com", method="post")
        self.assertEqual(req.method, "POST")


class TestBlockedPatterns(unittest.TestCase):
    def test_add_blocked(self):
        inspector = RequestInspector()
        inspector.add_blocked("malware.org")
        self.assertTrue(inspector.is_blocked("malware.org"))

    def test_remove_blocked(self):
        inspector = RequestInspector(blocked_hosts=["bad.com"])
        self.assertTrue(inspector.remove_blocked("bad.com"))
        self.assertFalse(inspector.is_blocked("bad.com"))

    def test_remove_nonexistent(self):
        inspector = RequestInspector()
        self.assertFalse(inspector.remove_blocked("nope.com"))

    def test_glob_pattern(self):
        inspector = RequestInspector(blocked_hosts=["*.evil.com"])
        self.assertTrue(inspector.is_blocked("sub.evil.com"))
        self.assertFalse(inspector.is_blocked("good.com"))

    def test_substring_match(self):
        inspector = RequestInspector(blocked_hosts=["evil"])
        self.assertTrue(inspector.is_blocked("evil.com"))
        self.assertTrue(inspector.is_blocked("super-evil.org"))


class TestHistory(unittest.TestCase):
    def test_history_limit(self):
        inspector = RequestInspector()
        for i in range(10):
            inspector.inspect(f"https://host{i}.com")
        self.assertEqual(len(inspector.history(limit=5)), 5)

    def test_blocked_requests_filter(self):
        inspector = RequestInspector(blocked_hosts=["bad.com"])
        inspector.inspect("https://good.com")
        inspector.inspect("https://bad.com")
        inspector.inspect("https://ok.com")
        blocked = inspector.blocked_requests()
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0].host, "bad.com")

    def test_clear_history(self):
        inspector = RequestInspector()
        inspector.inspect("https://a.com")
        inspector.inspect("https://b.com")
        count = inspector.clear_history()
        self.assertEqual(count, 2)
        self.assertEqual(len(inspector.history()), 0)

    def test_summary(self):
        inspector = RequestInspector(blocked_hosts=["bad.com"])
        inspector.inspect("https://good.com")
        inspector.inspect("https://bad.com")
        s = inspector.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["blocked_count"], 1)
        self.assertEqual(s["unique_hosts"], 2)


if __name__ == "__main__":
    unittest.main()
