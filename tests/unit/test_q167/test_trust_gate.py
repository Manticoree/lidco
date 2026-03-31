"""Tests for TrustGate (Task 950)."""
from __future__ import annotations

import unittest

from lidco.marketplace.manifest import Capability, PluginManifest, TrustLevel
from lidco.marketplace.trust_gate import TrustDecision, TrustGate


def _manifest(trust=TrustLevel.COMMUNITY, caps=None, name="plug"):
    return PluginManifest(
        name=name, version="1.0.0", description="d", author="a",
        trust_level=trust, capabilities=caps or [],
    )


class TestTrustDecision(unittest.TestCase):
    def test_fields(self):
        d = TrustDecision(allowed=True, reason="ok")
        self.assertTrue(d.allowed)
        self.assertEqual(d.reason, "ok")
        self.assertEqual(d.required_capabilities, [])
        self.assertEqual(d.trust_level, TrustLevel.UNVERIFIED)


class TestTrustGateVerified(unittest.TestCase):
    def test_verified_auto_trusted(self):
        gate = TrustGate(auto_trust_verified=True)
        d = gate.evaluate(_manifest(TrustLevel.VERIFIED))
        self.assertTrue(d.allowed)

    def test_verified_auto_trust_disabled(self):
        gate = TrustGate(auto_trust_verified=False)
        d = gate.evaluate(_manifest(TrustLevel.VERIFIED))
        self.assertFalse(d.allowed)


class TestTrustGateCommunity(unittest.TestCase):
    def test_community_safe_caps_allowed(self):
        gate = TrustGate()
        d = gate.evaluate(_manifest(TrustLevel.COMMUNITY, [Capability.FILE_READ, Capability.GIT]))
        self.assertTrue(d.allowed)

    def test_community_dangerous_execute_blocked(self):
        gate = TrustGate()
        d = gate.evaluate(_manifest(TrustLevel.COMMUNITY, [Capability.EXECUTE]))
        self.assertFalse(d.allowed)
        self.assertIn("dangerous", d.reason.lower())

    def test_community_dangerous_file_write_blocked(self):
        gate = TrustGate()
        d = gate.evaluate(_manifest(TrustLevel.COMMUNITY, [Capability.FILE_WRITE]))
        self.assertFalse(d.allowed)

    def test_community_no_caps_allowed(self):
        gate = TrustGate()
        d = gate.evaluate(_manifest(TrustLevel.COMMUNITY, []))
        self.assertTrue(d.allowed)


class TestTrustGateUnverified(unittest.TestCase):
    def test_unverified_always_blocked(self):
        gate = TrustGate()
        d = gate.evaluate(_manifest(TrustLevel.UNVERIFIED))
        self.assertFalse(d.allowed)
        self.assertIn("confirmation", d.reason.lower())


class TestTrustGateAllowlist(unittest.TestCase):
    def test_allowlisted_plugin_passes(self):
        gate = TrustGate(org_allowlist=["plug"])
        d = gate.evaluate(_manifest(TrustLevel.UNVERIFIED, [Capability.EXECUTE], name="plug"))
        self.assertTrue(d.allowed)

    def test_add_to_allowlist(self):
        gate = TrustGate()
        self.assertFalse(gate.is_allowed("x"))
        gate.add_to_allowlist("x")
        self.assertTrue(gate.is_allowed("x"))

    def test_remove_from_allowlist(self):
        gate = TrustGate(org_allowlist=["x"])
        gate.remove_from_allowlist("x")
        self.assertFalse(gate.is_allowed("x"))

    def test_remove_nonexistent_noop(self):
        gate = TrustGate()
        gate.remove_from_allowlist("nope")  # should not raise

    def test_capabilities_in_decision(self):
        gate = TrustGate()
        caps = [Capability.NETWORK, Capability.DATABASE]
        d = gate.evaluate(_manifest(TrustLevel.COMMUNITY, caps))
        self.assertEqual(d.required_capabilities, caps)


if __name__ == "__main__":
    unittest.main()
