"""Tree-sitter multi-language AST support — Q163."""
from __future__ import annotations

from lidco.ast.treesitter_parser import TreeSitterParser, ParseResult
from lidco.ast.universal_extractor import UniversalExtractor, ExtractedSymbol
from lidco.ast.repo_map import MultiLanguageRepoMap, RepoMapEntry
from lidco.ast.ast_linter import ASTLinter, LintResult

__all__ = [
    "TreeSitterParser",
    "ParseResult",
    "UniversalExtractor",
    "ExtractedSymbol",
    "MultiLanguageRepoMap",
    "RepoMapEntry",
    "ASTLinter",
    "LintResult",
]
