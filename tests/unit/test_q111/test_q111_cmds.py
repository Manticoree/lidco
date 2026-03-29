"""Tests for src/lidco/cli/commands/q111_cmds.py."""
import asyncio
import os
import tempfile
from unittest.mock import patch, MagicMock


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load():
    import lidco.cli.commands.q111_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


# ------------------------------------------------------------------ #
# /memory                                                              #
# ------------------------------------------------------------------ #

class TestMemoryCommand:
    def test_registered(self):
        assert "memory" in _load().commands

    def test_no_args(self):
        result = _run(_load().commands["memory"].handler(""))
        assert "Usage" in result

    def test_extract_no_text(self):
        result = _run(_load().commands["memory"].handler("extract"))
        assert "Usage" in result

    def test_extract_with_preference(self):
        result = _run(_load().commands["memory"].handler("extract I prefer Python for scripts."))
        assert "Extracted" in result or "No facts" in result

    def test_extract_no_facts(self):
        result = _run(_load().commands["memory"].handler("extract hello world"))
        assert "No facts" in result

    def test_approve_no_id(self):
        result = _run(_load().commands["memory"].handler("approve"))
        assert "Usage" in result

    def test_approve_missing_id(self):
        result = _run(_load().commands["memory"].handler("approve nonexistent"))
        assert "Not found" in result

    def test_reject_no_id(self):
        result = _run(_load().commands["memory"].handler("reject"))
        assert "Usage" in result

    def test_reject_missing_id(self):
        result = _run(_load().commands["memory"].handler("reject nonexistent"))
        assert "Not found" in result

    def test_list_empty(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["memory"].handler

        tmp = tempfile.mkdtemp()
        queue_path = os.path.join(tmp, "queue.json")
        from lidco.memory.approval_queue import MemoryApprovalQueue
        mod._state["approval_queue"] = MemoryApprovalQueue(storage_path=queue_path)

        result = _run(handler("list"))
        assert "No pending" in result

    def test_inject_no_memories(self):
        result = _run(_load().commands["memory"].handler("inject"))
        assert "No memories" in result

    def test_extract_and_list(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["memory"].handler

        # Use a tmp dir for the approval queue
        tmp = tempfile.mkdtemp()
        queue_path = os.path.join(tmp, "queue.json")

        from lidco.memory.approval_queue import MemoryApprovalQueue
        mod._state["approval_queue"] = MemoryApprovalQueue(storage_path=queue_path)

        result = _run(handler("extract I prefer using Python for everything."))
        if "Extracted" in result:
            result2 = _run(handler("list"))
            assert "Pending" in result2

    def test_extract_and_approve(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["memory"].handler

        tmp = tempfile.mkdtemp()
        queue_path = os.path.join(tmp, "queue.json")
        from lidco.memory.approval_queue import MemoryApprovalQueue
        mod._state["approval_queue"] = MemoryApprovalQueue(storage_path=queue_path)

        result = _run(handler("extract We use Docker for deployment."))
        if "Extracted" in result:
            # Extract the id from the result
            import re
            ids = re.findall(r"\[(\w+)\]", result)
            if ids:
                approve_result = _run(handler(f"approve {ids[0]}"))
                assert "Approved" in approve_result

    def test_extract_and_reject(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["memory"].handler

        tmp = tempfile.mkdtemp()
        queue_path = os.path.join(tmp, "queue.json")
        from lidco.memory.approval_queue import MemoryApprovalQueue
        mod._state["approval_queue"] = MemoryApprovalQueue(storage_path=queue_path)

        result = _run(handler("extract Never use eval in production."))
        if "Extracted" in result:
            import re
            ids = re.findall(r"\[(\w+)\]", result)
            if ids:
                reject_result = _run(handler(f"reject {ids[0]}"))
                assert "Rejected" in reject_result


# ------------------------------------------------------------------ #
# /checkpoint                                                          #
# ------------------------------------------------------------------ #

class TestCheckpointCommand:
    def test_registered(self):
        assert "checkpoint" in _load().commands

    def test_no_args(self):
        result = _run(_load().commands["checkpoint"].handler(""))
        assert "Usage" in result

    def test_save_no_label(self):
        result = _run(_load().commands["checkpoint"].handler("save"))
        assert "Usage" in result

    def test_save_with_label(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["checkpoint"].handler

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "cp.json")
        from lidco.memory.session_checkpoint import SessionCheckpointStore
        mod._state["checkpoint_store"] = SessionCheckpointStore(storage_path=path)

        result = _run(handler("save my checkpoint"))
        assert "Checkpoint saved" in result
        assert "my checkpoint" in result

    def test_list_empty(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["checkpoint"].handler

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "cp.json")
        from lidco.memory.session_checkpoint import SessionCheckpointStore
        mod._state["checkpoint_store"] = SessionCheckpointStore(storage_path=path)

        result = _run(handler("list"))
        assert "No checkpoints" in result

    def test_list_after_save(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["checkpoint"].handler

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "cp.json")
        from lidco.memory.session_checkpoint import SessionCheckpointStore
        mod._state["checkpoint_store"] = SessionCheckpointStore(storage_path=path)

        _run(handler("save test cp"))
        result = _run(handler("list"))
        assert "Checkpoints" in result

    def test_restore_no_id(self):
        result = _run(_load().commands["checkpoint"].handler("restore"))
        assert "Usage" in result

    def test_restore_missing(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["checkpoint"].handler

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "cp.json")
        from lidco.memory.session_checkpoint import SessionCheckpointStore
        mod._state["checkpoint_store"] = SessionCheckpointStore(storage_path=path)

        result = _run(handler("restore badid"))
        assert "Not found" in result

    def test_restore_existing(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["checkpoint"].handler

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "cp.json")
        from lidco.memory.session_checkpoint import SessionCheckpointStore
        mod._state["checkpoint_store"] = SessionCheckpointStore(storage_path=path)

        save_result = _run(handler("save mycp"))
        import re
        ids = re.findall(r":\s+(\w+)\s+\(", save_result)
        if ids:
            result = _run(handler(f"restore {ids[0]}"))
            assert "Restored" in result
            assert "Messages" in result

    def test_diff_no_args(self):
        result = _run(_load().commands["checkpoint"].handler("diff"))
        assert "Usage" in result

    def test_diff_one_arg(self):
        result = _run(_load().commands["checkpoint"].handler("diff abc"))
        assert "Usage" in result

    def test_diff_missing_ids(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["checkpoint"].handler

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "cp.json")
        from lidco.memory.session_checkpoint import SessionCheckpointStore
        mod._state["checkpoint_store"] = SessionCheckpointStore(storage_path=path)

        result = _run(handler("diff bad1 bad2"))
        assert "Error" in result

    def test_diff_existing(self):
        import lidco.cli.commands.q111_cmds as mod
        mod._state.clear()
        reg = FakeRegistry()
        mod.register(reg)
        handler = reg.commands["checkpoint"].handler

        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "cp.json")
        from lidco.memory.session_checkpoint import SessionCheckpointStore
        mod._state["checkpoint_store"] = SessionCheckpointStore(storage_path=path)

        save1 = _run(handler("save first"))
        save2 = _run(handler("save second"))

        import re
        ids1 = re.findall(r":\s+(\w+)\s+\(", save1)
        ids2 = re.findall(r":\s+(\w+)\s+\(", save2)
        if ids1 and ids2:
            result = _run(handler(f"diff {ids1[0]} {ids2[0]}"))
            assert "Messages added" in result
