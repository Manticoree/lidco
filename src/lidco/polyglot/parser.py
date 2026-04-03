"""Universal regex-based symbol parser for multiple languages."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Symbol:
    """A code symbol extracted from source."""

    name: str
    kind: str
    language: str
    file: str = ""
    line: int = 0


_PYTHON_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*def\s+(\w+)", "function"),
    (r"^\s*class\s+(\w+)", "class"),
    (r"^\s*async\s+def\s+(\w+)", "function"),
]

_JS_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*function\s+(\w+)", "function"),
    (r"^\s*class\s+(\w+)", "class"),
    (r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:function|\()", "function"),
    (r"^\s*(?:const|let|var)\s+(\w+)\s*=", "variable"),
    (r"^\s*export\s+(?:default\s+)?function\s+(\w+)", "function"),
    (r"^\s*export\s+(?:default\s+)?class\s+(\w+)", "class"),
]

_GO_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*func\s+(\w+)", "function"),
    (r"^\s*func\s+\(\w+\s+\*?\w+\)\s+(\w+)", "method"),
    (r"^\s*type\s+(\w+)\s+struct", "struct"),
    (r"^\s*type\s+(\w+)\s+interface", "interface"),
]

_RUST_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*(?:pub\s+)?fn\s+(\w+)", "function"),
    (r"^\s*(?:pub\s+)?struct\s+(\w+)", "struct"),
    (r"^\s*(?:pub\s+)?enum\s+(\w+)", "enum"),
    (r"^\s*(?:pub\s+)?trait\s+(\w+)", "trait"),
    (r"^\s*impl\s+(\w+)", "impl"),
]

_JAVA_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*(?:public|private|protected)?\s*class\s+(\w+)", "class"),
    (r"^\s*(?:public|private|protected)?\s*interface\s+(\w+)", "interface"),
    (r"^\s*(?:public|private|protected)?\s*(?:static\s+)?\w+\s+(\w+)\s*\(", "method"),
]

_C_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*(?:static\s+)?(?:inline\s+)?\w+\s+(\w+)\s*\(", "function"),
    (r"^\s*typedef\s+struct\s+\w*\s*\{", "struct"),
    (r"^\s*struct\s+(\w+)", "struct"),
    (r"^\s*#define\s+(\w+)", "macro"),
]

_LANGUAGE_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "python": _PYTHON_PATTERNS,
    "javascript": _JS_PATTERNS,
    "typescript": _JS_PATTERNS,
    "go": _GO_PATTERNS,
    "rust": _RUST_PATTERNS,
    "java": _JAVA_PATTERNS,
    "c": _C_PATTERNS,
}

_IMPORT_PATTERNS: dict[str, list[str]] = {
    "python": [r"^\s*import\s+([\w.]+)", r"^\s*from\s+([\w.]+)\s+import"],
    "javascript": [r"""^\s*import\s+.*?from\s+['"]([\w./@-]+)['"]""", r"""^\s*(?:const|let|var)\s+\w+\s*=\s*require\(['"]([\w./@-]+)['"]\)"""],
    "typescript": [r"""^\s*import\s+.*?from\s+['"]([\w./@-]+)['"]"""],
    "go": [r"""^\s*"([\w./]+)"$""", r"""^\s*import\s+"([\w./]+)"$"""],
    "rust": [r"^\s*use\s+([\w:]+)"],
    "java": [r"^\s*import\s+([\w.]+);"],
    "c": [r"""^\s*#include\s+[<"]([\w./]+)[>"]"""],
}


class UniversalParser:
    """Regex-based symbol extractor for multiple languages."""

    def parse(self, content: str, language: str) -> list[Symbol]:
        """Parse content and extract symbols for the given language."""
        lang = language.lower()
        if lang == "python":
            return self.parse_python(content)
        if lang in ("javascript", "typescript"):
            return self.parse_javascript(content)
        patterns = _LANGUAGE_PATTERNS.get(lang, [])
        symbols: list[Symbol] = []
        seen: set[str] = set()
        for lineno, raw_line in enumerate(content.splitlines(), 1):
            for pat, kind in patterns:
                m = re.match(pat, raw_line)
                if m:
                    name = m.group(1)
                    key = f"{name}:{kind}"
                    if key not in seen:
                        seen.add(key)
                        symbols.append(Symbol(name=name, kind=kind, language=lang, line=lineno))
        return symbols

    def parse_python(self, content: str) -> list[Symbol]:
        """Extract Python symbols (def/class)."""
        symbols: list[Symbol] = []
        seen: set[str] = set()
        for lineno, raw_line in enumerate(content.splitlines(), 1):
            for pat, kind in _PYTHON_PATTERNS:
                m = re.match(pat, raw_line)
                if m:
                    name = m.group(1)
                    key = f"{name}:{kind}"
                    if key not in seen:
                        seen.add(key)
                        symbols.append(Symbol(name=name, kind=kind, language="python", line=lineno))
        return symbols

    def parse_javascript(self, content: str) -> list[Symbol]:
        """Extract JavaScript/TypeScript symbols."""
        symbols: list[Symbol] = []
        seen: set[str] = set()
        for lineno, raw_line in enumerate(content.splitlines(), 1):
            for pat, kind in _JS_PATTERNS:
                m = re.match(pat, raw_line)
                if m:
                    name = m.group(1)
                    key = f"{name}:{kind}"
                    if key not in seen:
                        seen.add(key)
                        symbols.append(Symbol(name=name, kind=kind, language="javascript", line=lineno))
        return symbols

    def extract_imports(self, content: str, language: str) -> list[str]:
        """Extract import statements for the given language."""
        lang = language.lower()
        patterns = _IMPORT_PATTERNS.get(lang, [])
        imports: list[str] = []
        seen: set[str] = set()
        for raw_line in content.splitlines():
            for pat in patterns:
                m = re.match(pat, raw_line)
                if m:
                    imp = m.group(1)
                    if imp not in seen:
                        seen.add(imp)
                        imports.append(imp)
        return imports
