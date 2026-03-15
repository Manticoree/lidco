"""Tests for DuplicateDetector — Task 338."""

from __future__ import annotations

import pytest

from lidco.analysis.duplicate_detector import DuplicateBlock, DuplicateDetector


_BLOCK = """\
def helper(x):
    if x:
        return x * 2
    return 0
result = helper(5)
"""

_CLONE_A = "def foo():\n" + _BLOCK
_CLONE_B = "def bar():\n" + _BLOCK


class TestDuplicateBlock:
    def test_frozen(self):
        b = DuplicateBlock("a.py", "b.py", (1, 5), (10, 14), 5)
        with pytest.raises((AttributeError, TypeError)):
            b.size = 10  # type: ignore[misc]


class TestDuplicateDetector:
    def setup_method(self):
        self.dd = DuplicateDetector()

    def test_empty_sources(self):
        assert self.dd.detect({}) == []

    def test_no_duplicates(self):
        sources = {
            "a.py": "def foo():\n    return 1\n",
            "b.py": "def bar():\n    return 2\n",
        }
        # min_lines=5 but files are only 2 lines each
        result = self.dd.detect(sources, min_lines=5)
        assert result == []

    def test_identical_files_detected(self):
        code = "\n".join(f"line_{i} = {i}" for i in range(10))
        sources = {"a.py": code, "b.py": code}
        result = self.dd.detect(sources, min_lines=5)
        assert len(result) >= 1

    def test_duplicate_block_attributes(self):
        code = "\n".join(f"line_{i} = {i}" for i in range(10))
        sources = {"a.py": code, "b.py": code}
        result = self.dd.detect(sources, min_lines=5)
        block = result[0]
        assert block.size == 5
        assert isinstance(block.lines_a, tuple)
        assert isinstance(block.lines_b, tuple)

    def test_single_file_too_short(self):
        sources = {"a.py": "x = 1\n"}
        result = self.dd.detect(sources, min_lines=5)
        assert result == []

    def test_intra_file_duplication(self):
        # Same block appears twice in the same file
        block = "\n".join(f"statement_{i}()" for i in range(5))
        code = block + "\n\n" + block + "\n"
        sources = {"a.py": code}
        result = self.dd.detect(sources, min_lines=5)
        # Should detect that the same code repeats within the file
        assert len(result) >= 1
        assert result[0].file_a == "a.py"
        assert result[0].file_b == "a.py"

    def test_min_lines_threshold_respected(self):
        code = "\n".join(f"x_{i} = {i}" for i in range(10))
        sources = {"a.py": code, "b.py": code}
        result_5 = self.dd.detect(sources, min_lines=5)
        result_15 = self.dd.detect(sources, min_lines=15)
        assert len(result_5) >= 1
        assert len(result_15) == 0

    def test_canonical_order(self):
        code = "\n".join(f"val_{i} = True" for i in range(8))
        sources = {"a.py": code, "b.py": code}
        result = self.dd.detect(sources, min_lines=5)
        for block in result:
            # file_a should come before file_b lexicographically (canonical)
            assert (block.file_a, block.lines_a) <= (block.file_b, block.lines_b)
