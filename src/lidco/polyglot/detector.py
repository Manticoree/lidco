"""Language detection by extension, shebang, and content heuristics."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionResult:
    """Result of a language detection attempt."""

    language: str
    confidence: float
    method: str


_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "c",
    ".h": "c",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".cs": "csharp",
    ".lua": "lua",
    ".sh": "shell",
    ".bash": "shell",
}

_SHEBANG_MAP: dict[str, str] = {
    "python": "python",
    "python3": "python",
    "node": "javascript",
    "ruby": "ruby",
    "perl": "perl",
    "bash": "shell",
    "sh": "shell",
    "php": "php",
}

_KEYWORD_PATTERNS: dict[str, list[str]] = {
    "python": ["def ", "import ", "class ", "print(", "elif ", "self."],
    "javascript": ["function ", "const ", "let ", "var ", "=>", "require("],
    "typescript": ["interface ", "type ", ": string", ": number", "readonly "],
    "go": ["func ", "package ", "import (", "fmt.", "go func"],
    "rust": ["fn ", "let mut ", "impl ", "pub fn", "use std::"],
    "java": ["public class ", "private ", "System.out", "void ", "import java."],
    "c": ["#include", "int main(", "printf(", "sizeof(", "malloc("],
    "ruby": ["require ", "attr_accessor", "puts ", "end\n", "do |"],
}


class LanguageDetector:
    """Detect programming language from filename and/or content."""

    def detect_by_extension(self, filename: str) -> DetectionResult | None:
        """Detect language from file extension."""
        dot = filename.rfind(".")
        if dot == -1:
            return None
        ext = filename[dot:].lower()
        lang = _EXTENSION_MAP.get(ext)
        if lang is None:
            return None
        return DetectionResult(language=lang, confidence=0.9, method="extension")

    def detect_by_shebang(self, content: str) -> DetectionResult | None:
        """Detect language from shebang line."""
        if not content.startswith("#!"):
            return None
        first_line = content.split("\n", 1)[0]
        parts = first_line.split("/")
        last = parts[-1].strip()
        # Handle "env python3" style shebangs
        if last.startswith("env "):
            last = last.split()[-1]
        # Strip version suffixes like "python3.11"
        base = last.split(".")[0] if "." in last else last
        # Also strip trailing digits for e.g. "python3"
        clean = base.rstrip("0123456789") if base not in _SHEBANG_MAP else base
        token = _SHEBANG_MAP.get(base) or _SHEBANG_MAP.get(clean)
        if token is None:
            return None
        return DetectionResult(language=token, confidence=0.8, method="shebang")

    def detect_by_content(self, content: str) -> DetectionResult | None:
        """Detect language using keyword heuristics."""
        if not content.strip():
            return None
        best_lang: str | None = None
        best_score = 0
        for lang, keywords in _KEYWORD_PATTERNS.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > best_score:
                best_score = score
                best_lang = lang
        if best_lang is None or best_score == 0:
            return None
        confidence = min(0.5 + best_score * 0.1, 0.85)
        return DetectionResult(language=best_lang, confidence=confidence, method="content")

    def detect(self, filename: str, content: str = "") -> DetectionResult:
        """Combine all detection methods; highest confidence wins."""
        candidates: list[DetectionResult] = []
        ext_result = self.detect_by_extension(filename)
        if ext_result is not None:
            candidates.append(ext_result)
        if content:
            shebang_result = self.detect_by_shebang(content)
            if shebang_result is not None:
                candidates.append(shebang_result)
            content_result = self.detect_by_content(content)
            if content_result is not None:
                candidates.append(content_result)
        if not candidates:
            return DetectionResult(language="unknown", confidence=0.0, method="none")
        return max(candidates, key=lambda r: r.confidence)

    def supported_languages(self) -> list[str]:
        """Return sorted list of all supported languages."""
        langs: set[str] = set(_EXTENSION_MAP.values())
        langs.update(_KEYWORD_PATTERNS.keys())
        return sorted(langs)
