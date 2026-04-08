"""Tests for Q313 CLI commands."""

import asyncio
import shlex
import tempfile
import unittest

from lidco.snapshot_test.manager import SnapshotManager


def _q(path: str) -> str:
    """Quote a path for safe shlex splitting."""
    return shlex.quote(path)


class _FakeRegistry:
    """Minimal registry to capture registrations."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = handler


def _build_registry() -> _FakeRegistry:
    from lidco.cli.commands.q313_cmds import register_q313_commands
    reg = _FakeRegistry()
    register_q313_commands(reg)
    return reg


class TestRegistration(unittest.TestCase):
    def test_registers_snapshot(self):
        reg = _build_registry()
        self.assertIn("snapshot", reg.commands)

    def test_registers_snapshot_diff(self):
        reg = _build_registry()
        self.assertIn("snapshot-diff", reg.commands)

    def test_registers_snapshot_review(self):
        reg = _build_registry()
        self.assertIn("snapshot-review", reg.commands)

    def test_registers_snapshot_stats(self):
        reg = _build_registry()
        self.assertIn("snapshot-stats", reg.commands)

    def test_four_commands(self):
        reg = _build_registry()
        self.assertEqual(len(reg.commands), 4)


class TestSnapshotHandler(unittest.TestCase):
    def _handler(self):
        return _build_registry().commands["snapshot"]

    def test_no_args_shows_usage(self):
        result = asyncio.run(self._handler()(""))
        self.assertIn("Usage", result)

    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"list --dir {_q(td)}"))
            self.assertIn("No snapshots", result)

    def test_create(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"create mysnap hello --dir {_q(td)}"))
            self.assertIn("Created", result)
            self.assertIn("mysnap", result)

    def test_create_then_list(self):
        with tempfile.TemporaryDirectory() as td:
            asyncio.run(self._handler()(f"create s1 data --dir {_q(td)}"))
            result = asyncio.run(self._handler()(f"list --dir {_q(td)}"))
            self.assertIn("s1", result)

    def test_show(self):
        with tempfile.TemporaryDirectory() as td:
            asyncio.run(self._handler()(f"create s1 hello --dir {_q(td)}"))
            result = asyncio.run(self._handler()(f"show s1 --dir {_q(td)}"))
            self.assertIn("hello", result)
            self.assertIn("Snapshot: s1", result)

    def test_show_missing(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"show nope --dir {_q(td)}"))
            self.assertIn("not found", result)

    def test_update(self):
        with tempfile.TemporaryDirectory() as td:
            asyncio.run(self._handler()(f"create s1 old --dir {_q(td)}"))
            result = asyncio.run(self._handler()(f"update s1 new --dir {_q(td)}"))
            self.assertIn("Updated", result)

    def test_delete(self):
        with tempfile.TemporaryDirectory() as td:
            asyncio.run(self._handler()(f"create s1 data --dir {_q(td)}"))
            result = asyncio.run(self._handler()(f"delete s1 --dir {_q(td)}"))
            self.assertIn("Deleted", result)

    def test_delete_nonexistent(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"delete nope --dir {_q(td)}"))
            self.assertIn("not found", result)

    def test_unknown_subcommand(self):
        result = asyncio.run(self._handler()("badcmd"))
        self.assertIn("Unknown subcommand", result)

    def test_show_no_name(self):
        result = asyncio.run(self._handler()("show"))
        self.assertIn("Usage", result)

    def test_create_no_value(self):
        result = asyncio.run(self._handler()("create onlyname"))
        self.assertIn("Usage", result)


class TestSnapshotDiffHandler(unittest.TestCase):
    def _handler(self):
        return _build_registry().commands["snapshot-diff"]

    def test_no_args(self):
        result = asyncio.run(self._handler()(""))
        self.assertIn("Usage", result)

    def test_diff_nonexistent(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"nosuch value --dir {_q(td)}"))
            self.assertIn("No diff", result)

    def test_diff_with_change(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SnapshotManager(td)
            mgr.create("s1", "old")
            result = asyncio.run(self._handler()(f"s1 new --dir {_q(td)}"))
            self.assertIn("-old", result)
            self.assertIn("+new", result)


class TestSnapshotReviewHandler(unittest.TestCase):
    def _handler(self):
        return _build_registry().commands["snapshot-review"]

    def test_list_empty(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"list --dir {_q(td)}"))
            self.assertIn("No pending", result)

    def test_no_args_shows_pending(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"--dir {_q(td)}"))
            self.assertIn("No pending", result)

    def test_accept(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"accept mysnap --dir {_q(td)}"))
            self.assertIn("Accepted", result)

    def test_reject(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"reject mysnap --dir {_q(td)}"))
            self.assertIn("Rejected", result)

    def test_accept_all(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"accept-all --dir {_q(td)}"))
            self.assertIn("Accepted", result)

    def test_reject_all(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"reject-all --dir {_q(td)}"))
            self.assertIn("Rejected", result)

    def test_history_empty(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"history --dir {_q(td)}"))
            self.assertIn("No review history", result)

    def test_unknown_subcommand(self):
        result = asyncio.run(self._handler()("badcmd"))
        self.assertIn("Usage", result)


class TestSnapshotStatsHandler(unittest.TestCase):
    def _handler(self):
        return _build_registry().commands["snapshot-stats"]

    def test_empty(self):
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(self._handler()(f"--dir {_q(td)}"))
            self.assertIn("Total: 0", result)

    def test_with_snapshots(self):
        with tempfile.TemporaryDirectory() as td:
            mgr = SnapshotManager(td)
            mgr.create("s1", "hello")
            mgr.create("s2", "world!")
            result = asyncio.run(self._handler()(f"--dir {_q(td)}"))
            self.assertIn("Total: 2", result)
            self.assertIn("Snapshot Stats", result)


if __name__ == "__main__":
    unittest.main()
