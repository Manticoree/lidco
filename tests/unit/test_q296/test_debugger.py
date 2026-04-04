"""Tests for Q296 ContainerDebugger."""
import subprocess
import unittest

from lidco.containers.debugger import ContainerDebugger


def _make_run_fn(stdout="", stderr="", returncode=0):
    """Return a mock run function."""
    def _run(cmd):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)
    return _run


class TestContainerDebugger(unittest.TestCase):
    # -- logs --------------------------------------------------------------

    def test_logs_returns_lines(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn(stdout="line1\nline2\nline3\n"))
        lines = dbg.logs("abc123")
        self.assertEqual(lines, ["line1", "line2", "line3"])

    def test_logs_empty(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn(stdout=""))
        lines = dbg.logs("abc123")
        self.assertEqual(lines, [])

    def test_logs_uses_stderr_fallback(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn(stdout="", stderr="err1\nerr2"))
        lines = dbg.logs("abc123")
        self.assertEqual(lines, ["err1", "err2"])

    def test_logs_empty_container_raises(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn())
        with self.assertRaises(ValueError):
            dbg.logs("")

    def test_logs_passes_tail(self):
        captured = {}
        def _run(cmd):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        dbg = ContainerDebugger(run_fn=_run)
        dbg.logs("abc", tail=50)
        self.assertIn("50", captured["cmd"])

    # -- exec_cmd ----------------------------------------------------------

    def test_exec_cmd_success(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn(stdout="hello world"))
        result = dbg.exec_cmd("abc123", "echo hello")
        self.assertEqual(result, "hello world")

    def test_exec_cmd_failure_raises(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn(returncode=1, stderr="not found"))
        with self.assertRaises(RuntimeError):
            dbg.exec_cmd("abc123", "bad_cmd")

    def test_exec_cmd_empty_container_raises(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn())
        with self.assertRaises(ValueError):
            dbg.exec_cmd("", "ls")

    def test_exec_cmd_empty_cmd_raises(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn())
        with self.assertRaises(ValueError):
            dbg.exec_cmd("abc", "")

    # -- port_forward ------------------------------------------------------

    def test_port_forward_config(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn())
        cfg = dbg.port_forward("abc123", 8080, 80)
        self.assertEqual(cfg["container"], "abc123")
        self.assertEqual(cfg["local_port"], 8080)
        self.assertEqual(cfg["remote_port"], 80)
        self.assertEqual(cfg["status"], "configured")

    def test_port_forward_invalid_local_port(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn())
        with self.assertRaises(ValueError):
            dbg.port_forward("abc", 0, 80)

    def test_port_forward_invalid_remote_port(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn())
        with self.assertRaises(ValueError):
            dbg.port_forward("abc", 80, 70000)

    def test_port_forward_has_command(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn())
        cfg = dbg.port_forward("abc", 3000, 8080)
        self.assertIn("command", cfg)
        self.assertIn("abc", cfg["command"])

    # -- health_check ------------------------------------------------------

    def test_health_check_running(self):
        import json
        state = json.dumps({"Running": True, "Status": "running", "Health": {"Status": "healthy"}})
        dbg = ContainerDebugger(run_fn=_make_run_fn(stdout=state))
        result = dbg.health_check("abc123")
        self.assertTrue(result["running"])
        self.assertEqual(result["status"], "running")
        self.assertEqual(result["health"], "healthy")

    def test_health_check_not_found(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn(returncode=1, stderr="not found"))
        result = dbg.health_check("missing")
        self.assertFalse(result["running"])
        self.assertEqual(result["status"], "not_found")

    def test_health_check_empty_container_raises(self):
        dbg = ContainerDebugger(run_fn=_make_run_fn())
        with self.assertRaises(ValueError):
            dbg.health_check("")

    def test_health_check_no_health_info(self):
        import json
        state = json.dumps({"Running": True, "Status": "running"})
        dbg = ContainerDebugger(run_fn=_make_run_fn(stdout=state))
        result = dbg.health_check("abc123")
        self.assertEqual(result["health"], "none")

    def test_health_check_stopped(self):
        import json
        state = json.dumps({"Running": False, "Status": "exited"})
        dbg = ContainerDebugger(run_fn=_make_run_fn(stdout=state))
        result = dbg.health_check("abc123")
        self.assertFalse(result["running"])
        self.assertEqual(result["status"], "exited")


if __name__ == "__main__":
    unittest.main()
