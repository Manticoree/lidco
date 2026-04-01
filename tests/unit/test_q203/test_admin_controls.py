"""Tests for AdminControls."""
from __future__ import annotations

import unittest

from lidco.enterprise.admin_controls import AdminAction, AdminControls


class TestAdminActionFrozen(unittest.TestCase):
    def test_frozen(self):
        a = AdminAction(action="disable", target="x")
        with self.assertRaises(AttributeError):
            a.action = "other"  # type: ignore[misc]

    def test_defaults(self):
        a = AdminAction(action="test", target="t")
        self.assertEqual(a.admin_id, "")
        self.assertEqual(a.reason, "")
        self.assertEqual(a.timestamp, 0.0)


class TestPluginControls(unittest.TestCase):
    def test_disable_enable(self):
        ac = AdminControls()
        ac.disable_plugin("bad-plugin", reason="insecure")
        self.assertTrue(ac.is_plugin_disabled("bad-plugin"))
        ac.enable_plugin("bad-plugin")
        self.assertFalse(ac.is_plugin_disabled("bad-plugin"))

    def test_disabled_plugins_list(self):
        ac = AdminControls()
        ac.disable_plugin("a")
        ac.disable_plugin("b")
        self.assertEqual(set(ac.disabled_plugins()), {"a", "b"})

    def test_not_disabled_by_default(self):
        ac = AdminControls()
        self.assertFalse(ac.is_plugin_disabled("anything"))


class TestMCPControls(unittest.TestCase):
    def test_deny_allow(self):
        ac = AdminControls()
        ac.deny_mcp_server("evil-server", reason="untrusted")
        self.assertTrue(ac.is_mcp_denied("evil-server"))
        ac.allow_mcp_server("evil-server")
        self.assertFalse(ac.is_mcp_denied("evil-server"))

    def test_not_denied_by_default(self):
        ac = AdminControls()
        self.assertFalse(ac.is_mcp_denied("any"))


class TestModelControls(unittest.TestCase):
    def test_restrict_unrestrict(self):
        ac = AdminControls()
        ac.restrict_model("gpt-5", reason="cost")
        self.assertTrue(ac.is_model_restricted("gpt-5"))
        ac.unrestrict_model("gpt-5")
        self.assertFalse(ac.is_model_restricted("gpt-5"))

    def test_not_restricted_by_default(self):
        ac = AdminControls()
        self.assertFalse(ac.is_model_restricted("any"))


class TestAuditLog(unittest.TestCase):
    def test_audit_recorded(self):
        ac = AdminControls()
        ac.disable_plugin("p1")
        ac.deny_mcp_server("s1")
        ac.restrict_model("m1")
        log = ac.audit_log()
        self.assertEqual(len(log), 3)
        actions = [a.action for a in log]
        self.assertIn("disable_plugin", actions)
        self.assertIn("deny_mcp_server", actions)
        self.assertIn("restrict_model", actions)

    def test_audit_targets(self):
        ac = AdminControls()
        ac.disable_plugin("p1")
        ac.enable_plugin("p1")
        log = ac.audit_log()
        self.assertEqual(len(log), 2)
        self.assertEqual(log[0].target, "p1")
        self.assertEqual(log[1].target, "p1")

    def test_audit_timestamps(self):
        ac = AdminControls()
        ac.disable_plugin("p1")
        log = ac.audit_log()
        self.assertGreater(log[0].timestamp, 0)


class TestSummary(unittest.TestCase):
    def test_summary_content(self):
        ac = AdminControls()
        ac.disable_plugin("p1", reason="bad")
        ac.deny_mcp_server("s1")
        s = ac.summary()
        self.assertIn("1 disabled plugins", s)
        self.assertIn("1 denied MCP servers", s)
        self.assertIn("p1", s)
        self.assertIn("s1", s)


if __name__ == "__main__":
    unittest.main()
