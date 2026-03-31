"""Tree-sitter language pack integration — Task 927."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:
    import tree_sitter
    from tree_sitter_language_pack import get_language, get_parser
    HAS_TREESITTER = True
except ImportError:
    HAS_TREESITTER = False
    tree_sitter = None  # type: ignore[assignment]
    get_language = None  # type: ignore[assignment]
    get_parser = None  # type: ignore[assignment]


_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".cs": "c_sharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".php": "php",
    ".lua": "lua",
    ".r": "r",
    ".R": "r",
    ".hs": "haskell",
    ".ex": "elixir",
    ".exs": "elixir",
    ".erl": "erlang",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sql": "sql",
    ".dart": "dart",
    ".pl": "perl",
    ".pm": "perl",
}


@dataclass
class ParseResult:
    """Result of parsing source code."""

    language: str
    tree_available: bool
    node_count: int
    errors: list[str] = field(default_factory=list)
    source_path: str = ""


class TreeSitterParser:
    """Multi-language parser with optional tree-sitter backend.

    When tree-sitter and tree-sitter-language-pack are installed, uses
    them for accurate AST parsing.  Otherwise falls back to regex-based
    heuristics so the tool is always functional.
    """

    def __init__(self) -> None:
        self._parser_cache: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if tree-sitter backend is available."""
        return HAS_TREESITTER

    def supported_languages(self) -> list[str]:
        """Return supported language names (empty when tree-sitter missing)."""
        if not HAS_TREESITTER:
            return []
        return sorted(set(_EXTENSION_MAP.values()))

    def detect_language(self, file_path: str) -> str | None:
        """Map a file extension to a language name."""
        import os

        _, ext = os.path.splitext(file_path)
        return _EXTENSION_MAP.get(ext)

    def parse(self, source: str, language: str) -> ParseResult:
        """Parse *source* in *language*, returning a :class:`ParseResult`."""
        if HAS_TREESITTER:
            return self._parse_treesitter(source, language)
        return self._parse_regex(source, language)

    # ------------------------------------------------------------------
    # Tree-sitter backend
    # ------------------------------------------------------------------

    def _parse_treesitter(self, source: str, language: str) -> ParseResult:
        try:
            parser = self._get_ts_parser(language)
            tree = parser.parse(source.encode("utf-8"))
            errors: list[str] = []
            node_count = self._count_nodes(tree.root_node)
            self._collect_errors(tree.root_node, errors)
            return ParseResult(
                language=language,
                tree_available=True,
                node_count=node_count,
                errors=errors,
            )
        except Exception as exc:
            return ParseResult(
                language=language,
                tree_available=False,
                node_count=0,
                errors=[f"tree-sitter error: {exc}"],
            )

    def _get_ts_parser(self, language: str) -> Any:
        if language not in self._parser_cache:
            self._parser_cache[language] = get_parser(language)  # type: ignore[misc]
        return self._parser_cache[language]

    @staticmethod
    def _count_nodes(node: Any) -> int:
        count = 1
        for child in node.children:
            count += TreeSitterParser._count_nodes(child)
        return count

    @staticmethod
    def _collect_errors(node: Any, errors: list[str]) -> None:
        if node.type == "ERROR":
            errors.append(
                f"Syntax error at line {node.start_point[0] + 1}, "
                f"col {node.start_point[1]}"
            )
        for child in node.children:
            TreeSitterParser._collect_errors(child, errors)

    # ------------------------------------------------------------------
    # Regex fallback
    # ------------------------------------------------------------------

    def _parse_regex(self, source: str, language: str) -> ParseResult:
        lines = source.splitlines()
        errors: list[str] = []

        if language == "python":
            try:
                compile(source, "<string>", "exec")
            except SyntaxError as exc:
                errors.append(f"SyntaxError: {exc.msg} (line {exc.lineno})")

        node_count = len(lines)
        return ParseResult(
            language=language,
            tree_available=False,
            node_count=node_count,
            errors=errors,
        )
