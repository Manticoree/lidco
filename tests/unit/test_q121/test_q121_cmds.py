"""Tests for src/lidco/cli/commands/q121_cmds.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load():
    import lidco.cli.commands.q121_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg, mod


SIMPLE_DIFF = """\
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,3 @@
 line1
-line2
+line2_modified
 line3
"""


class TestPatchCmdRegistered:
    def test_registered(self):
        reg, _ = _load()
        assert "patch" in reg.commands

    def test_no_args_returns_usage(self):
        reg, _ = _load()
        result = _run(reg.commands["patch"].handler(""))
        assert "Usage" in result or "parse" in result.lower()


class TestPatchParse:
    def test_parse_with_diff(self):
        reg, _ = _load()
        result = _run(reg.commands["patch"].handler(f"parse {SIMPLE_DIFF}"))
        assert "file" in result.lower() or "+" in result

    def test_parse_no_text(self):
        reg, _ = _load()
        result = _run(reg.commands["patch"].handler("parse"))
        assert "Usage" in result or "diff" in result.lower()

    def test_parse_stores_files(self):
        reg, mod = _load()
        _run(reg.commands["patch"].handler(f"parse {SIMPLE_DIFF}"))
        assert "parsed_files" in mod._state

    def test_parse_summary_format(self):
        reg, _ = _load()
        result = _run(reg.commands["patch"].handler(f"parse {SIMPLE_DIFF}"))
        assert isinstance(result, str)
        assert len(result) > 0


class TestPatchApply:
    def test_apply_no_original(self):
        reg, _ = _load()
        result = _run(reg.commands["patch"].handler("apply"))
        assert "No original" in result or "state" in result.lower()

    def test_apply_no_patch(self):
        reg, mod = _load()
        mod._state["original"] = "line1\nline2\nline3\n"
        result = _run(reg.commands["patch"].handler("apply"))
        assert "parse" in result.lower() or "No parsed" in result

    def test_apply_with_patch(self):
        reg, mod = _load()
        mod._state["original"] = "line1\nline2\nline3\n"
        _run(reg.commands["patch"].handler(f"parse {SIMPLE_DIFF}"))
        result = _run(reg.commands["patch"].handler("apply"))
        assert "applied" in result.lower() or "success" in result.lower()

    def test_apply_stores_result(self):
        reg, mod = _load()
        mod._state["original"] = "line1\nline2\nline3\n"
        _run(reg.commands["patch"].handler(f"parse {SIMPLE_DIFF}"))
        _run(reg.commands["patch"].handler("apply"))
        assert "applied_text" in mod._state


class TestPatchDiff:
    def test_diff_no_state(self):
        reg, _ = _load()
        result = _run(reg.commands["patch"].handler("diff"))
        assert isinstance(result, str)

    def test_diff_with_state(self):
        reg, mod = _load()
        mod._state["original"] = "hello\nworld\n"
        mod._state["applied_text"] = "hello\nearth\n"
        result = _run(reg.commands["patch"].handler("diff"))
        assert isinstance(result, str)


class TestPatchStats:
    def test_stats_no_state(self):
        reg, _ = _load()
        result = _run(reg.commands["patch"].handler("stats"))
        assert isinstance(result, str)

    def test_stats_with_state(self):
        reg, mod = _load()
        mod._state["original"] = "a\nb\n"
        mod._state["applied_text"] = "a\nc\n"
        result = _run(reg.commands["patch"].handler("stats"))
        assert "Added" in result or "added" in result.lower()

    def test_unknown_sub(self):
        reg, _ = _load()
        result = _run(reg.commands["patch"].handler("unknown"))
        assert "Usage" in result or "parse" in result.lower()
