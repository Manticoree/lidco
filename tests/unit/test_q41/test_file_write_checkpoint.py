"""Tests for Q41 — FileWriteTool checkpoint callback (Task 283)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.tools.file_write import FileWriteTool


@pytest.fixture()
def tool():
    t = FileWriteTool()
    t._sandbox = None
    t._confirm_callback = None
    t._checkpoint_callback = None
    return t


class TestFileWriteCheckpointCallback:
    def test_checkpoint_called_before_write(self, tmp_path, tool):
        p = tmp_path / "x.py"
        p.write_text("old")
        calls = []
        tool.set_checkpoint_callback(lambda path, old: calls.append((path, old)))

        asyncio.run(tool._run(path=str(p), content="new"))

        assert len(calls) == 1
        path_arg, old_arg = calls[0]
        assert str(p) in path_arg
        assert old_arg == "old"

    def test_checkpoint_called_for_new_file(self, tmp_path, tool):
        p = tmp_path / "new.py"
        calls = []
        tool.set_checkpoint_callback(lambda path, old: calls.append((path, old)))

        asyncio.run(tool._run(path=str(p), content="content"))

        assert len(calls) == 1
        assert calls[0][1] is None  # file did not exist

    def test_no_checkpoint_callback_no_error(self, tmp_path, tool):
        p = tmp_path / "y.py"
        # Should not raise even without a checkpoint callback
        result = asyncio.run(tool._run(path=str(p), content="x"))
        assert result.success is True

    def test_set_checkpoint_callback_stores_callback(self, tool):
        cb = MagicMock()
        tool.set_checkpoint_callback(cb)
        assert tool._checkpoint_callback is cb

    def test_set_checkpoint_callback_none(self, tool):
        tool.set_checkpoint_callback(None)
        assert tool._checkpoint_callback is None

    def test_checkpoint_exception_does_not_block_write(self, tmp_path, tool):
        p = tmp_path / "z.py"
        p.write_text("old")

        def bad_cb(path, old):
            raise RuntimeError("oops")

        tool.set_checkpoint_callback(bad_cb)
        result = asyncio.run(tool._run(path=str(p), content="new"))
        # Write should succeed despite callback error
        assert result.success is True
        assert p.read_text() == "new"
