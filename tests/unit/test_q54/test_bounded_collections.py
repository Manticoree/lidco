"""Q54/366 — bounded collections in CommandRegistry."""
from __future__ import annotations

import pytest
from collections import deque


class TestBoundedCollections:
    def test_edited_files_is_deque(self):
        from lidco.cli.commands import CommandRegistry
        cr = CommandRegistry()
        assert isinstance(cr._edited_files, deque)

    def test_turn_times_is_deque(self):
        from lidco.cli.commands import CommandRegistry
        cr = CommandRegistry()
        assert isinstance(cr._turn_times, deque)

    def test_edited_files_max_200(self):
        from lidco.cli.commands import CommandRegistry
        cr = CommandRegistry()
        for i in range(250):
            cr._edited_files.append(f"file_{i}.py")
        assert len(cr._edited_files) == 200
        # Oldest entries dropped, newest kept
        assert cr._edited_files[-1] == "file_249.py"

    def test_turn_times_max_500(self):
        from lidco.cli.commands import CommandRegistry
        cr = CommandRegistry()
        for i in range(600):
            cr._turn_times.append(float(i))
        assert len(cr._turn_times) == 500
        assert cr._turn_times[-1] == 599.0
