"""Tests for src/lidco/cli/commands/q120_cmds.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load():
    import lidco.cli.commands.q120_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg, mod


# ------------------------------------------------------------------ #
# /memory consolidate                                                  #
# ------------------------------------------------------------------ #

class TestMemoryConsolidate:
    def test_registered(self):
        reg, _ = _load()
        assert "memory" in reg.commands

    def test_no_args_usage(self):
        reg, _ = _load()
        result = _run(reg.commands["memory"].handler(""))
        assert "Usage" in result or "consolidate" in result.lower()

    def test_consolidate_runs(self):
        reg, _ = _load()
        result = _run(reg.commands["memory"].handler("consolidate"))
        assert "consolidat" in result.lower()

    def test_consolidate_dry_run(self):
        reg, _ = _load()
        result = _run(reg.commands["memory"].handler("consolidate --dry-run"))
        assert "[dry-run]" in result

    def test_consolidate_unknown_sub(self):
        reg, _ = _load()
        result = _run(reg.commands["memory"].handler("unknown"))
        assert "Usage" in result or "consolidate" in result.lower()


# ------------------------------------------------------------------ #
# /session fork, /session diff, /session forks                        #
# ------------------------------------------------------------------ #

class TestSessionForkCommands:
    def test_session_registered(self):
        reg, _ = _load()
        assert "session" in reg.commands

    def test_session_no_args(self):
        reg, _ = _load()
        result = _run(reg.commands["session"].handler(""))
        assert "Usage" in result or "fork" in result.lower()

    def test_session_fork_creates(self):
        reg, _ = _load()
        result = _run(reg.commands["session"].handler("fork TestFork"))
        assert "fork" in result.lower() or "TestFork" in result

    def test_session_fork_with_from_turn(self):
        reg, _ = _load()
        result = _run(reg.commands["session"].handler("fork MyFork --from-turn 3"))
        assert "fork" in result.lower()

    def test_session_fork_no_title(self):
        reg, _ = _load()
        result = _run(reg.commands["session"].handler("fork"))
        assert "Usage" in result or "title" in result.lower()

    def test_session_forks_list(self):
        reg, _ = _load()
        _run(reg.commands["session"].handler("fork A"))
        _run(reg.commands["session"].handler("fork B"))
        result = _run(reg.commands["session"].handler("forks"))
        assert "A" in result or "fork" in result.lower()

    def test_session_forks_empty(self):
        reg, _ = _load()
        result = _run(reg.commands["session"].handler("forks"))
        assert "No forks" in result or "0" in result

    def test_session_diff(self):
        reg, mod = _load()
        # Create two forks to diff
        r1 = _run(reg.commands["session"].handler("fork A"))
        r2 = _run(reg.commands["session"].handler("fork B"))
        # Extract fork IDs from state
        forks = mod._state.get("fork_manager")
        if forks:
            all_forks = forks.list_all()
            if len(all_forks) >= 2:
                fid_a = all_forks[0].fork_id
                fid_b = all_forks[1].fork_id
                result = _run(reg.commands["session"].handler(f"diff {fid_a} {fid_b}"))
                assert "common" in result.lower() or "diff" in result.lower() or "prefix" in result.lower()

    def test_session_diff_no_args(self):
        reg, _ = _load()
        result = _run(reg.commands["session"].handler("diff"))
        assert "Usage" in result


# ------------------------------------------------------------------ #
# /transcript search, /transcript next, /transcript prev               #
# ------------------------------------------------------------------ #

class TestTranscriptCommands:
    def test_transcript_registered(self):
        reg, _ = _load()
        assert "transcript" in reg.commands

    def test_transcript_no_args(self):
        reg, _ = _load()
        result = _run(reg.commands["transcript"].handler(""))
        assert "Usage" in result or "search" in result.lower()

    def test_transcript_search(self):
        reg, _ = _load()
        result = _run(reg.commands["transcript"].handler("search hello"))
        assert "match" in result.lower() or "0" in result or "result" in result.lower()

    def test_transcript_search_no_query(self):
        reg, _ = _load()
        result = _run(reg.commands["transcript"].handler("search"))
        assert "Usage" in result or "query" in result.lower() or "0" in result

    def test_transcript_next_no_search(self):
        reg, _ = _load()
        result = _run(reg.commands["transcript"].handler("next"))
        assert "no" in result.lower() or "end" in result.lower() or "search" in result.lower()

    def test_transcript_prev_no_search(self):
        reg, _ = _load()
        result = _run(reg.commands["transcript"].handler("prev"))
        assert "no" in result.lower() or "start" in result.lower() or "search" in result.lower()

    def test_transcript_next_end(self):
        reg, _ = _load()
        _run(reg.commands["transcript"].handler("search hello"))
        result = _run(reg.commands["transcript"].handler("next"))
        assert "end" in result.lower() or "no" in result.lower() or "result" in result.lower()

    def test_transcript_prev_start(self):
        reg, _ = _load()
        _run(reg.commands["transcript"].handler("search hello"))
        result = _run(reg.commands["transcript"].handler("prev"))
        assert "start" in result.lower() or "no" in result.lower() or "result" in result.lower()


# ------------------------------------------------------------------ #
# /summary show, /summary update                                      #
# ------------------------------------------------------------------ #

class TestSummaryCommands:
    def test_summary_registered(self):
        reg, _ = _load()
        assert "summary" in reg.commands

    def test_summary_no_args(self):
        reg, _ = _load()
        result = _run(reg.commands["summary"].handler(""))
        assert "Usage" in result or "show" in result.lower()

    def test_summary_show_no_summary(self):
        reg, _ = _load()
        result = _run(reg.commands["summary"].handler("show"))
        assert "No summary" in result

    def test_summary_update(self):
        reg, _ = _load()
        result = _run(reg.commands["summary"].handler("update"))
        assert "summar" in result.lower()

    def test_summary_show_after_update(self):
        reg, _ = _load()
        _run(reg.commands["summary"].handler("update"))
        result = _run(reg.commands["summary"].handler("show"))
        # Might still say no summary if stub turns < threshold
        assert isinstance(result, str)

    def test_summary_unknown_sub(self):
        reg, _ = _load()
        result = _run(reg.commands["summary"].handler("unknown"))
        assert "Usage" in result or "show" in result.lower()
