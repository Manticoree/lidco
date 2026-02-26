"""Tests for file tools (read, write, edit)."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from lidco.tools.file_read import FileReadTool
from lidco.tools.file_write import FileWriteTool
from lidco.tools.file_edit import FileEditTool
from lidco.tools.base import ToolPermission


class TestFileReadTool:
    def setup_method(self):
        self.tool = FileReadTool()

    def test_name(self):
        assert self.tool.name == "file_read"

    def test_permission_is_auto(self):
        assert self.tool.permission == ToolPermission.AUTO

    @pytest.mark.asyncio
    async def test_read_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\n")
        result = await self.tool.execute(path=str(f))
        assert result.success is True
        assert "line1" in result.output
        assert "line2" in result.output

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, tmp_path):
        result = await self.tool.execute(path=str(tmp_path / "nope.txt"))
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_read_with_offset(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("line1\nline2\nline3\nline4\n")
        result = await self.tool.execute(path=str(f), offset=2, limit=2)
        assert result.success is True
        assert "line2" in result.output
        assert "line3" in result.output
        assert "line1" not in result.output

    @pytest.mark.asyncio
    async def test_read_directory_fails(self, tmp_path):
        result = await self.tool.execute(path=str(tmp_path))
        assert result.success is False

    def test_openai_schema(self):
        schema = self.tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "file_read"
        assert "path" in schema["function"]["parameters"]["properties"]


class TestFileReadCompression:
    """Tests for smart compression when reading large indexed files."""

    def _make_tool(self, tmp_path: Path, summary: str) -> FileReadTool:
        """Return a FileReadTool with a mock enricher and project_dir=tmp_path."""
        enricher = MagicMock()
        enricher.get_file_symbol_summary.return_value = summary
        return FileReadTool(enricher=enricher, project_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_small_file_not_compressed(self, tmp_path: Path) -> None:
        f = tmp_path / "small.py"
        f.write_text("x = 1\n" * 20)  # ~120 chars, below threshold
        tool = self._make_tool(tmp_path, "## File summary\n  - function foo · line 1")
        result = await tool.execute(path=str(f))
        assert result.success
        assert "## File summary" not in result.output

    @pytest.mark.asyncio
    async def test_large_file_not_indexed_not_compressed(self, tmp_path: Path) -> None:
        f = tmp_path / "large.py"
        f.write_text("x = 1\n" * 800)  # ~5600 chars, above threshold
        tool = self._make_tool(tmp_path, "")  # empty summary = not indexed
        result = await tool.execute(path=str(f))
        assert result.success
        assert "## File summary" not in result.output

    @pytest.mark.asyncio
    async def test_large_indexed_file_is_compressed(self, tmp_path: Path) -> None:
        f = tmp_path / "module.py"
        f.write_text("x = 1\n" * 800)  # above threshold
        tool = self._make_tool(tmp_path, "## File summary (module.py — 800 lines, 3 symbols)\n  - function foo · line 1")
        result = await tool.execute(path=str(f))
        assert result.success
        assert "## File summary" in result.output

    @pytest.mark.asyncio
    async def test_compressed_output_has_full_content_section(self, tmp_path: Path) -> None:
        f = tmp_path / "module.py"
        f.write_text("x = 1\n" * 800)
        tool = self._make_tool(tmp_path, "## File summary\n  - class Foo · line 1")
        result = await tool.execute(path=str(f))
        assert "## Full content" in result.output

    @pytest.mark.asyncio
    async def test_compressed_output_has_truncation_hint(self, tmp_path: Path) -> None:
        f = tmp_path / "module.py"
        f.write_text("x = 1\n" * 800)
        tool = self._make_tool(tmp_path, "## File summary\n  - class Foo · line 1")
        result = await tool.execute(path=str(f))
        assert "offset/limit" in result.output

    @pytest.mark.asyncio
    async def test_compressed_metadata_has_compressed_flag(self, tmp_path: Path) -> None:
        f = tmp_path / "module.py"
        f.write_text("x = 1\n" * 800)
        tool = self._make_tool(tmp_path, "## File summary\n  - class Foo · line 1")
        result = await tool.execute(path=str(f))
        assert result.metadata.get("compressed") is True

    @pytest.mark.asyncio
    async def test_offset_read_bypasses_compression(self, tmp_path: Path) -> None:
        """Reads with explicit offset should not be compressed."""
        f = tmp_path / "module.py"
        f.write_text("x = 1\n" * 800)
        tool = self._make_tool(tmp_path, "## File summary\n  - class Foo · line 1")
        result = await tool.execute(path=str(f), offset=50, limit=20)
        assert result.success
        assert "## File summary" not in result.output

    @pytest.mark.asyncio
    async def test_small_limit_bypasses_compression(self, tmp_path: Path) -> None:
        """limit < 50 bypasses compression (targeted read)."""
        f = tmp_path / "module.py"
        f.write_text("x = 1\n" * 800)
        tool = self._make_tool(tmp_path, "## File summary\n  - class Foo · line 1")
        result = await tool.execute(path=str(f), offset=1, limit=10)
        assert result.success
        assert "## File summary" not in result.output

    @pytest.mark.asyncio
    async def test_file_outside_project_dir_not_compressed(self, tmp_path: Path) -> None:
        """File outside project_dir cannot form a relative path → no compression."""
        import tempfile
        with tempfile.TemporaryDirectory() as other_dir:
            f = Path(other_dir) / "module.py"
            f.write_text("x = 1\n" * 800)
            # project_dir is tmp_path, file is in other_dir
            tool = self._make_tool(tmp_path, "## File summary\n  - class Foo · line 1")
            result = await tool.execute(path=str(f))
            assert result.success
            assert "## File summary" not in result.output

    @pytest.mark.asyncio
    async def test_no_enricher_no_compression(self, tmp_path: Path) -> None:
        """When enricher is not provided and project has no index, no compression."""
        f = tmp_path / "module.py"
        f.write_text("x = 1\n" * 800)
        # project_dir has no .lidco/project_index.db
        tool = FileReadTool(project_dir=tmp_path)
        result = await tool.execute(path=str(f))
        assert result.success
        assert "## File summary" not in result.output


class TestFileWriteTool:
    def setup_method(self):
        self.tool = FileWriteTool()

    def test_name(self):
        assert self.tool.name == "file_write"

    def test_permission_is_ask(self):
        assert self.tool.permission == ToolPermission.ASK

    @pytest.mark.asyncio
    async def test_write_new_file(self, tmp_path):
        f = tmp_path / "new.txt"
        result = await self.tool.execute(path=str(f), content="hello world")
        assert result.success is True
        assert f.read_text() == "hello world"

    @pytest.mark.asyncio
    async def test_write_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "sub" / "dir" / "file.txt"
        result = await self.tool.execute(path=str(f), content="deep")
        assert result.success is True
        assert f.read_text() == "deep"

    @pytest.mark.asyncio
    async def test_overwrite_existing(self, tmp_path):
        f = tmp_path / "existing.txt"
        f.write_text("old content")
        result = await self.tool.execute(path=str(f), content="new content")
        assert result.success is True
        assert f.read_text() == "new content"


class TestFileEditTool:
    def setup_method(self):
        self.tool = FileEditTool()

    def test_name(self):
        assert self.tool.name == "file_edit"

    @pytest.mark.asyncio
    async def test_replace_unique_string(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello():\n    print('hello')\n")
        result = await self.tool.execute(
            path=str(f), old_string="hello", new_string="world"
        )
        # "hello" appears twice, so without replace_all it should fail
        assert result.success is False

    @pytest.mark.asyncio
    async def test_replace_all(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("foo bar foo baz foo")
        result = await self.tool.execute(
            path=str(f), old_string="foo", new_string="qux", replace_all=True
        )
        assert result.success is True
        assert f.read_text() == "qux bar qux baz qux"

    @pytest.mark.asyncio
    async def test_replace_single_occurrence(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("unique_string here")
        result = await self.tool.execute(
            path=str(f), old_string="unique_string", new_string="replaced"
        )
        assert result.success is True
        assert f.read_text() == "replaced here"

    @pytest.mark.asyncio
    async def test_string_not_found(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("some content")
        result = await self.tool.execute(
            path=str(f), old_string="nonexistent", new_string="replaced"
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_edit_nonexistent_file(self, tmp_path):
        result = await self.tool.execute(
            path=str(tmp_path / "nope.py"), old_string="a", new_string="b"
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_context_preview_present_on_success(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("only_one_line")
        result = await self.tool.execute(
            path=str(f), old_string="only_one_line", new_string="replaced"
        )
        assert result.success is True
        assert "context_preview" in result.metadata

    @pytest.mark.asyncio
    async def test_context_preview_contains_new_string(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("alpha\nbeta\ngamma\n")
        result = await self.tool.execute(
            path=str(f), old_string="beta", new_string="BETA"
        )
        assert result.success is True
        assert "BETA" in result.metadata["context_preview"]

    @pytest.mark.asyncio
    async def test_anchor_line_correct(self, tmp_path):
        lines = [f"line{i}" for i in range(30)]
        f = tmp_path / "code.py"
        f.write_text("\n".join(lines))
        # "line15" is at index 15 (0-based)
        result = await self.tool.execute(
            path=str(f), old_string="line15", new_string="CHANGED"
        )
        assert result.success is True
        assert result.metadata["anchor_line"] == 15

    @pytest.mark.asyncio
    async def test_context_preview_clipped_at_file_start(self, tmp_path):
        """Edit on line 2 should not produce negative indices."""
        lines = [f"line{i}" for i in range(5)]
        f = tmp_path / "code.py"
        f.write_text("\n".join(lines))
        result = await self.tool.execute(
            path=str(f), old_string="line1", new_string="FIRST"
        )
        assert result.success is True
        preview = result.metadata["context_preview"]
        assert "line0" in preview  # beginning of file visible
        assert "FIRST" in preview

    @pytest.mark.asyncio
    async def test_context_preview_clipped_at_file_end(self, tmp_path):
        """Edit near end of file should not raise IndexError."""
        lines = [f"line{i}" for i in range(5)]
        f = tmp_path / "code.py"
        f.write_text("\n".join(lines))
        result = await self.tool.execute(
            path=str(f), old_string="line4", new_string="LAST"
        )
        assert result.success is True
        assert "LAST" in result.metadata["context_preview"]

    @pytest.mark.asyncio
    async def test_context_preview_spans_ten_lines_around_anchor(self, tmp_path):
        """Preview must include lines within ±10 of the anchor."""
        lines = [f"L{i:03d}" for i in range(50)]
        f = tmp_path / "code.py"
        f.write_text("\n".join(lines))
        # "L025" is at line 25; preview should include L015..L035
        result = await self.tool.execute(
            path=str(f), old_string="L025", new_string="CHANGED"
        )
        assert result.success is True
        preview = result.metadata["context_preview"]
        assert "L015" in preview
        assert "L035" in preview
        assert "L000" not in preview  # too far away
