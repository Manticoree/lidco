"""Tests for Q164 FsJail."""
from __future__ import annotations

import os
import unittest

from lidco.sandbox.fs_jail import FsJail
from lidco.sandbox.policy import SandboxPolicy


class TestFsJail(unittest.TestCase):
    def _make_jail(self, allowed=None, denied=None, resolve_fn=None):
        policy = SandboxPolicy(
            allowed_paths=allowed or ["/home/user/project"],
            denied_paths=denied or ["/etc", "/var"],
        )
        if resolve_fn:
            return FsJail(policy, resolve_fn=resolve_fn)
        # Use identity resolve for deterministic tests
        return FsJail(policy, resolve_fn=lambda p: p)

    def test_check_path_allowed(self):
        jail = self._make_jail()
        self.assertTrue(jail.check_path("/home/user/project/file.py"))

    def test_check_path_denied(self):
        jail = self._make_jail()
        self.assertFalse(jail.check_path("/etc/passwd"))

    def test_check_path_not_in_allowed(self):
        jail = self._make_jail()
        self.assertFalse(jail.check_path("/opt/other"))

    def test_check_path_exact_allowed(self):
        jail = self._make_jail()
        self.assertTrue(jail.check_path("/home/user/project"))

    def test_check_read_allowed_outside(self):
        """Read is more permissive — allows non-denied paths even outside allowed."""
        jail = self._make_jail()
        self.assertTrue(jail.check_read("/opt/something"))

    def test_check_read_denied(self):
        jail = self._make_jail()
        self.assertFalse(jail.check_read("/etc/shadow"))

    def test_check_write_allowed(self):
        jail = self._make_jail()
        self.assertTrue(jail.check_write("/home/user/project/out.txt"))

    def test_check_write_denied(self):
        jail = self._make_jail()
        self.assertFalse(jail.check_write("/etc/hosts"))

    def test_check_write_outside_allowed(self):
        jail = self._make_jail()
        self.assertFalse(jail.check_write("/opt/outside"))

    def test_violations_empty_initially(self):
        jail = self._make_jail()
        self.assertEqual(jail.violations, [])

    def test_violations_recorded_on_deny(self):
        jail = self._make_jail()
        jail.check_path("/etc/passwd")
        self.assertEqual(len(jail.violations), 1)
        self.assertEqual(jail.violations[0].violation_type, "fs")

    def test_violations_recorded_on_write_deny(self):
        jail = self._make_jail()
        jail.check_write("/var/log/syslog")
        self.assertEqual(len(jail.violations), 1)

    def test_violations_multiple(self):
        jail = self._make_jail()
        jail.check_path("/etc/a")
        jail.check_path("/var/b")
        self.assertEqual(len(jail.violations), 2)

    def test_violations_returns_copy(self):
        jail = self._make_jail()
        v1 = jail.violations
        v2 = jail.violations
        self.assertIsNot(v1, v2)

    def test_symlink_escape_blocked(self):
        """Symlink resolves outside allowed -> blocked."""
        def fake_resolve(path):
            if "sneaky" in path:
                return "/etc/secret"
            return path

        jail = self._make_jail(resolve_fn=fake_resolve)
        self.assertFalse(jail.check_path("/home/user/project/sneaky"))

    def test_symlink_within_allowed(self):
        """Symlink resolves within allowed -> allowed."""
        def fake_resolve(path):
            return "/home/user/project/real_file"

        jail = self._make_jail(resolve_fn=fake_resolve)
        self.assertTrue(jail.check_path("/home/user/project/link"))

    def test_denied_subdir(self):
        jail = self._make_jail()
        self.assertFalse(jail.check_path("/etc/nginx/conf.d/default.conf"))

    def test_allowed_empty_permits_non_denied(self):
        """When allowed_paths is empty, any non-denied path is accessible."""
        policy = SandboxPolicy(allowed_paths=[], denied_paths=["/etc"])
        jail = FsJail(policy, resolve_fn=lambda p: p)
        self.assertTrue(jail.check_path("/opt/anything"))
        self.assertFalse(jail.check_path("/etc/passwd"))


if __name__ == "__main__":
    unittest.main()
