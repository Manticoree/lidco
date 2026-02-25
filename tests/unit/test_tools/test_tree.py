"""Tests for TreeTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.tools.tree import TreeTool


@pytest.fixture()
def tool() -> TreeTool:
    return TreeTool()


def _make_fs(root: Path) -> None:
    """Create a small fixture directory tree."""
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("# main")
    (root / "src" / "utils.py").write_text("# utils")
    (root / "src" / "sub").mkdir()
    (root / "src" / "sub" / "helper.py").write_text("# helper")
    (root / "tests").mkdir()
    (root / "tests" / "test_main.py").write_text("# test")
    (root / "README.md").write_text("# readme")
    (root / ".hidden_file").write_text("secret")
    (root / ".hidden_dir").mkdir()
    (root / ".hidden_dir" / "inner.txt").write_text("x")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "main.cpython-313.pyc").write_bytes(b"\x00")


class TestTreeToolMeta:
    def test_name(self, tool: TreeTool) -> None:
        assert tool.name == "tree"

    def test_schema_structure(self, tool: TreeTool) -> None:
        schema = tool.to_openai_schema()
        params = schema["function"]["parameters"]["properties"]
        assert "path" in params
        assert "max_depth" in params
        assert "show_hidden" in params

    def test_no_required_params(self, tool: TreeTool) -> None:
        schema = tool.to_openai_schema()
        required = schema["function"]["parameters"].get("required", [])
        assert required == []


class TestTreeToolOutput:
    @pytest.mark.asyncio
    async def test_shows_files_and_dirs(self, tool: TreeTool, tmp_path: Path) -> None:
        _make_fs(tmp_path)
        result = await tool._run(path=str(tmp_path))
        assert result.success
        assert "src/" in result.output
        assert "tests/" in result.output
        assert "README.md" in result.output

    @pytest.mark.asyncio
    async def test_hidden_excluded_by_default(self, tool: TreeTool, tmp_path: Path) -> None:
        _make_fs(tmp_path)
        result = await tool._run(path=str(tmp_path))
        assert result.success
        assert ".hidden_file" not in result.output
        assert ".hidden_dir" not in result.output

    @pytest.mark.asyncio
    async def test_show_hidden_includes_dotfiles(self, tool: TreeTool, tmp_path: Path) -> None:
        _make_fs(tmp_path)
        result = await tool._run(path=str(tmp_path), show_hidden=True)
        assert result.success
        assert ".hidden_file" in result.output

    @pytest.mark.asyncio
    async def test_pycache_always_excluded(self, tool: TreeTool, tmp_path: Path) -> None:
        _make_fs(tmp_path)
        result = await tool._run(path=str(tmp_path), show_hidden=True)
        assert result.success
        assert "__pycache__" not in result.output

    @pytest.mark.asyncio
    async def test_max_depth_limits_output(self, tool: TreeTool, tmp_path: Path) -> None:
        _make_fs(tmp_path)
        result_1 = await tool._run(path=str(tmp_path), max_depth=1)
        result_3 = await tool._run(path=str(tmp_path), max_depth=3)
        # Depth-1 must not show nested sub/ contents
        assert "helper.py" not in result_1.output
        # Depth-3 must show nested contents
        assert "helper.py" in result_3.output

    @pytest.mark.asyncio
    async def test_root_shown_as_first_line(self, tool: TreeTool, tmp_path: Path) -> None:
        _make_fs(tmp_path)
        result = await tool._run(path=str(tmp_path))
        assert result.output.startswith(str(tmp_path))

    @pytest.mark.asyncio
    async def test_summary_line_present(self, tool: TreeTool, tmp_path: Path) -> None:
        _make_fs(tmp_path)
        result = await tool._run(path=str(tmp_path))
        assert "entries" in result.output

    @pytest.mark.asyncio
    async def test_metadata_entry_count(self, tool: TreeTool, tmp_path: Path) -> None:
        _make_fs(tmp_path)
        result = await tool._run(path=str(tmp_path))
        assert result.metadata["entry_count"] > 0
        assert result.metadata["truncated"] == 0


class TestTreeToolTruncation:
    @pytest.mark.asyncio
    async def test_truncation_when_many_files(self, tool: TreeTool, tmp_path: Path) -> None:
        from lidco.tools.tree import _MAX_ENTRIES
        # Create more files than the limit
        for i in range(_MAX_ENTRIES + 10):
            (tmp_path / f"file_{i:04d}.py").write_text("")

        result = await tool._run(path=str(tmp_path))
        assert result.success
        assert result.metadata["truncated"] > 0
        assert "more entries" in result.output


class TestTreeToolErrors:
    @pytest.mark.asyncio
    async def test_nonexistent_path(self, tool: TreeTool, tmp_path: Path) -> None:
        result = await tool._run(path=str(tmp_path / "ghost"))
        assert not result.success
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_file_not_directory(self, tool: TreeTool, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("x")
        result = await tool._run(path=str(f))
        assert not result.success
        assert "not a directory" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_directory(self, tool: TreeTool, tmp_path: Path) -> None:
        result = await tool._run(path=str(tmp_path))
        assert result.success
        assert result.metadata["entry_count"] == 0


class TestTreeToolRegistered:
    def test_tree_in_default_registry(self) -> None:
        from lidco.tools.registry import ToolRegistry
        registry = ToolRegistry.create_default_registry()
        assert registry.get("tree") is not None
