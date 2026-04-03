"""Tests for ProxyManager (Q263)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from lidco.netsec.proxy import ProxyConfig, ProxyManager


class TestProxyConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = ProxyConfig(name="test", url="http://proxy:8080")
        self.assertEqual(cfg.proxy_type, "http")
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.providers, [])


class TestProxyManagerCRUD(unittest.TestCase):
    def test_add_and_list(self):
        mgr = ProxyManager()
        cfg = ProxyConfig(name="corp", url="http://corp-proxy:3128")
        mgr.add(cfg)
        self.assertEqual(len(mgr.all_configs()), 1)

    def test_remove(self):
        mgr = ProxyManager()
        mgr.add(ProxyConfig(name="p1", url="http://p1:80"))
        self.assertTrue(mgr.remove("p1"))
        self.assertFalse(mgr.remove("p1"))

    def test_overwrite(self):
        mgr = ProxyManager()
        mgr.add(ProxyConfig(name="p1", url="http://old:80"))
        mgr.add(ProxyConfig(name="p1", url="http://new:80"))
        configs = mgr.all_configs()
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].url, "http://new:80")


class TestProxyLookup(unittest.TestCase):
    def test_get_for_provider(self):
        mgr = ProxyManager()
        mgr.add(ProxyConfig(name="openai", url="http://p:80", providers=["openai", "anthropic"]))
        self.assertIsNotNone(mgr.get_for_provider("openai"))
        self.assertIsNone(mgr.get_for_provider("google"))

    def test_get_for_provider_disabled(self):
        mgr = ProxyManager()
        mgr.add(ProxyConfig(name="p1", url="http://p:80", providers=["openai"], enabled=False))
        self.assertIsNone(mgr.get_for_provider("openai"))

    def test_get_for_url_fallback(self):
        mgr = ProxyManager()
        mgr.add(ProxyConfig(name="default", url="http://proxy:80"))
        result = mgr.get_for_url("https://api.openai.com/v1")
        self.assertIsNotNone(result)

    def test_get_for_url_none(self):
        mgr = ProxyManager()
        self.assertIsNone(mgr.get_for_url("https://example.com"))


class TestProxyEnableDisable(unittest.TestCase):
    def test_disable_and_enable(self):
        mgr = ProxyManager()
        mgr.add(ProxyConfig(name="p1", url="http://p:80"))
        self.assertTrue(mgr.disable("p1"))
        self.assertFalse(mgr.all_configs()[0].enabled)
        self.assertTrue(mgr.enable("p1"))
        self.assertTrue(mgr.all_configs()[0].enabled)

    def test_enable_nonexistent(self):
        mgr = ProxyManager()
        self.assertFalse(mgr.enable("nope"))
        self.assertFalse(mgr.disable("nope"))


class TestDetectEnv(unittest.TestCase):
    @patch.dict("os.environ", {"HTTP_PROXY": "http://envproxy:3128"}, clear=False)
    def test_detect_http_proxy(self):
        mgr = ProxyManager()
        detected = mgr.detect_env()
        names = [c.name for c in detected]
        self.assertIn("http_proxy", names)

    @patch.dict("os.environ", {}, clear=True)
    def test_detect_empty(self):
        mgr = ProxyManager()
        detected = mgr.detect_env()
        self.assertEqual(len(detected), 0)


class TestProxySummary(unittest.TestCase):
    def test_summary(self):
        mgr = ProxyManager()
        mgr.add(ProxyConfig(name="p1", url="http://a:80"))
        mgr.add(ProxyConfig(name="p2", url="http://b:80", enabled=False))
        s = mgr.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["enabled"], 1)
        self.assertEqual(s["disabled"], 1)


if __name__ == "__main__":
    unittest.main()
