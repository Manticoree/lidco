"""Tests for Q127 CLI commands (/snapshot)."""
from __future__ import annotations
import asyncio
import unittest
from lidco.cli.commands import q127_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ127Commands(unittest.TestCase):
    def setUp(self):
        q127_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q127_cmds.register(MockRegistry())
        self.handler = self.registered["snapshot"].handler

    def test_command_registered(self):
        self.assertIn("snapshot", self.registered)

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_sub_shows_usage(self):
        result = _run(self.handler("bogus"))
        self.assertIn("Usage", result)

    def test_capture_returns_snapshot_id(self):
        result = _run(self.handler("capture v1"))
        self.assertIn("Captured", result)
        self.assertIn("v1", result)

    def test_capture_no_label_uses_default(self):
        result = _run(self.handler("capture"))
        self.assertIn("Captured", result)

    def test_list_empty(self):
        result = _run(self.handler("list"))
        self.assertIn("No snapshots", result)

    def test_list_after_capture(self):
        _run(self.handler("capture first_snap"))
        result = _run(self.handler("list"))
        self.assertIn("Snapshot", result)
        self.assertIn("first_snap", result)

    def test_restore_not_found(self):
        result = _run(self.handler("restore nonexistent"))
        self.assertIn("not found", result)

    def test_restore_no_args(self):
        result = _run(self.handler("restore"))
        self.assertIn("Usage", result)

    def test_restore_dry_run(self):
        # Capture then restore with dry
        _run(self.handler("capture mysnap"))
        snap_id = list(q127_cmds._state["snapshots"].keys())[0]
        result = _run(self.handler(f"restore {snap_id} dry"))
        self.assertIn("dry-run", result)

    def test_restore_snap_exists(self):
        _run(self.handler("capture mysnap"))
        snap_id = list(q127_cmds._state["snapshots"].keys())[0]
        result = _run(self.handler(f"restore {snap_id}"))
        # Should not say "not found"
        self.assertNotIn("not found", result)

    def test_diff_not_found_a(self):
        result = _run(self.handler("diff nonexistent other"))
        self.assertIn("not found", result)

    def test_diff_not_found_b(self):
        _run(self.handler("capture snap_a"))
        id_a = list(q127_cmds._state["snapshots"].keys())[0]
        result = _run(self.handler(f"diff {id_a} nonexistent"))
        self.assertIn("not found", result)

    def test_diff_no_args(self):
        result = _run(self.handler("diff"))
        self.assertIn("Usage", result)

    def test_diff_two_snapshots(self):
        _run(self.handler("capture snap_a"))
        _run(self.handler("capture snap_b"))
        keys = list(q127_cmds._state["snapshots"].keys())
        result = _run(self.handler(f"diff {keys[0]} {keys[1]}"))
        self.assertIn("Diff", result)

    def test_list_shows_multiple(self):
        _run(self.handler("capture alpha"))
        _run(self.handler("capture beta"))
        result = _run(self.handler("list"))
        self.assertIn("alpha", result)
        self.assertIn("beta", result)

    def test_capture_with_paths(self):
        # paths that don't exist are just skipped; no crash
        result = _run(self.handler("capture v2 nonexistent_path.py"))
        self.assertIn("Captured", result)

    def test_description_set(self):
        self.assertIn("snapshot", self.registered["snapshot"].description.lower())

    def test_list_count(self):
        _run(self.handler("capture s1"))
        _run(self.handler("capture s2"))
        _run(self.handler("capture s3"))
        result = _run(self.handler("list"))
        self.assertIn("Snapshots (3)", result)

    def test_restore_reports_file_count(self):
        _run(self.handler("capture empty_snap"))
        snap_id = list(q127_cmds._state["snapshots"].keys())[0]
        result = _run(self.handler(f"restore {snap_id}"))
        # Should show "0/0 file(s)" for empty snapshot
        self.assertIn("file(s)", result)

    def test_diff_keys_present(self):
        _run(self.handler("capture snap_a"))
        _run(self.handler("capture snap_b"))
        keys = list(q127_cmds._state["snapshots"].keys())
        result = _run(self.handler(f"diff {keys[0]} {keys[1]}"))
        for keyword in ("Added", "Removed", "Modified", "Unchanged"):
            self.assertIn(keyword, result)


if __name__ == "__main__":
    unittest.main()
