"""Code indexer for RAG system using tree-sitter with line-based fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "env", ".env", ".eggs", "egg-info",
})

SUPPORTED_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".cpp", ".c", ".rb",
})

EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".rb": "ruby",
}

# Tree-sitter language to node types that represent meaningful blocks
TREESITTER_BLOCK_TYPES: dict[str, tuple[str, ...]] = {
    "python": ("function_definition", "class_definition"),
    "javascript": ("function_declaration", "class_declaration", "arrow_function", "method_definition"),
    "typescript": ("function_declaration", "class_declaration", "arrow_function", "method_definition"),
    "java": ("method_declaration", "class_declaration"),
    "go": ("function_declaration", "method_declaration", "type_declaration"),
    "rust": ("function_item", "impl_item", "struct_item"),
    "cpp": ("function_definition", "class_specifier"),
    "c": ("function_definition",),
    "ruby": ("method", "class", "module"),
}


@dataclass(frozen=True)
class CodeChunk:
    """A chunk of code with metadata."""

    file_path: str
    content: str
    language: str
    chunk_type: str  # "function", "class", "module", "block"
    start_line: int
    end_line: int
    name: str  # function/class name if available


class CodeIndexer:
    """Indexes source code files into chunks for vector storage.

    Uses tree-sitter for semantic chunking when available,
    with a line-based fallback for all languages.
    """

    def __init__(
        self,
        project_dir: Path,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self._project_dir = project_dir
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._treesitter_available = self._check_treesitter()

    @staticmethod
    def _check_treesitter() -> bool:
        """Check whether tree-sitter is importable."""
        try:
            import tree_sitter  # noqa: F401
            return True
        except ImportError:
            logger.debug("tree-sitter not available, using line-based chunking only")
            return False

    def get_supported_extensions(self) -> set[str]:
        """Return set of supported file extensions."""
        return set(SUPPORTED_EXTENSIONS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def index_file(self, file_path: Path) -> list[CodeChunk]:
        """Parse a file and return chunks.

        Tries tree-sitter for semantic chunking first, then falls back
        to simple line-based chunking.
        """
        if not file_path.is_file():
            return []

        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return []

        language = EXTENSION_TO_LANGUAGE.get(ext, "unknown")

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("Cannot read %s: %s", file_path, e)
            return []

        if not source.strip():
            return []

        # Try tree-sitter first
        if self._treesitter_available:
            chunks = self._treesitter_chunks(file_path, source, language)
            if chunks:
                return chunks

        # Fallback: line-based chunking
        return self._line_based_chunks(file_path, source, language)

    def index_directory(
        self,
        directory: Path,
        extensions: set[str] | None = None,
    ) -> list[CodeChunk]:
        """Index all matching files in a directory recursively.

        Skips common non-source directories like .git, node_modules, etc.
        """
        target_extensions = extensions or self.get_supported_extensions()
        all_chunks: list[CodeChunk] = []

        if not directory.is_dir():
            logger.warning("Directory does not exist: %s", directory)
            return all_chunks

        for item in sorted(directory.rglob("*")):
            # Skip files inside ignored directories
            if any(part in SKIP_DIRS for part in item.parts):
                continue

            if item.is_file() and item.suffix.lower() in target_extensions:
                chunks = self.index_file(item)
                all_chunks.extend(chunks)

        logger.info(
            "Indexed %d chunks from %s", len(all_chunks), directory,
        )
        return all_chunks

    # ------------------------------------------------------------------
    # Tree-sitter chunking
    # ------------------------------------------------------------------

    def _treesitter_chunks(
        self, file_path: Path, source: str, language: str,
    ) -> list[CodeChunk]:
        """Extract semantic chunks using tree-sitter."""
        try:
            from tree_sitter import Language, Parser  # type: ignore[import-untyped]
            import tree_sitter_languages  # type: ignore[import-untyped]
        except ImportError:
            return []

        ts_lang_name = language
        try:
            lang = tree_sitter_languages.get_language(ts_lang_name)
            parser = tree_sitter_languages.get_parser(ts_lang_name)
        except Exception:
            return []

        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)

        block_types = TREESITTER_BLOCK_TYPES.get(language, ())
        if not block_types:
            return []

        chunks: list[CodeChunk] = []
        self._walk_tree(
            tree.root_node, source_bytes, file_path, language, block_types, chunks,
        )

        # If tree-sitter found no blocks, return empty to trigger fallback
        if not chunks:
            return []

        # Also add a module-level chunk for code outside functions/classes
        # that might contain imports, constants, etc.
        module_chunk = self._extract_module_level(
            tree.root_node, source_bytes, file_path, language, block_types,
        )
        if module_chunk:
            chunks.insert(0, module_chunk)

        return chunks

    def _walk_tree(
        self,
        node: object,
        source_bytes: bytes,
        file_path: Path,
        language: str,
        block_types: tuple[str, ...],
        out: list[CodeChunk],
    ) -> None:
        """Recursively walk the AST and extract chunks for block nodes."""
        node_type: str = getattr(node, "type", "")
        children = getattr(node, "children", [])

        if node_type in block_types:
            start_line = getattr(node, "start_point", (0,))[0] + 1
            end_line = getattr(node, "end_point", (0,))[0] + 1
            start_byte = getattr(node, "start_byte", 0)
            end_byte = getattr(node, "end_byte", len(source_bytes))
            content = source_bytes[start_byte:end_byte].decode("utf-8", errors="replace")

            chunk_type = "class" if "class" in node_type else "function"
            name = self._extract_node_name(node)

            # If the chunk is too large, split it further
            if len(content) > self._chunk_size * 2:
                sub_chunks = self._split_large_content(
                    file_path, content, language, chunk_type, name, start_line,
                )
                out.extend(sub_chunks)
            else:
                out.append(CodeChunk(
                    file_path=str(file_path),
                    content=content,
                    language=language,
                    chunk_type=chunk_type,
                    start_line=start_line,
                    end_line=end_line,
                    name=name,
                ))
            return  # Don't recurse into extracted blocks

        for child in children:
            self._walk_tree(child, source_bytes, file_path, language, block_types, out)

    @staticmethod
    def _extract_node_name(node: object) -> str:
        """Try to extract a name (identifier) from a tree-sitter node."""
        children = getattr(node, "children", [])
        for child in children:
            child_type = getattr(child, "type", "")
            if child_type in ("identifier", "name", "property_identifier"):
                return getattr(child, "text", b"").decode("utf-8", errors="replace")
        return ""

    def _extract_module_level(
        self,
        root_node: object,
        source_bytes: bytes,
        file_path: Path,
        language: str,
        block_types: tuple[str, ...],
    ) -> CodeChunk | None:
        """Extract top-level code that is not inside functions or classes."""
        children = getattr(root_node, "children", [])
        module_lines: list[str] = []
        first_line: int | None = None

        for child in children:
            child_type = getattr(child, "type", "")
            if child_type not in block_types:
                start_byte = getattr(child, "start_byte", 0)
                end_byte = getattr(child, "end_byte", 0)
                text = source_bytes[start_byte:end_byte].decode("utf-8", errors="replace").strip()
                if text:
                    if first_line is None:
                        first_line = getattr(child, "start_point", (0,))[0] + 1
                    module_lines.append(text)

        content = "\n".join(module_lines)
        if not content.strip():
            return None

        lines = content.splitlines()
        return CodeChunk(
            file_path=str(file_path),
            content=content,
            language=language,
            chunk_type="module",
            start_line=first_line or 1,
            end_line=(first_line or 1) + len(lines) - 1,
            name=file_path.stem,
        )

    # ------------------------------------------------------------------
    # Line-based fallback chunking
    # ------------------------------------------------------------------

    def _line_based_chunks(
        self, file_path: Path, source: str, language: str,
    ) -> list[CodeChunk]:
        """Split source code into overlapping line-based chunks."""
        lines = source.splitlines(keepends=True)
        if not lines:
            return []

        chunks: list[CodeChunk] = []
        chunk_start = 0

        while chunk_start < len(lines):
            # Collect lines until we hit chunk_size characters
            chunk_lines: list[str] = []
            char_count = 0
            idx = chunk_start

            while idx < len(lines) and char_count < self._chunk_size:
                chunk_lines.append(lines[idx])
                char_count += len(lines[idx])
                idx += 1

            content = "".join(chunk_lines)
            start_line = chunk_start + 1
            end_line = chunk_start + len(chunk_lines)

            name = self._guess_chunk_name(chunk_lines, file_path)

            chunks.append(CodeChunk(
                file_path=str(file_path),
                content=content,
                language=language,
                chunk_type="block",
                start_line=start_line,
                end_line=end_line,
                name=name,
            ))

            # Advance by (chunk_size - overlap) worth of lines
            overlap_chars = 0
            overlap_lines = 0
            for rev_idx in range(len(chunk_lines) - 1, -1, -1):
                overlap_chars += len(chunk_lines[rev_idx])
                overlap_lines += 1
                if overlap_chars >= self._chunk_overlap:
                    break

            advance = max(1, len(chunk_lines) - overlap_lines)
            chunk_start += advance

        return chunks

    @staticmethod
    def _guess_chunk_name(lines: list[str], file_path: Path) -> str:
        """Try to guess a meaningful name from the first few lines."""
        for line in lines[:10]:
            stripped = line.strip()
            # Python
            if stripped.startswith("def ") or stripped.startswith("async def "):
                name_part = stripped.split("(")[0]
                return name_part.replace("def ", "").replace("async ", "").strip()
            if stripped.startswith("class "):
                name_part = stripped.split("(")[0].split(":")[0]
                return name_part.replace("class ", "").strip()
            # JS/TS
            if stripped.startswith("function "):
                name_part = stripped.split("(")[0]
                return name_part.replace("function ", "").strip()
            if stripped.startswith("export class ") or stripped.startswith("export default class "):
                parts = stripped.split()
                for i, p in enumerate(parts):
                    if p == "class" and i + 1 < len(parts):
                        return parts[i + 1].rstrip("{").rstrip(":")
        return file_path.stem

    def _split_large_content(
        self,
        file_path: Path,
        content: str,
        language: str,
        chunk_type: str,
        name: str,
        base_start_line: int,
    ) -> list[CodeChunk]:
        """Split an oversized block into smaller overlapping chunks."""
        lines = content.splitlines(keepends=True)
        chunks: list[CodeChunk] = []
        chunk_start = 0
        part_num = 0

        while chunk_start < len(lines):
            chunk_lines: list[str] = []
            char_count = 0
            idx = chunk_start

            while idx < len(lines) and char_count < self._chunk_size:
                chunk_lines.append(lines[idx])
                char_count += len(lines[idx])
                idx += 1

            part_num += 1
            chunk_content = "".join(chunk_lines)
            start = base_start_line + chunk_start
            end = base_start_line + chunk_start + len(chunk_lines) - 1

            chunks.append(CodeChunk(
                file_path=str(file_path),
                content=chunk_content,
                language=language,
                chunk_type=chunk_type,
                start_line=start,
                end_line=end,
                name=f"{name}__part{part_num}" if part_num > 1 else name,
            ))

            overlap_chars = 0
            overlap_lines = 0
            for rev_idx in range(len(chunk_lines) - 1, -1, -1):
                overlap_chars += len(chunk_lines[rev_idx])
                overlap_lines += 1
                if overlap_chars >= self._chunk_overlap:
                    break

            advance = max(1, len(chunk_lines) - overlap_lines)
            chunk_start += advance

        return chunks
