"""Q55/371 — Hunk-level diff approval."""
from __future__ import annotations

import pytest


SAMPLE_DIFF = """\
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,5 +1,6 @@
 def foo():
-    return 1
+    return 42
+    # updated

 def bar():
     pass
@@ -10,3 +11,4 @@
 def baz():
-    x = 0
+    x = 1
     return x
"""


class TestParseHunks:
    def test_parses_two_hunks(self):
        from lidco.cli.hunk_approver import parse_hunks
        hunks = parse_hunks(SAMPLE_DIFF)
        assert len(hunks) == 2

    def test_hunk_has_correct_files(self):
        from lidco.cli.hunk_approver import parse_hunks
        hunks = parse_hunks(SAMPLE_DIFF)
        assert hunks[0].file_a == "a/src/foo.py"
        assert hunks[0].file_b == "b/src/foo.py"

    def test_hunk_header_parsed(self):
        from lidco.cli.hunk_approver import parse_hunks
        hunks = parse_hunks(SAMPLE_DIFF)
        assert "@@ -1,5 +1,6 @@" in hunks[0].header

    def test_hunk_lines_contain_diff(self):
        from lidco.cli.hunk_approver import parse_hunks
        hunks = parse_hunks(SAMPLE_DIFF)
        lines_text = "\n".join(hunks[0].lines)
        assert "-    return 1" in lines_text
        assert "+    return 42" in lines_text

    def test_parse_empty_diff(self):
        from lidco.cli.hunk_approver import parse_hunks
        assert parse_hunks("") == []

    def test_hunk_start_lines(self):
        from lidco.cli.hunk_approver import parse_hunks
        hunks = parse_hunks(SAMPLE_DIFF)
        assert hunks[0].start_a == 1
        assert hunks[0].start_b == 1
        assert hunks[1].start_a == 10


class TestApproveHunks:
    def _mock_console(self, responses: list[str]):
        """Return a console mock and an input mock that returns responses in sequence."""
        console = None
        idx = [0]

        def mock_input(prompt: str) -> str:
            val = responses[idx[0]] if idx[0] < len(responses) else "s"
            idx[0] += 1
            return val

        return console, mock_input

    def test_accept_all(self):
        from lidco.cli.hunk_approver import parse_hunks, approve_hunks_interactive
        hunks = parse_hunks(SAMPLE_DIFF)
        with __import__("unittest.mock", fromlist=["patch"]).patch("builtins.input", side_effect=["a", "a"]):
            approved = approve_hunks_interactive(hunks)
        assert len(approved) == 2

    def test_skip_all(self):
        from lidco.cli.hunk_approver import parse_hunks, approve_hunks_interactive
        hunks = parse_hunks(SAMPLE_DIFF)
        with __import__("unittest.mock", fromlist=["patch"]).patch("builtins.input", side_effect=["s", "s"]):
            approved = approve_hunks_interactive(hunks)
        assert approved == []

    def test_accept_first_skip_second(self):
        from lidco.cli.hunk_approver import parse_hunks, approve_hunks_interactive
        hunks = parse_hunks(SAMPLE_DIFF)
        with __import__("unittest.mock", fromlist=["patch"]).patch("builtins.input", side_effect=["a", "s"]):
            approved = approve_hunks_interactive(hunks)
        assert len(approved) == 1
        assert approved[0].start_a == hunks[0].start_a

    def test_quit_stops_early(self):
        from lidco.cli.hunk_approver import parse_hunks, approve_hunks_interactive
        hunks = parse_hunks(SAMPLE_DIFF)
        with __import__("unittest.mock", fromlist=["patch"]).patch("builtins.input", side_effect=["a", "q"]):
            approved = approve_hunks_interactive(hunks)
        # First accepted, second quit
        assert len(approved) == 1

    def test_empty_hunks_returns_empty(self):
        from lidco.cli.hunk_approver import approve_hunks_interactive
        assert approve_hunks_interactive([]) == []
