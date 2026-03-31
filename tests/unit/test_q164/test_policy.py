"""Tests for Q164 SandboxPolicy and PolicyViolation."""
from __future__ import annotations

import os
import time
import unittest

from lidco.sandbox.policy import PolicyViolation, SandboxPolicy


class TestPolicyViolation(unittest.TestCase):
    def test_defaults(self):
        v = PolicyViolation(violation_type="fs", detail="blocked")
        self.assertEqual(v.violation_type, "fs")
        self.assertEqual(v.detail, "blocked")
        self.assertTrue(v.blocked)
        self.assertGreater(v.timestamp, 0.0)

    def test_custom_timestamp(self):
        v = PolicyViolation(violation_type="net", detail="x", timestamp=42.0)
        self.assertEqual(v.timestamp, 42.0)

    def test_blocked_default_true(self):
        v = PolicyViolation(violation_type="mem", detail="over limit")
        self.assertTrue(v.blocked)

    def test_blocked_false(self):
        v = PolicyViolation(violation_type="proc", detail="warn", blocked=False)
        self.assertFalse(v.blocked)

    def test_violation_types(self):
        for vt in ("fs", "net", "mem", "time", "proc"):
            v = PolicyViolation(violation_type=vt, detail="test")
            self.assertEqual(v.violation_type, vt)


class TestSandboxPolicy(unittest.TestCase):
    def test_default_fields(self):
        p = SandboxPolicy()
        self.assertEqual(p.allowed_paths, [])
        self.assertEqual(p.denied_paths, [])
        self.assertEqual(p.allowed_domains, [])
        self.assertTrue(p.deny_all_network)
        self.assertEqual(p.max_memory_mb, 512)
        self.assertEqual(p.max_time_seconds, 60)
        self.assertFalse(p.allow_subprocesses)

    def test_custom_values(self):
        p = SandboxPolicy(
            allowed_paths=["/home"],
            denied_paths=["/etc"],
            allowed_domains=["example.com"],
            deny_all_network=False,
            max_memory_mb=256,
            max_time_seconds=30,
            allow_subprocesses=True,
        )
        self.assertEqual(p.allowed_paths, ["/home"])
        self.assertEqual(p.max_memory_mb, 256)
        self.assertTrue(p.allow_subprocesses)

    def test_with_defaults_has_cwd(self):
        p = SandboxPolicy.with_defaults()
        self.assertIn(os.getcwd(), p.allowed_paths)

    def test_with_defaults_has_denied(self):
        p = SandboxPolicy.with_defaults()
        self.assertTrue(len(p.denied_paths) > 0)

    def test_with_defaults_deny_network(self):
        p = SandboxPolicy.with_defaults()
        self.assertTrue(p.deny_all_network)

    def test_with_defaults_no_subprocesses(self):
        p = SandboxPolicy.with_defaults()
        self.assertFalse(p.allow_subprocesses)

    def test_merge_denied_union(self):
        a = SandboxPolicy(denied_paths=["/etc"])
        b = SandboxPolicy(denied_paths=["/var"])
        merged = a.merge(b)
        self.assertIn("/etc", merged.denied_paths)
        self.assertIn("/var", merged.denied_paths)

    def test_merge_deny_network_wins(self):
        a = SandboxPolicy(deny_all_network=False)
        b = SandboxPolicy(deny_all_network=True)
        self.assertTrue(a.merge(b).deny_all_network)
        self.assertTrue(b.merge(a).deny_all_network)

    def test_merge_subprocesses_deny_wins(self):
        a = SandboxPolicy(allow_subprocesses=True)
        b = SandboxPolicy(allow_subprocesses=False)
        self.assertFalse(a.merge(b).allow_subprocesses)

    def test_merge_stricter_memory(self):
        a = SandboxPolicy(max_memory_mb=256)
        b = SandboxPolicy(max_memory_mb=512)
        self.assertEqual(a.merge(b).max_memory_mb, 256)

    def test_merge_stricter_time(self):
        a = SandboxPolicy(max_time_seconds=30)
        b = SandboxPolicy(max_time_seconds=120)
        self.assertEqual(a.merge(b).max_time_seconds, 30)

    def test_merge_domains_intersection(self):
        a = SandboxPolicy(allowed_domains=["a.com", "b.com"])
        b = SandboxPolicy(allowed_domains=["b.com", "c.com"])
        merged = a.merge(b)
        self.assertIn("b.com", merged.allowed_domains)
        self.assertNotIn("a.com", merged.allowed_domains)

    def test_merge_domains_one_empty(self):
        a = SandboxPolicy(allowed_domains=["a.com"])
        b = SandboxPolicy(allowed_domains=[])
        merged = a.merge(b)
        self.assertIn("a.com", merged.allowed_domains)

    def test_merge_allowed_paths_union(self):
        a = SandboxPolicy(allowed_paths=["/home"])
        b = SandboxPolicy(allowed_paths=["/tmp"])
        merged = a.merge(b)
        self.assertIn("/home", merged.allowed_paths)
        self.assertIn("/tmp", merged.allowed_paths)


if __name__ == "__main__":
    unittest.main()
