"""Diagram generation — produces Mermaid markdown from code or descriptions."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

_VALID_STYLES = {"flowchart", "sequence", "class", "er", "gantt"}

_STYLE_PROMPTS: dict[str, str] = {
    "flowchart": "a Mermaid flowchart (graph TD)",
    "sequence": "a Mermaid sequence diagram (sequenceDiagram)",
    "class": "a Mermaid class diagram (classDiagram)",
    "er": "a Mermaid entity-relationship diagram (erDiagram)",
    "gantt": "a Mermaid Gantt chart (gantt)",
}


def _extract_mermaid(text: str) -> str:
    """Extract Mermaid code from a markdown code block, or return text as-is."""
    lines = text.splitlines()
    in_block = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not in_block and stripped.startswith("```"):
            lang = stripped[3:].strip().lower()
            if lang in ("mermaid", ""):
                in_block = True
            continue
        if in_block:
            if stripped.startswith("```"):
                break
            collected.append(line)
    return "\n".join(collected).strip() if collected else text.strip()


class DiagramGenerator:
    """Generate Mermaid diagrams from code files or text descriptions."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def _llm_generate(self, prompt: str) -> str:
        """Call the session's LLM and return the raw text response."""
        try:
            result = await self._session.orchestrator.handle(prompt, agent_name="architect")
            content = result.content if hasattr(result, "content") else str(result)
            return content
        except Exception as exc:
            return f"LLM error: {exc}"

    async def generate_from_code(
        self, file_path: str | Path, style: str = "flowchart"
    ) -> str:
        """Read *file_path* and generate a Mermaid diagram from its source."""
        path = Path(file_path)
        if not path.exists():
            return f"Error: file not found: {path}"
        style = style if style in _VALID_STYLES else "flowchart"
        source = path.read_text(encoding="utf-8", errors="replace")
        # Truncate large files
        if len(source) > 8000:
            source = source[:8000] + "\n# ... (truncated)"

        style_desc = _STYLE_PROMPTS[style]
        prompt = (
            f"Generate {style_desc} for the following source code. "
            "Output ONLY the raw Mermaid diagram code inside a ```mermaid block. "
            "Do not add explanation.\n\n"
            f"```python\n{source}\n```"
        )
        raw = await self._llm_generate(prompt)
        return _extract_mermaid(raw)

    async def generate_from_description(
        self, description: str, style: str = "flowchart"
    ) -> str:
        """Generate a Mermaid diagram from a natural-language *description*."""
        style = style if style in _VALID_STYLES else "flowchart"
        style_desc = _STYLE_PROMPTS[style]
        prompt = (
            f"Generate {style_desc} based on this description. "
            "Output ONLY the raw Mermaid diagram code inside a ```mermaid block. "
            "Do not add explanation.\n\n"
            f"{description}"
        )
        raw = await self._llm_generate(prompt)
        return _extract_mermaid(raw)


class MermaidRenderer:
    """Render Mermaid diagrams to PNG (if mmdc is available) or return markdown."""

    @staticmethod
    def _has_mmdc() -> bool:
        return shutil.which("mmdc") is not None

    @classmethod
    def render(cls, mermaid_code: str, output_path: str | Path | None = None) -> str:
        """Render *mermaid_code*.

        If ``mmdc`` is available and *output_path* is provided, renders to PNG
        and returns the path.  Otherwise wraps in a markdown code block.
        """
        if cls._has_mmdc() and output_path is not None:
            return cls._render_with_mmdc(mermaid_code, Path(output_path))
        return f"```mermaid\n{mermaid_code}\n```"

    @classmethod
    def _render_with_mmdc(cls, mermaid_code: str, output_path: Path) -> str:
        """Write a temp .mmd file, call mmdc, return output path string."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mmd", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(mermaid_code)
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["mmdc", "-i", tmp_path, "-o", str(output_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return str(output_path)
            return (
                f"mmdc rendering failed: {result.stderr.strip()}\n\n"
                f"```mermaid\n{mermaid_code}\n```"
            )
        except subprocess.TimeoutExpired:
            return f"mmdc timed out.\n\n```mermaid\n{mermaid_code}\n```"
        finally:
            Path(tmp_path).unlink(missing_ok=True)
