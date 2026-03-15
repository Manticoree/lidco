"""Document reader — PDF, DOCX, and plain text."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Optional PDF backends
try:
    import pypdf  # type: ignore[import]
    _HAS_PYPDF = True
except ImportError:
    _HAS_PYPDF = False

try:
    import pdfplumber  # type: ignore[import]
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

# Optional DOCX backend
try:
    import docx  # type: ignore[import]  # python-docx
    _HAS_DOCX = True
except ImportError:
    _HAS_DOCX = False

_MAX_CHARS = 50_000
_TRUNCATION_NOTICE = "\n\n[Document truncated at 50,000 characters]"


class DocumentReader:
    """Read PDF, DOCX, and plain-text documents."""

    def read_pdf(self, path: str | Path, max_pages: int = 20) -> str:
        """Extract text from a PDF file.

        Tries ``pypdf`` first, then ``pdfplumber``.
        Raises RuntimeError if neither is available.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if _HAS_PDFPLUMBER:
            return self._read_pdf_pdfplumber(file_path, max_pages)
        if _HAS_PYPDF:
            return self._read_pdf_pypdf(file_path, max_pages)
        raise RuntimeError(
            "No PDF library installed. Install one:\n"
            "  pip install pypdf\n"
            "  pip install pdfplumber"
        )

    def _read_pdf_pypdf(self, path: Path, max_pages: int) -> str:
        reader = pypdf.PdfReader(str(path))
        pages = reader.pages[:max_pages]
        parts = []
        for page in pages:
            text = page.extract_text() or ""
            parts.append(text)
        full_text = "\n".join(parts)
        return self._truncate(full_text)

    def _read_pdf_pdfplumber(self, path: Path, max_pages: int) -> str:
        with pdfplumber.open(str(path)) as pdf:
            pages = pdf.pages[:max_pages]
            parts = []
            for page in pages:
                text = page.extract_text() or ""
                parts.append(text)
        full_text = "\n".join(parts)
        return self._truncate(full_text)

    def read_docx(self, path: str | Path) -> str:
        """Extract text from a DOCX file.

        Raises RuntimeError if python-docx is not installed.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not _HAS_DOCX:
            raise RuntimeError(
                "python-docx is not installed. Install it with:\n"
                "  pip install python-docx"
            )
        document = docx.Document(str(file_path))
        paragraphs = [para.text for para in document.paragraphs]
        full_text = "\n".join(paragraphs)
        return self._truncate(full_text)

    def read_txt(self, path: str | Path) -> str:
        """Read a plain text file."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return self._truncate(text)

    def read(self, path: str | Path) -> str:
        """Dispatch to the appropriate reader based on file extension."""
        file_path = Path(path)
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return self.read_pdf(file_path)
        if ext in (".docx",):
            return self.read_docx(file_path)
        # Default: treat as plain text
        return self.read_txt(file_path)

    @staticmethod
    def _truncate(text: str) -> str:
        if len(text) > _MAX_CHARS:
            return text[:_MAX_CHARS] + _TRUNCATION_NOTICE
        return text


# ---------------------------------------------------------------------------
# BaseTool wrapper
# ---------------------------------------------------------------------------

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult  # noqa: E402


class DocumentContextTool(BaseTool):
    """Read a document (PDF/DOCX/TXT) and inject its content into context."""

    def __init__(self) -> None:
        self._reader = DocumentReader()

    @property
    def name(self) -> str:
        return "read_document"

    @property
    def description(self) -> str:
        return (
            "Read a document file (PDF, DOCX, or TXT) and return its text content. "
            "Supports up to 50,000 characters; longer documents are truncated."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Absolute or relative path to the document file.",
                required=True,
            ),
            ToolParameter(
                name="max_pages",
                type="integer",
                description="Maximum PDF pages to read (default 20).",
                required=False,
                default=20,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    async def _run(self, **kwargs: Any) -> ToolResult:
        return await self.execute(**kwargs)

    async def execute(self, path: str, max_pages: int = 20, **_: Any) -> ToolResult:
        try:
            file_path = Path(path)
            ext = file_path.suffix.lower()
            if ext == ".pdf":
                content = self._reader.read_pdf(file_path, max_pages=max_pages)
            else:
                content = self._reader.read(file_path)
            truncated = _TRUNCATION_NOTICE in content
            return ToolResult(
                output=content,
                success=True,
                metadata={"truncated": truncated, "path": str(file_path)},
            )
        except FileNotFoundError as exc:
            return ToolResult(output="", success=False, error=str(exc))
        except RuntimeError as exc:
            return ToolResult(output="", success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(output="", success=False, error=f"Unexpected error: {exc}")
