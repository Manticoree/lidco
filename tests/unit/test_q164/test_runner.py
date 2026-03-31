"""Tests for Q164 SandboxRunner."""
from __future__ import annotations

import unittest

from lidco.sandbox.fs_jail import FsJail
from lidco.sandbox.net_restrictor import NetworkRestrictor
from lidco.sandbox.policy import SandboxPolicy
from lidco.sandbox.runner import SandboxResult, SandboxRunner


def _make_runner(allow_subprocesses=True, subprocess_fn=None, allowed_paths=None):
    policy = SandboxPolicy(
        allowed_paths=allowed_paths or ["/home/user/project"],
        denied_paths=["/etc"],
        allow_subprocesses=allow_subprocesses,
        max_time_seconds=10,
    )
    jail = FsJail(policy, resolve_fn=lambda p: p)
    net = NetworkRestrictor(policy)
    return SandboxRunner(policy, jail, net, subprocess_fn=subprocess_fn)


class TestSandboxResult(unittest.TestCase):
    def test_defaults(self):
        r = SandboxResult()
        self.assertEqual(r.stdout, "")
        self.assertEqual(r.stderr, "")
        self.assertEqual(r.returncode, -1)
        self.assertEqual(r.violations, [])
        self.assertFalse(r.timed_out)
        self.assertTrue(r.allowed)


class TestSandboxRunner(unittest.TestCase):
    def test_check_command_allowed(self):
        runner = _make_runner(allow_subprocesses=True)
        ok, reason = runner.check_command("echo hello")
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_check_command_blocked_rm_rf(self):
        runner = _make_runner(allow_subprocesses=True)
        ok, reason = runner.check_command("rm -rf /")
        self.assertFalse(ok)
        self.assertIn("Dangerous", reason)

    def test_check_command_blocked_mkfs(self):
        runner = _make_runner(allow_subprocesses=True)
        ok, reason = runner.check_command("mkfs.ext4 /dev/sda1")
        self.assertFalse(ok)

    def test_check_command_no_subprocess(self):
        runner = _make_runner(allow_subprocesses=False)
        ok, reason = runner.check_command("echo hello")
        self.assertFalse(ok)
        self.assertIn("not allowed", reason)

    def test_run_success(self):
        def fake_sub(cmd, cwd, timeout):
            return "output", "", 0, False

        runner = _make_runner(subprocess_fn=fake_sub)
        result = runner.run("echo hi", cwd="/home/user/project")
        self.assertTrue(result.allowed)
        self.assertEqual(result.stdout, "output")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.timed_out)

    def test_run_blocked_command(self):
        runner = _make_runner(allow_subprocesses=False)
        result = runner.run("echo hi")
        self.assertFalse(result.allowed)
        self.assertIn("not allowed", result.stderr)

    def test_run_dangerous_command(self):
        runner = _make_runner(allow_subprocesses=True)
        result = runner.run("rm -rf /")
        self.assertFalse(result.allowed)

    def test_run_cwd_denied(self):
        def fake_sub(cmd, cwd, timeout):
            return "out", "", 0, False

        runner = _make_runner(subprocess_fn=fake_sub)
        result = runner.run("ls", cwd="/etc")
        self.assertFalse(result.allowed)

    def test_run_timeout(self):
        def fake_sub(cmd, cwd, timeout):
            return "", "timed out", -1, True

        runner = _make_runner(subprocess_fn=fake_sub)
        result = runner.run("sleep 999", cwd="/home/user/project")
        self.assertTrue(result.timed_out)
        self.assertTrue(result.allowed)  # was allowed to start

    def test_all_violations_aggregates(self):
        runner = _make_runner(allow_subprocesses=False)
        runner.run("echo test")  # generates proc violation
        violations = runner.all_violations()
        self.assertGreater(len(violations), 0)

    def test_all_violations_includes_fs(self):
        def fake_sub(cmd, cwd, timeout):
            return "", "", 0, False

        runner = _make_runner(subprocess_fn=fake_sub)
        # Trigger fs violation by accessing denied cwd
        runner.run("ls", cwd="/etc")
        violations = runner.all_violations()
        fs_violations = [v for v in violations if v.violation_type == "fs"]
        self.assertGreater(len(fs_violations), 0)

    def test_run_nonexistent_cwd_not_in_allowed(self):
        def fake_sub(cmd, cwd, timeout):
            return "", "", 0, False

        runner = _make_runner(subprocess_fn=fake_sub)
        result = runner.run("ls", cwd="/nonexistent")
        self.assertFalse(result.allowed)


if __name__ == "__main__":
    unittest.main()
