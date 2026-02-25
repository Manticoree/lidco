"""Tests for ArchDiagramTool and rendering helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lidco.tools.arch_diagram import ArchDiagramTool, _build_tree, _render_top_level_summary


# ---------------------------------------------------------------------------
# _build_tree
# ---------------------------------------------------------------------------

class TestBuildTree:
    def test_empty_adjacency(self) -> None:
        assert _build_tree({}, "root", 2, set()) == []

    def test_single_child(self) -> None:
        adj = {"root": {"child.py"}}
        lines = _build_tree(adj, "root", 2, set())
        assert len(lines) == 1
        assert "child.py" in lines[0]
        assert "└──" in lines[0]

    def test_multiple_children_sorted(self) -> None:
        adj = {"root": {"b.py", "a.py", "c.py"}}
        lines = _build_tree(adj, "root", 2, set())
        names = [l.strip().lstrip("├── ").lstrip("└── ") for l in lines]
        assert names == sorted(names)

    def test_max_depth_respected(self) -> None:
        adj = {"root": {"child"}, "child": {"grandchild"}}
        lines = _build_tree(adj, "root", 1, set())
        combined = "\n".join(lines)
        assert "grandchild" not in combined

    def test_depth_2_shows_grandchildren(self) -> None:
        adj = {"root": {"child"}, "child": {"grandchild.py"}}
        lines = _build_tree(adj, "root", 2, set())
        combined = "\n".join(lines)
        assert "grandchild.py" in combined

    def test_cycle_prevention(self) -> None:
        adj = {"a": {"b"}, "b": {"a"}}
        # Should not recurse infinitely
        lines = _build_tree(adj, "a", 3, set())
        assert len(lines) < 10


# ---------------------------------------------------------------------------
# _render_top_level_summary
# ---------------------------------------------------------------------------

class TestRenderTopLevelSummary:
    def _make_graph(self, imports: dict, imported_by: dict) -> MagicMock:
        g = MagicMock()
        g._imports = {k: set(v) for k, v in imports.items()}
        g._imported_by = {k: set(v) for k, v in imported_by.items()}
        g._ensure_built = MagicMock()
        return g

    def test_empty_graph_shows_no_index_message(self) -> None:
        g = self._make_graph({}, {})
        result = _render_top_level_summary(g)
        assert "No import relationships" in result

    def test_shows_most_imported(self) -> None:
        g = self._make_graph(
            {},
            {"base.py": ["a.py", "b.py", "c.py"]},
        )
        result = _render_top_level_summary(g)
        assert "base.py" in result
        assert "3" in result

    def test_shows_most_dependencies(self) -> None:
        g = self._make_graph(
            {"heavy.py": ["x.py", "y.py", "z.py"]},
            {},
        )
        result = _render_top_level_summary(g)
        assert "heavy.py" in result


# ---------------------------------------------------------------------------
# ArchDiagramTool
# ---------------------------------------------------------------------------

class TestArchDiagramTool:
    def setup_method(self) -> None:
        self.tool = ArchDiagramTool()

    def test_name(self) -> None:
        assert self.tool.name == "arch_diagram"

    def test_has_three_parameters(self) -> None:
        names = {p.name for p in self.tool.parameters}
        assert names == {"root_path", "direction", "max_depth"}

    @pytest.mark.asyncio
    async def test_invalid_direction_returns_error(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = await self.tool._run(direction="circular")
        assert result.success is False
        assert "direction" in result.error.lower()

    @pytest.mark.asyncio
    async def test_missing_index_returns_error(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = await self.tool._run()
        assert result.success is False
        assert "index" in result.error.lower()

    @pytest.mark.asyncio
    async def test_with_index_returns_diagram(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        # Create the .lidco dir so Path.exists() is satisfied
        db_dir = tmp_path / ".lidco"
        db_dir.mkdir()
        (db_dir / "project_index.db").write_bytes(b"")

        mock_graph = MagicMock()
        mock_graph._imports = {"a.py": {"b.py"}}
        mock_graph._imported_by = {"b.py": {"a.py"}}
        mock_graph._ensure_built = MagicMock()

        # Imports happen inside _run(), so patch at source location
        with patch("lidco.index.db.IndexDatabase"), \
             patch("lidco.index.dependency_graph.DependencyGraph", return_value=mock_graph):
            result = await self.tool._run(root_path="b.py", direction="dependents")

        assert result.success is True
        assert "b.py" in result.output
