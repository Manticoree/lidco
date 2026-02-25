"""Tests for DiffTool."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.tools.diff import DiffTool


@pytest.fixture()
def tool() -> DiffTool:
    return DiffTool()


class TestDiffToolMeta:
    def test_name(self, tool: DiffTool) -> None:
        assert tool.name == "diff"

    def test_schema_structure(self, tool: DiffTool) -> None:
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        params = schema["function"]["parameters"]["properties"]
        assert "path_a" in params
        assert "path_b" in params
        assert "unified" in params

    def test_required_params(self, tool: DiffTool) -> None:
        schema = tool.to_openai_schema()
        required = schema["function"]["parameters"]["required"]
        assert "path_a" in required
        assert "path_b" in required
        assert "unified" not in required


class TestDiffToolIdentical:
    @pytest.mark.asyncio
    async def test_identical_files(self, tool: DiffTool, tmp_path: Path) -> None:
        f = tmp_path / "a.py"
        f.write_text("line1\nline2\n")
        g = tmp_path / "b.py"
        g.write_text("line1\nline2\n")

        result = await tool._run(path_a=str(f), path_b=str(g))
        assert result.success
        assert "identical" in result.output.lower()
        assert result.metadata["added"] == 0
        assert result.metadata["removed"] == 0
        assert result.metadata["identical"] is True


class TestDiffToolDifferent:
    @pytest.mark.asyncio
    async def test_shows_added_lines(self, tool: DiffTool, tmp_path: Path) -> None:
        a = tmp_path / "a.py"
        a.write_text("line1\n")
        b = tmp_path / "b.py"
        b.write_text("line1\nline2\n")

        result = await tool._run(path_a=str(a), path_b=str(b))
        assert result.success
        assert "+line2" in result.output
        assert result.metadata["added"] == 1
        assert result.metadata["removed"] == 0

    @pytest.mark.asyncio
    async def test_shows_removed_lines(self, tool: DiffTool, tmp_path: Path) -> None:
        a = tmp_path / "a.py"
        a.write_text("line1\nline2\n")
        b = tmp_path / "b.py"
        b.write_text("line1\n")

        result = await tool._run(path_a=str(a), path_b=str(b))
        assert result.success
        assert "-line2" in result.output
        assert result.metadata["removed"] == 1
        assert result.metadata["added"] == 0

    @pytest.mark.asyncio
    async def test_added_and_removed(self, tool: DiffTool, tmp_path: Path) -> None:
        a = tmp_path / "a.py"
        a.write_text("alpha\nbeta\n")
        b = tmp_path / "b.py"
        b.write_text("alpha\ngamma\ndelta\n")

        result = await tool._run(path_a=str(a), path_b=str(b))
        assert result.success
        assert result.metadata["added"] >= 1
        assert result.metadata["removed"] >= 1

    @pytest.mark.asyncio
    async def test_unified_context_lines(self, tool: DiffTool, tmp_path: Path) -> None:
        lines = [f"line{i}\n" for i in range(20)]
        a = tmp_path / "a.py"
        a.write_text("".join(lines))
        b_lines = lines.copy()
        b_lines[10] = "CHANGED\n"
        b = tmp_path / "b.py"
        b.write_text("".join(b_lines))

        result_1 = await tool._run(path_a=str(a), path_b=str(b), unified=1)
        result_5 = await tool._run(path_a=str(a), path_b=str(b), unified=5)
        # More context → more lines in output
        assert len(result_5.output) > len(result_1.output)

    @pytest.mark.asyncio
    async def test_includes_file_names_in_header(self, tool: DiffTool, tmp_path: Path) -> None:
        a = tmp_path / "original.py"
        a.write_text("x = 1\n")
        b = tmp_path / "modified.py"
        b.write_text("x = 2\n")

        result = await tool._run(path_a=str(a), path_b=str(b))
        assert "original.py" in result.output
        assert "modified.py" in result.output


class TestDiffToolErrors:
    @pytest.mark.asyncio
    async def test_missing_path_a(self, tool: DiffTool, tmp_path: Path) -> None:
        b = tmp_path / "b.py"
        b.write_text("x\n")
        result = await tool._run(path_a=str(tmp_path / "ghost.py"), path_b=str(b))
        assert not result.success
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_missing_path_b(self, tool: DiffTool, tmp_path: Path) -> None:
        a = tmp_path / "a.py"
        a.write_text("x\n")
        result = await tool._run(path_a=str(a), path_b=str(tmp_path / "ghost.py"))
        assert not result.success

    @pytest.mark.asyncio
    async def test_empty_files(self, tool: DiffTool, tmp_path: Path) -> None:
        a = tmp_path / "a.py"
        a.write_text("")
        b = tmp_path / "b.py"
        b.write_text("")
        result = await tool._run(path_a=str(a), path_b=str(b))
        assert result.success
        assert result.metadata["identical"] is True


class TestDiffToolRegistered:
    def test_diff_in_default_registry(self) -> None:
        from lidco.tools.registry import ToolRegistry
        registry = ToolRegistry.create_default_registry()
        assert registry.get("diff") is not None
