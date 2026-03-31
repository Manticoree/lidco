"""Q132: File classifier by extension and path patterns."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# Extension → language
_EXT_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".rst": "markdown",
    ".txt": "text",
    ".html": "html",
    ".css": "css",
    ".sh": "shell",
    ".bash": "shell",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".cs": "csharp",
    ".php": "php",
    ".sql": "sql",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".xml": "xml",
    ".svg": "xml",
}

_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".pdf",
    ".zip", ".tar", ".gz", ".7z", ".whl", ".pyc", ".so", ".dll",
    ".exe", ".bin", ".db", ".sqlite", ".ttf", ".woff", ".woff2",
}

_TEST_PATTERNS = ("test_", "_test.", "tests/", "/test/", "spec.", "_spec.")
_CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".xml"}
_DOC_EXTS = {".md", ".rst", ".txt"}
_GENERATED_PATTERNS = (".min.js", "dist/", "build/", "__pycache__/", ".pyc")


@dataclass
class FileClass:
    path: str
    category: str  # source/test/config/doc/asset/generated/unknown
    language: str
    is_binary: bool = False


class FileClassifier:
    """Classify files by category and language based on path/extension."""

    def classify(self, path: str, content: str = "") -> FileClass:
        ext = os.path.splitext(path)[1].lower()
        norm = path.replace("\\", "/")

        is_binary = ext in _BINARY_EXTS
        language = _EXT_LANGUAGE.get(ext, "other") if not is_binary else "binary"

        category = self._infer_category(norm, ext)
        return FileClass(path=path, category=category, language=language, is_binary=is_binary)

    def classify_many(self, paths: list[str]) -> list[FileClass]:
        return [self.classify(p) for p in paths]

    def filter_by_category(self, files: list[FileClass], category: str) -> list[FileClass]:
        return [f for f in files if f.category == category]

    def language_stats(self, files: list[FileClass]) -> dict[str, int]:
        stats: dict[str, int] = {}
        for f in files:
            stats[f.language] = stats.get(f.language, 0) + 1
        return stats

    # --- internals -----------------------------------------------------------

    def _infer_category(self, norm: str, ext: str) -> str:
        # Generated check first
        for pat in _GENERATED_PATTERNS:
            if pat in norm:
                return "generated"

        # Test
        for pat in _TEST_PATTERNS:
            if pat in norm:
                return "test"

        # Binary → asset
        if ext in _BINARY_EXTS:
            return "asset"

        # Config
        if ext in _CONFIG_EXTS:
            # But yaml/json in docs/ dir → doc
            if any(d in norm for d in ("docs/", "doc/")):
                return "doc"
            return "config"

        # Doc
        if ext in _DOC_EXTS:
            return "doc"

        # Source
        if ext in _EXT_LANGUAGE:
            return "source"

        return "unknown"
