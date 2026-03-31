"""Universal symbol extractor — Task 928."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lidco.ast.treesitter_parser import TreeSitterParser, HAS_TREESITTER


@dataclass
class ExtractedSymbol:
    """A symbol extracted from source code."""

    name: str
    kind: str  # function, class, method, variable, import
    language: str
    line: int
    end_line: int | None = None
    signature: str = ""


class UniversalExtractor:
    """Extract symbols from source in any supported language.

    Uses tree-sitter queries when available, regex otherwise.
    """

    def __init__(self, parser: TreeSitterParser) -> None:
        self._parser = parser

    def extract(self, source: str, language: str) -> list[ExtractedSymbol]:
        """Extract symbols from *source* in *language*."""
        if HAS_TREESITTER and self._parser.is_available():
            try:
                return self._extract_treesitter(source, language)
            except Exception:
                pass  # fall through to regex

        dispatch = {
            "python": self._extract_python,
            "javascript": self._extract_javascript,
            "typescript": self._extract_javascript,
        }
        handler = dispatch.get(language, self._extract_generic)
        return handler(source, language)

    # ------------------------------------------------------------------
    # Tree-sitter extraction
    # ------------------------------------------------------------------

    def _extract_treesitter(self, source: str, language: str) -> list[ExtractedSymbol]:
        from tree_sitter_language_pack import get_parser  # type: ignore[import-untyped]

        parser = get_parser(language)
        tree = parser.parse(source.encode("utf-8"))
        symbols: list[ExtractedSymbol] = []
        self._walk_ts_node(tree.root_node, language, symbols)
        return symbols

    def _walk_ts_node(
        self, node: Any, language: str, symbols: list[ExtractedSymbol]
    ) -> None:
        kind = self._ts_node_kind(node.type, language)
        if kind:
            name = self._ts_node_name(node, language)
            if name:
                start = node.start_point[0] + 1
                end = node.end_point[0] + 1
                sig = self._ts_node_signature(node, language)
                symbols.append(
                    ExtractedSymbol(
                        name=name,
                        kind=kind,
                        language=language,
                        line=start,
                        end_line=end,
                        signature=sig,
                    )
                )
        for child in node.children:
            self._walk_ts_node(child, language, symbols)

    @staticmethod
    def _ts_node_kind(node_type: str, language: str) -> str | None:
        mapping: dict[str, str] = {
            "function_definition": "function",
            "function_declaration": "function",
            "method_definition": "method",
            "class_definition": "class",
            "class_declaration": "class",
            "import_statement": "import",
            "import_from_statement": "import",
            "lexical_declaration": "variable",
            "variable_declaration": "variable",
        }
        return mapping.get(node_type)

    @staticmethod
    def _ts_node_name(node: Any, language: str) -> str | None:
        for child in node.children:
            if child.type in ("identifier", "property_identifier", "type_identifier"):
                return child.text.decode("utf-8") if isinstance(child.text, bytes) else child.text
        # For import statements, return the full text trimmed
        if "import" in node.type:
            text = node.text.decode("utf-8") if isinstance(node.text, bytes) else node.text
            return text.strip().split("\n")[0][:120]
        return None

    @staticmethod
    def _ts_node_signature(node: Any, language: str) -> str:
        text = node.text.decode("utf-8") if isinstance(node.text, bytes) else node.text
        first_line = text.split("\n")[0]
        return first_line[:200]

    # ------------------------------------------------------------------
    # Regex fallback: Python
    # ------------------------------------------------------------------

    def _extract_python(self, source: str, language: str = "python") -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        lines = source.splitlines()

        _func_re = re.compile(r"^(\s*)(async\s+)?def\s+(\w+)\s*\(")
        _class_re = re.compile(r"^(\s*)class\s+(\w+)")
        _import_re = re.compile(r"^(import\s+.+|from\s+\S+\s+import\s+.+)")

        for i, line in enumerate(lines, 1):
            m = _func_re.match(line)
            if m:
                indent = m.group(1)
                name = m.group(3)
                kind = "method" if len(indent) > 0 else "function"
                symbols.append(
                    ExtractedSymbol(
                        name=name,
                        kind=kind,
                        language="python",
                        line=i,
                        end_line=None,
                        signature=line.rstrip(),
                    )
                )
                continue
            m = _class_re.match(line)
            if m:
                symbols.append(
                    ExtractedSymbol(
                        name=m.group(2),
                        kind="class",
                        language="python",
                        line=i,
                        end_line=None,
                        signature=line.rstrip(),
                    )
                )
                continue
            m = _import_re.match(line)
            if m:
                symbols.append(
                    ExtractedSymbol(
                        name=m.group(1).strip(),
                        kind="import",
                        language="python",
                        line=i,
                        end_line=None,
                        signature=m.group(1).strip(),
                    )
                )
        return symbols

    # ------------------------------------------------------------------
    # Regex fallback: JavaScript / TypeScript
    # ------------------------------------------------------------------

    def _extract_javascript(self, source: str, language: str = "javascript") -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        lines = source.splitlines()

        _func_re = re.compile(
            r"^(?:export\s+)?(?:async\s+)?function\s+(\w+)"
        )
        _class_re = re.compile(r"^(?:export\s+)?class\s+(\w+)")
        _const_re = re.compile(
            r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*="
        )
        _import_re = re.compile(r"^import\s+.+")
        _method_re = re.compile(r"^\s+(?:async\s+)?(\w+)\s*\(")

        for i, line in enumerate(lines, 1):
            m = _func_re.match(line)
            if m:
                symbols.append(
                    ExtractedSymbol(
                        name=m.group(1), kind="function", language=language,
                        line=i, end_line=None, signature=line.rstrip(),
                    )
                )
                continue
            m = _class_re.match(line)
            if m:
                symbols.append(
                    ExtractedSymbol(
                        name=m.group(1), kind="class", language=language,
                        line=i, end_line=None, signature=line.rstrip(),
                    )
                )
                continue
            m = _const_re.match(line)
            if m:
                symbols.append(
                    ExtractedSymbol(
                        name=m.group(1), kind="variable", language=language,
                        line=i, end_line=None, signature=line.rstrip(),
                    )
                )
                continue
            m = _import_re.match(line)
            if m:
                symbols.append(
                    ExtractedSymbol(
                        name=line.strip(), kind="import", language=language,
                        line=i, end_line=None, signature=line.strip(),
                    )
                )
                continue
            m = _method_re.match(line)
            if m:
                symbols.append(
                    ExtractedSymbol(
                        name=m.group(1), kind="method", language=language,
                        line=i, end_line=None, signature=line.rstrip(),
                    )
                )

        return symbols

    # ------------------------------------------------------------------
    # Regex fallback: generic
    # ------------------------------------------------------------------

    def _extract_generic(self, source: str, language: str = "unknown") -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        lines = source.splitlines()

        _func_re = re.compile(
            r"(?:func|fn|def|function|sub|proc)\s+(\w+)"
        )
        _class_re = re.compile(
            r"(?:class|struct|interface|enum|type)\s+(\w+)"
        )

        for i, line in enumerate(lines, 1):
            m = _func_re.search(line)
            if m:
                symbols.append(
                    ExtractedSymbol(
                        name=m.group(1), kind="function", language=language,
                        line=i, end_line=None, signature=line.rstrip(),
                    )
                )
                continue
            m = _class_re.search(line)
            if m:
                symbols.append(
                    ExtractedSymbol(
                        name=m.group(1), kind="class", language=language,
                        line=i, end_line=None, signature=line.rstrip(),
                    )
                )

        return symbols
