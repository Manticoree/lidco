"""Tests for search tools (glob, grep)."""

import pytest

from lidco.tools.glob import GlobTool
from lidco.tools.grep import GrepTool
from lidco.tools.base import ToolPermission


class TestGlobTool:
    def setup_method(self):
        self.tool = GlobTool()

    def test_name(self):
        assert self.tool.name == "glob"

    def test_permission_is_auto(self):
        assert self.tool.permission == ToolPermission.AUTO

    @pytest.mark.asyncio
    async def test_find_python_files(self, tmp_path):
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "b.py").write_text("pass")
        (tmp_path / "c.txt").write_text("text")
        result = await self.tool.execute(pattern="*.py", path=str(tmp_path))
        assert result.success is True
        assert "a.py" in result.output
        assert "b.py" in result.output
        assert "c.txt" not in result.output

    @pytest.mark.asyncio
    async def test_recursive_glob(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.py").write_text("pass")
        result = await self.tool.execute(pattern="**/*.py", path=str(tmp_path))
        assert result.success is True
        assert "deep.py" in result.output

    @pytest.mark.asyncio
    async def test_no_matches(self, tmp_path):
        result = await self.tool.execute(pattern="*.xyz", path=str(tmp_path))
        assert result.success is True
        assert result.metadata["count"] == 0

    @pytest.mark.asyncio
    async def test_nonexistent_dir(self, tmp_path):
        result = await self.tool.execute(pattern="*", path=str(tmp_path / "nope"))
        assert result.success is False


class TestGrepTool:
    def setup_method(self):
        self.tool = GrepTool()

    def test_name(self):
        assert self.tool.name == "grep"

    def test_permission_is_auto(self):
        assert self.tool.permission == ToolPermission.AUTO

    @pytest.mark.asyncio
    async def test_find_pattern(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello():\n    print('world')\n")
        result = await self.tool.execute(pattern="hello", path=str(tmp_path))
        assert result.success is True
        assert "hello" in result.output
        assert result.metadata["count"] >= 1

    @pytest.mark.asyncio
    async def test_case_insensitive(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("Hello World\n")
        result = await self.tool.execute(
            pattern="hello", path=str(tmp_path), case_insensitive=True
        )
        assert result.success is True
        assert result.metadata["count"] >= 1

    @pytest.mark.asyncio
    async def test_no_matches(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("some content\n")
        result = await self.tool.execute(pattern="zzzznotfound", path=str(tmp_path))
        assert result.success is True
        assert result.metadata["count"] == 0

    @pytest.mark.asyncio
    async def test_regex_pattern(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("foo123\nbar456\nfoo789\n")
        result = await self.tool.execute(pattern=r"foo\d+", path=str(tmp_path))
        assert result.success is True
        assert result.metadata["count"] == 2

    @pytest.mark.asyncio
    async def test_invalid_regex(self, tmp_path):
        result = await self.tool.execute(pattern="[invalid", path=str(tmp_path))
        assert result.success is False
        assert "regex" in result.error.lower()

    @pytest.mark.asyncio
    async def test_search_single_file(self, tmp_path):
        f = tmp_path / "target.py"
        f.write_text("target_line\nother_line\n")
        result = await self.tool.execute(pattern="target", path=str(f))
        assert result.success is True
        assert result.metadata["count"] >= 1

    @pytest.mark.asyncio
    async def test_include_filter(self, tmp_path):
        (tmp_path / "a.py").write_text("findme\n")
        (tmp_path / "b.txt").write_text("findme\n")
        result = await self.tool.execute(
            pattern="findme", path=str(tmp_path), include="*.py"
        )
        assert result.success is True
        assert "a.py" in result.output
        assert "b.txt" not in result.output
