"""Tests for src/lidco/memory/session_fork.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


PARENT_TURNS = [
    {"role": "user", "content": "hello"},
    {"role": "assistant", "content": "hi there"},
    {"role": "user", "content": "how are you"},
    {"role": "assistant", "content": "great"},
    {"role": "user", "content": "bye"},
]


class TestSessionFork:
    def test_dataclass_fields(self):
        from lidco.memory.session_fork import SessionFork
        fork = SessionFork(
            fork_id="f1", parent_session_id="s1", title="Test",
            branch_point_turn=3, turns=[{"role": "user", "content": "x"}]
        )
        assert fork.fork_id == "f1"
        assert fork.parent_session_id == "s1"
        assert fork.title == "Test"
        assert fork.branch_point_turn == 3
        assert len(fork.turns) == 1

    def test_default_created_at(self):
        from lidco.memory.session_fork import SessionFork
        fork = SessionFork(fork_id="f", parent_session_id="s", title="T",
                           branch_point_turn=0, turns=[])
        assert fork.created_at == ""


class TestSessionForkManagerCreate:
    def test_create_copies_all_turns(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "Fork All", PARENT_TURNS)
        assert len(fork.turns) == 5
        assert fork.parent_session_id == "s1"
        assert fork.title == "Fork All"
        assert fork.branch_point_turn == 5

    def test_create_with_branch_point(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "Fork Partial", PARENT_TURNS, branch_point_turn=3)
        assert len(fork.turns) == 3
        assert fork.branch_point_turn == 3
        assert fork.turns[0]["content"] == "hello"
        assert fork.turns[2]["content"] == "how are you"

    def test_create_branch_zero(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "Empty Fork", PARENT_TURNS, branch_point_turn=0)
        assert len(fork.turns) == 0

    def test_create_generates_unique_ids(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        f1 = mgr.create("s1", "A", PARENT_TURNS)
        f2 = mgr.create("s1", "B", PARENT_TURNS)
        assert f1.fork_id != f2.fork_id

    def test_create_deep_copies_turns(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "Deep", PARENT_TURNS, branch_point_turn=2)
        # Modifying original should not affect fork
        assert fork.turns[0] is not PARENT_TURNS[0]

    def test_create_empty_parent(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "Empty", [])
        assert len(fork.turns) == 0

    def test_create_sets_created_at(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "T", PARENT_TURNS)
        assert fork.created_at != ""


class TestSessionForkManagerGetListDelete:
    def test_get_existing(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "T", PARENT_TURNS)
        retrieved = mgr.get(fork.fork_id)
        assert retrieved is not None
        assert retrieved.fork_id == fork.fork_id

    def test_get_nonexistent(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        assert mgr.get("nonexistent") is None

    def test_list_all_empty(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        assert mgr.list_all() == []

    def test_list_all_multiple(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        mgr.create("s1", "A", PARENT_TURNS)
        mgr.create("s1", "B", PARENT_TURNS)
        mgr.create("s2", "C", PARENT_TURNS)
        assert len(mgr.list_all()) == 3

    def test_delete_existing(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "T", PARENT_TURNS)
        mgr.delete(fork.fork_id)
        assert mgr.get(fork.fork_id) is None
        assert len(mgr.list_all()) == 0

    def test_delete_nonexistent(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        mgr.delete("nope")  # should not raise


class TestSessionForkManagerDiff:
    def test_diff_identical_forks(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        f1 = mgr.create("s1", "A", PARENT_TURNS)
        f2 = mgr.create("s1", "B", PARENT_TURNS)
        diff = mgr.diff(f1.fork_id, f2.fork_id)
        assert diff.common_prefix_turns == 5
        assert diff.added == 0
        assert diff.removed == 0

    def test_diff_divergent_forks(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        f1 = mgr.create("s1", "A", PARENT_TURNS, branch_point_turn=3)
        f2 = mgr.create("s1", "B", PARENT_TURNS, branch_point_turn=3)
        # Append different turns
        mgr.append_turn(f1.fork_id, {"role": "user", "content": "fork1 extra"})
        mgr.append_turn(f2.fork_id, {"role": "user", "content": "fork2 extra"})
        mgr.append_turn(f2.fork_id, {"role": "assistant", "content": "fork2 extra2"})
        diff = mgr.diff(f1.fork_id, f2.fork_id)
        assert diff.common_prefix_turns == 3
        assert diff.added == 2  # fork_b has 2 extra after prefix
        assert diff.removed == 1  # fork_a has 1 extra after prefix

    def test_diff_one_empty(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        f1 = mgr.create("s1", "A", PARENT_TURNS, branch_point_turn=0)
        f2 = mgr.create("s1", "B", PARENT_TURNS, branch_point_turn=3)
        diff = mgr.diff(f1.fork_id, f2.fork_id)
        assert diff.common_prefix_turns == 0
        assert diff.added == 3
        assert diff.removed == 0

    def test_diff_ids_in_result(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        f1 = mgr.create("s1", "A", PARENT_TURNS)
        f2 = mgr.create("s1", "B", PARENT_TURNS)
        diff = mgr.diff(f1.fork_id, f2.fork_id)
        assert diff.fork_a_id == f1.fork_id
        assert diff.fork_b_id == f2.fork_id


class TestSessionForkManagerAppendTurn:
    def test_append_turn(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "T", PARENT_TURNS, branch_point_turn=2)
        updated = mgr.append_turn(fork.fork_id, {"role": "user", "content": "new"})
        assert len(updated.turns) == 3
        assert updated.turns[-1]["content"] == "new"

    def test_append_turn_persists(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "T", PARENT_TURNS, branch_point_turn=1)
        mgr.append_turn(fork.fork_id, {"role": "user", "content": "added"})
        retrieved = mgr.get(fork.fork_id)
        assert len(retrieved.turns) == 2

    def test_append_turn_nonexistent_raises(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        try:
            mgr.append_turn("nope", {"role": "user", "content": "x"})
            assert False, "Should have raised"
        except (KeyError, ValueError):
            pass

    def test_append_multiple_turns(self):
        from lidco.memory.session_fork import SessionForkManager
        mgr = SessionForkManager()
        fork = mgr.create("s1", "T", [], branch_point_turn=0)
        mgr.append_turn(fork.fork_id, {"role": "user", "content": "a"})
        mgr.append_turn(fork.fork_id, {"role": "assistant", "content": "b"})
        mgr.append_turn(fork.fork_id, {"role": "user", "content": "c"})
        result = mgr.get(fork.fork_id)
        assert len(result.turns) == 3
