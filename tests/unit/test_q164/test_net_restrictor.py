"""Tests for Q164 NetworkRestrictor."""
from __future__ import annotations

import unittest

from lidco.sandbox.net_restrictor import NetworkRestrictor
from lidco.sandbox.policy import SandboxPolicy


class TestNetworkRestrictor(unittest.TestCase):
    def test_deny_all_blocks_external(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=[])
        nr = NetworkRestrictor(policy)
        self.assertFalse(nr.check_domain("example.com"))

    def test_localhost_always_allowed(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=[])
        nr = NetworkRestrictor(policy)
        self.assertTrue(nr.check_domain("localhost"))

    def test_127_always_allowed(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=[])
        nr = NetworkRestrictor(policy)
        self.assertTrue(nr.check_domain("127.0.0.1"))

    def test_ipv6_loopback_always_allowed(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=[])
        nr = NetworkRestrictor(policy)
        self.assertTrue(nr.check_domain("::1"))

    def test_allowed_domain_passes(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=["api.example.com"])
        nr = NetworkRestrictor(policy)
        self.assertTrue(nr.check_domain("api.example.com"))

    def test_subdomain_of_allowed(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=["example.com"])
        nr = NetworkRestrictor(policy)
        self.assertTrue(nr.check_domain("sub.example.com"))

    def test_domain_not_in_allowed(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=["example.com"])
        nr = NetworkRestrictor(policy)
        self.assertFalse(nr.check_domain("evil.com"))

    def test_check_url_valid(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=["example.com"])
        nr = NetworkRestrictor(policy)
        self.assertTrue(nr.check_url("https://example.com/api/v1"))

    def test_check_url_denied(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=["example.com"])
        nr = NetworkRestrictor(policy)
        self.assertFalse(nr.check_url("https://evil.com/hack"))

    def test_check_url_localhost(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=[])
        nr = NetworkRestrictor(policy)
        self.assertTrue(nr.check_url("http://localhost:8080/api"))

    def test_check_url_no_hostname(self):
        policy = SandboxPolicy(deny_all_network=True)
        nr = NetworkRestrictor(policy)
        self.assertFalse(nr.check_url("not-a-url"))

    def test_violations_empty_initially(self):
        nr = NetworkRestrictor(SandboxPolicy())
        self.assertEqual(nr.violations, [])

    def test_violations_recorded(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=[])
        nr = NetworkRestrictor(policy)
        nr.check_domain("evil.com")
        self.assertEqual(len(nr.violations), 1)
        self.assertEqual(nr.violations[0].violation_type, "net")

    def test_violations_returns_copy(self):
        nr = NetworkRestrictor(SandboxPolicy())
        v1 = nr.violations
        v2 = nr.violations
        self.assertIsNot(v1, v2)

    def test_not_deny_all_no_list_allows_all(self):
        policy = SandboxPolicy(deny_all_network=False, allowed_domains=[])
        nr = NetworkRestrictor(policy)
        self.assertTrue(nr.check_domain("anything.com"))

    def test_case_insensitive(self):
        policy = SandboxPolicy(deny_all_network=True, allowed_domains=["Example.COM"])
        nr = NetworkRestrictor(policy)
        self.assertTrue(nr.check_domain("example.com"))
        self.assertTrue(nr.check_domain("EXAMPLE.COM"))


if __name__ == "__main__":
    unittest.main()
