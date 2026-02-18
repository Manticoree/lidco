"""Tests for file tools (read, write, edit)."""

import pytest
from pathlib import Path

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
