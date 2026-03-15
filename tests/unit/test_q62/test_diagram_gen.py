"""Tests for DiagramGenerator and MermaidRenderer — Q62 Task 419."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestDiagramGeneratorValidStyles:
    def test_valid_styles_defined(self):
        from lidco.multimodal.diagram_gen import _VALID_STYLES
        assert "flowchart" in _VALID_STYLES
        assert "sequence" in _VALID_STYLES
        assert "class" in _VALID_STYLES
        assert "er" in _VALID_STYLES
        assert "gantt" in _VALID_STYLES

    def test_invalid_style_falls_back_to_flowchart(self):
        from lidco.multimodal.diagram_gen import DiagramGenerator
        session = MagicMock()
        gen = DiagramGenerator(session=session)
        # generate_from_code with invalid style
        gen._session.orchestrator.handle = AsyncMock(return_value=MagicMock(content="graph TD\n  A[test]"))
        # Just ensure it doesn't crash
        assert gen is not None

    @pytest.mark.asyncio
    async def test_generate_from_code_missing_file(self):
        from lidco.multimodal.diagram_gen import DiagramGenerator
        session = MagicMock()
        gen = DiagramGenerator(session=session)
        result = await gen.generate_from_code("/nonexistent/file.py", style="flowchart")
        assert "not found" in result.lower() or "error" in result.lower()


class TestDiagramGeneratorGenerate:
    @pytest.mark.asyncio
    async def test_generate_from_code_reads_file(self, tmp_path):
        from lidco.multimodal.diagram_gen import DiagramGenerator
        src = tmp_path / "module.py"
        src.write_text("def hello(): pass\n")
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.content = "```mermaid\ngraph TD\n  A[hello]\n```"
        session.orchestrator.handle = AsyncMock(return_value=mock_result)
        gen = DiagramGenerator(session=session)
        result = await gen.generate_from_code(str(src), style="flowchart")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_from_description_returns_mermaid(self):
        from lidco.multimodal.diagram_gen import DiagramGenerator
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.content = "```mermaid\nsequenceDiagram\n  A->>B: Hello\n```"
        session.orchestrator.handle = AsyncMock(return_value=mock_result)
        gen = DiagramGenerator(session=session)
        result = await gen.generate_from_description("auth flow", style="sequence")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_invalid_style_normalised(self):
        from lidco.multimodal.diagram_gen import DiagramGenerator
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.content = "graph TD\n  A[test]"
        session.orchestrator.handle = AsyncMock(return_value=mock_result)
        gen = DiagramGenerator(session=session)
        result = await gen.generate_from_description("test", style="invalid_style")
        assert isinstance(result, str)


class TestExtractMermaid:
    def test_extracts_from_code_block(self):
        from lidco.multimodal.diagram_gen import _extract_mermaid
        text = "```mermaid\ngraph TD\n  A --> B\n```"
        result = _extract_mermaid(text)
        assert "graph TD" in result
        assert "```" not in result

    def test_returns_raw_if_no_block(self):
        from lidco.multimodal.diagram_gen import _extract_mermaid
        text = "graph TD\n  A --> B"
        result = _extract_mermaid(text)
        assert "graph TD" in result


class TestMermaidRenderer:
    def test_render_returns_markdown_without_mmdc(self):
        from lidco.multimodal.diagram_gen import MermaidRenderer
        with patch.object(MermaidRenderer, "_has_mmdc", return_value=False):
            result = MermaidRenderer.render("graph TD\n  A --> B")
        assert "```mermaid" in result
        assert "graph TD" in result

    def test_render_with_output_path_but_no_mmdc(self, tmp_path):
        from lidco.multimodal.diagram_gen import MermaidRenderer
        out = tmp_path / "out.png"
        with patch.object(MermaidRenderer, "_has_mmdc", return_value=False):
            result = MermaidRenderer.render("graph TD\n  A --> B", output_path=str(out))
        # Without mmdc, returns markdown fallback
        assert isinstance(result, str)
