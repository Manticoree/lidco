"""Tests for GitEventListener — detect git operations via .git dir polling."""
from __future__ import annotations

import os
import tempfile
import unittest

from lidco.awareness.git_listener import GitEvent, GitEventListener, GitState


class TestGitEventListener(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.git_dir = os.path.join(self.tmpdir, ".git")
        os.makedirs(self.git_dir)
        # Create basic HEAD
        self._write_git_file("HEAD", "ref: refs/heads/main\n")
        # Create refs/heads/main
        refs_dir = os.path.join(self.git_dir, "refs", "heads")
        os.makedirs(refs_dir, exist_ok=True)
        self._write_git_file(os.path.join("refs", "heads", "main"), "abc12345deadbeef\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_git_file(self, rel_path: str, content: str) -> str:
        path = os.path.join(self.git_dir, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_repo_dir_property(self):
        listener = GitEventListener(self.tmpdir)
        self.assertEqual(listener.repo_dir, self.tmpdir)

    def test_get_current_state_basic(self):
        listener = GitEventListener(self.tmpdir)
        state = listener.get_current_state()
        self.assertEqual(state.branch, "main")
        self.assertEqual(state.head_commit, "abc12345")
        self.assertFalse(state.is_merging)
        self.assertFalse(state.is_rebasing)
        self.assertEqual(state.stash_count, 0)

    def test_get_current_state_detached(self):
        self._write_git_file("HEAD", "deadbeef12345678\n")
        listener = GitEventListener(self.tmpdir)
        state = listener.get_current_state()
        self.assertTrue(state.branch.startswith("detached:"))

    def test_get_current_state_merging(self):
        self._write_git_file("MERGE_HEAD", "abc123\n")
        listener = GitEventListener(self.tmpdir)
        state = listener.get_current_state()
        self.assertTrue(state.is_merging)

    def test_get_current_state_rebasing(self):
        os.makedirs(os.path.join(self.git_dir, "rebase-merge"), exist_ok=True)
        listener = GitEventListener(self.tmpdir)
        state = listener.get_current_state()
        self.assertTrue(state.is_rebasing)

    def test_get_current_state_stash(self):
        self._write_git_file(os.path.join("refs", "stash"), "abc123\n")
        listener = GitEventListener(self.tmpdir)
        state = listener.get_current_state()
        self.assertEqual(state.stash_count, 1)

    def test_poll_first_time_no_events(self):
        listener = GitEventListener(self.tmpdir)
        events = listener.poll()
        self.assertEqual(events, [])

    def test_poll_detects_branch_switch(self):
        listener = GitEventListener(self.tmpdir)
        listener.poll()  # baseline

        # Switch branch
        self._write_git_file("HEAD", "ref: refs/heads/feature\n")
        refs_dir = os.path.join(self.git_dir, "refs", "heads")
        os.makedirs(refs_dir, exist_ok=True)
        self._write_git_file(os.path.join("refs", "heads", "feature"), "abc12345deadbeef\n")

        events = listener.poll()
        branch_events = [e for e in events if e.event_type == "branch_switch"]
        self.assertEqual(len(branch_events), 1)
        self.assertEqual(branch_events[0].branch_before, "main")
        self.assertEqual(branch_events[0].branch_after, "feature")

    def test_poll_detects_commit(self):
        listener = GitEventListener(self.tmpdir)
        listener.poll()  # baseline

        # New commit on same branch
        self._write_git_file(os.path.join("refs", "heads", "main"), "newcommit1234\n")
        events = listener.poll()
        commit_events = [e for e in events if e.event_type == "commit"]
        self.assertEqual(len(commit_events), 1)
        self.assertIn("newcommi", commit_events[0].details)

    def test_poll_detects_merge(self):
        listener = GitEventListener(self.tmpdir)
        listener.poll()  # baseline

        self._write_git_file("MERGE_HEAD", "abc\n")
        events = listener.poll()
        merge_events = [e for e in events if e.event_type == "merge"]
        self.assertEqual(len(merge_events), 1)

    def test_poll_detects_rebase(self):
        listener = GitEventListener(self.tmpdir)
        listener.poll()  # baseline

        os.makedirs(os.path.join(self.git_dir, "rebase-merge"), exist_ok=True)
        events = listener.poll()
        rebase_events = [e for e in events if e.event_type == "rebase"]
        self.assertEqual(len(rebase_events), 1)

    def test_poll_detects_stash_pop(self):
        # Start with a stash
        self._write_git_file(os.path.join("refs", "stash"), "abc\n")
        listener = GitEventListener(self.tmpdir)
        listener.poll()  # baseline (stash_count=1)

        # Pop stash
        stash_file = os.path.join(self.git_dir, "refs", "stash")
        os.remove(stash_file)
        events = listener.poll()
        stash_events = [e for e in events if e.event_type == "stash_pop"]
        self.assertEqual(len(stash_events), 1)

    def test_on_event_callback(self):
        listener = GitEventListener(self.tmpdir)
        listener.poll()  # baseline

        received = []
        listener.on_event(lambda e: received.append(e))

        self._write_git_file("MERGE_HEAD", "abc\n")
        listener.poll()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].event_type, "merge")

    def test_callback_exception_does_not_break(self):
        listener = GitEventListener(self.tmpdir)
        listener.poll()

        def bad_cb(e):
            raise RuntimeError("fail")

        received = []
        listener.on_event(bad_cb)
        listener.on_event(lambda e: received.append(e))

        self._write_git_file("MERGE_HEAD", "abc\n")
        events = listener.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(len(received), 1)

    def test_clear_events(self):
        listener = GitEventListener(self.tmpdir)
        listener.poll()
        self._write_git_file("MERGE_HEAD", "abc\n")
        listener.poll()
        self.assertTrue(len(listener.events) > 0)
        listener.clear_events()
        self.assertEqual(listener.events, [])

    def test_events_accumulate(self):
        listener = GitEventListener(self.tmpdir)
        listener.poll()

        self._write_git_file("MERGE_HEAD", "abc\n")
        listener.poll()

        os.makedirs(os.path.join(self.git_dir, "rebase-merge"), exist_ok=True)
        listener.poll()

        self.assertTrue(len(listener.events) >= 2)

    def test_format_state(self):
        listener = GitEventListener(self.tmpdir)
        state = listener.get_current_state()
        formatted = listener.format_state(state)
        self.assertIn("Branch: main", formatted)
        self.assertIn("HEAD:", formatted)

    def test_format_state_not_polled(self):
        listener = GitEventListener(self.tmpdir)
        formatted = listener.format_state()
        self.assertIn("unknown", formatted)

    def test_format_state_with_merge(self):
        self._write_git_file("MERGE_HEAD", "abc\n")
        listener = GitEventListener(self.tmpdir)
        state = listener.get_current_state()
        formatted = listener.format_state(state)
        self.assertIn("MERGING", formatted)

    def test_format_state_with_rebase(self):
        os.makedirs(os.path.join(self.git_dir, "rebase-merge"), exist_ok=True)
        listener = GitEventListener(self.tmpdir)
        state = listener.get_current_state()
        formatted = listener.format_state(state)
        self.assertIn("REBASING", formatted)

    def test_format_state_with_stash(self):
        self._write_git_file(os.path.join("refs", "stash"), "abc\n")
        listener = GitEventListener(self.tmpdir)
        state = listener.get_current_state()
        formatted = listener.format_state(state)
        self.assertIn("Stashes:", formatted)

    def test_git_event_dataclass(self):
        ev = GitEvent(event_type="commit", details="new commit")
        self.assertEqual(ev.event_type, "commit")
        self.assertIsInstance(ev.detected_at, float)
        self.assertIsNone(ev.branch_before)

    def test_git_state_dataclass(self):
        st = GitState(branch="main", head_commit="abc")
        self.assertEqual(st.branch, "main")
        self.assertFalse(st.is_merging)
        self.assertEqual(st.stash_count, 0)

    def test_events_property_is_copy(self):
        listener = GitEventListener(self.tmpdir)
        events = listener.events
        events.append(GitEvent(event_type="fake", details="x"))
        self.assertEqual(len(listener.events), 0)

    def test_no_git_dir(self):
        """Listener on dir without .git should return defaults."""
        empty = tempfile.mkdtemp()
        try:
            listener = GitEventListener(empty)
            state = listener.get_current_state()
            self.assertEqual(state.branch, "unknown")
        finally:
            import shutil
            shutil.rmtree(empty, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
