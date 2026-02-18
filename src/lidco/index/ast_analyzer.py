"""Static AST analysis for extracting symbols and imports from source files.

Supports Python (stdlib ast) and JS/TS (regex-based).  All other languages
fall back to a line-scanning pass that detects common function/class patterns.

AstAnalyzer never raises — errors are logged and empty lists are returned so
the indexer can continue processing remaining files.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from lidco.index.schema import ImportRecord, SymbolRecord
from lidco.rag.indexer import EXTENSION_TO_LANGUAGE, SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

# ── JS/TS regex patterns ──────────────────────────────────────────────────────

# Each entry: (pattern, kind, is_exported)
_JS_SYMBOL_PATTERNS: list[tuple[re.Pattern[str], str, bool]] = [
    (re.compile(r"^export\s+(?:default\s+)?(?:abstract\s+)?class\s+(\w+)"), "class", True),
    (re.compile(r"^class\s+(\w+)"), "class", False),
    (re.compile(r"^export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)"), "function", True),
    (re.compile(r"^(?:async\s+)?function\s+(\w+)"), "function", False),
    # Arrow functions assigned to const/let/var
    (re.compile(r"^export\s+(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\("), "function", True),
    (re.compile(r"^(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\("), "function", False),
    # Exported constants (non-arrow)
    (re.compile(r"^export\s+(?:const|let|var)\s+(\w+)\b"), "constant", True),
    # ALL_CAPS module-level constants
    (re.compile(r"^(?:const|let|var)\s+([A-Z][A-Z0-9_]{2,})\b"), "constant", False),
]

_JS_IMPORT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"""^import\s+.+\s+from\s+['"](.+)['"]"""), "from"),
    (re.compile(r"""^import\s+['"](.+)['"]"""), "module"),
    (re.compile(r"""(?:const|let|var)\s+.+\s*=\s*require\(\s*['"](.+)['"]\s*\)"""), "require"),
    (re.compile(r"""import\s*\(\s*['"](.+)['"]\s*\)"""), "dynamic"),
]

# ── Generic line-scan patterns (fallback for Java, Go, Rust, etc.) ────────────

_GENERIC_SYMBOL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Java / C++ / C#
    (re.compile(r"(?:public|private|protected|static).*?\bclass\s+(\w+)"), "class"),
    (re.compile(r"(?:public|private|protected|static)[^(]*\b(\w+)\s*\("), "function"),
    # Go
    (re.compile(r"^func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s+)?(\w+)\s*\("), "function"),
    (re.compile(r"^type\s+(\w+)\s+struct\b"), "class"),
    # Rust
    (re.compile(r"^(?:pub\s+)?fn\s+(\w+)\s*[\(<]"), "function"),
    (re.compile(r"^(?:pub\s+)?struct\s+(\w+)\b"), "class"),
    (re.compile(r"^(?:pub\s+)?enum\s+(\w+)\b"), "class"),
    # Ruby
    (re.compile(r"^(?:def\s+(\w+))"), "function"),
    (re.compile(r"^(?:class\s+(\w+))"), "class"),
]


# ── Public API ────────────────────────────────────────────────────────────────

class AstAnalyzer:
    """Extract symbols and imports from source files.

    Usage::

        analyzer = AstAnalyzer()
        symbols, imports = analyzer.analyze(Path("src/auth.py"), file_id=3)
        role = analyzer.detect_file_role(Path("src/auth.py"), symbols)
    """

    def analyze(
        self,
        file_path: Path,
        file_id: int = 0,
    ) -> tuple[list[SymbolRecord], list[ImportRecord]]:
        """Return (symbols, imports) extracted from *file_path*.

        Returns empty lists on any read/parse error.
        """
        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return [], []

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Cannot read %s: %s", file_path, exc)
            return [], []

        if not source.strip():
            return [], []

        language = EXTENSION_TO_LANGUAGE.get(ext, "unknown")

        if language == "python":
            return self._analyze_python(source, file_id)
        if language in ("javascript", "typescript"):
            return self._analyze_js_ts(source, file_id)
        return self._analyze_generic(source, file_id)

    # ── Role detection ────────────────────────────────────────────────────────

    @staticmethod
    def detect_file_role(file_path: Path, symbols: list[SymbolRecord]) -> str:
        """Infer the role of a file from its path and extracted symbols.

        Returns one of: entrypoint, config, test, model, router, utility.
        """
        name = file_path.name.lower()
        stem = file_path.stem.lower()
        path_str = str(file_path).replace("\\", "/").lower()

        # Tests — check first (test files can also look like entrypoints)
        if (
            stem.startswith("test_")
            or stem.endswith("_test")
            or ".spec." in name
            or ".test." in name
            or "/tests/" in path_str
            or "/test/" in path_str
            or "/__tests__/" in path_str
        ):
            return "test"

        # Config / settings files
        if (
            stem in ("config", "settings", "conf", "configuration", "constants",
                     "env", "envs", "defaults")
            or name in ("pyproject.toml", "setup.cfg", "setup.py", "webpack.config.js",
                        "vite.config.ts", "jest.config.js", "tsconfig.json", ".env")
            or stem.endswith(("_config", "_settings", "_conf"))
        ):
            return "config"

        # Entrypoints
        if stem in ("__main__", "main", "app", "server", "index", "cli",
                    "wsgi", "asgi", "manage", "run", "start"):
            return "entrypoint"

        # Routers / HTTP handlers
        symbol_names_lower = {s.name.lower() for s in symbols}
        if (
            stem in ("routes", "router", "routers", "views", "handlers",
                     "endpoints", "api", "urls")
            or any(
                n.startswith(("create_router", "create_app", "setup_routes", "register_routes"))
                for n in symbol_names_lower
            )
        ):
            return "router"

        # Models / schemas
        class_names_lower = {s.name.lower() for s in symbols if s.kind == "class"}
        if (
            stem in ("models", "model", "schema", "schemas", "entities", "entity",
                     "types", "interfaces")
            or any(
                "model" in n or "schema" in n or "entity" in n
                for n in class_names_lower
            )
        ):
            return "model"

        return "utility"

    # ── Python analysis ───────────────────────────────────────────────────────

    def _analyze_python(
        self,
        source: str,
        file_id: int,
    ) -> tuple[list[SymbolRecord], list[ImportRecord]]:
        """Parse Python source with the stdlib ast module."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            logger.debug("Python SyntaxError: %s", exc)
            return [], []

        symbols: list[SymbolRecord] = []
        imports: list[ImportRecord] = []

        for node in ast.iter_child_nodes(tree):
            # Top-level functions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(SymbolRecord(
                    file_id=file_id,
                    name=node.name,
                    kind="function",
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    is_exported=not node.name.startswith("_"),
                ))

            # Top-level classes + their methods
            elif isinstance(node, ast.ClassDef):
                symbols.append(SymbolRecord(
                    file_id=file_id,
                    name=node.name,
                    kind="class",
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    is_exported=not node.name.startswith("_"),
                ))
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbols.append(SymbolRecord(
                            file_id=file_id,
                            name=child.name,
                            kind="method",
                            line_start=child.lineno,
                            line_end=child.end_lineno or child.lineno,
                            is_exported=not child.name.startswith("_"),
                            parent_name=node.name,
                        ))

            # Top-level constants/variables (ALL_CAPS or annotated assignments)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        symbols.append(SymbolRecord(
                            file_id=file_id,
                            name=target.id,
                            kind="constant",
                            line_start=node.lineno,
                            line_end=node.lineno,
                            is_exported=True,
                        ))

            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    name = node.target.id
                    if name.isupper():
                        symbols.append(SymbolRecord(
                            file_id=file_id,
                            name=name,
                            kind="constant",
                            line_start=node.lineno,
                            line_end=node.lineno,
                            is_exported=True,
                        ))

            # Imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportRecord(
                        from_file_id=file_id,
                        imported_module=alias.name,
                        import_kind="module",
                    ))

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append(ImportRecord(
                    from_file_id=file_id,
                    imported_module=module,
                    import_kind="from",
                ))

        return symbols, imports

    # ── JS / TS analysis ──────────────────────────────────────────────────────

    def _analyze_js_ts(
        self,
        source: str,
        file_id: int,
    ) -> tuple[list[SymbolRecord], list[ImportRecord]]:
        """Extract symbols and imports from JS/TS using regex line scanning."""
        symbols: list[SymbolRecord] = []
        imports: list[ImportRecord] = []

        for lineno, raw_line in enumerate(source.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("//") or line.startswith("*"):
                continue

            # Symbols
            for pattern, kind, exported in _JS_SYMBOL_PATTERNS:
                m = pattern.match(line)
                if m:
                    symbols.append(SymbolRecord(
                        file_id=file_id,
                        name=m.group(1),
                        kind=kind,
                        line_start=lineno,
                        is_exported=exported,
                    ))
                    break  # first match wins per line

            # Imports
            for pattern, import_kind in _JS_IMPORT_PATTERNS:
                m = pattern.search(line)
                if m:
                    imports.append(ImportRecord(
                        from_file_id=file_id,
                        imported_module=m.group(1),
                        import_kind=import_kind,
                    ))
                    break

        return symbols, imports

    # ── Generic fallback ──────────────────────────────────────────────────────

    def _analyze_generic(
        self,
        source: str,
        file_id: int,
    ) -> tuple[list[SymbolRecord], list[ImportRecord]]:
        """Line-scanning fallback for Java, Go, Rust, Ruby, and other languages."""
        symbols: list[SymbolRecord] = []

        for lineno, raw_line in enumerate(source.splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            for pattern, kind in _GENERIC_SYMBOL_PATTERNS:
                m = pattern.match(line)
                if m:
                    name = m.group(1)
                    if name and len(name) > 1:
                        symbols.append(SymbolRecord(
                            file_id=file_id,
                            name=name,
                            kind=kind,
                            line_start=lineno,
                        ))
                    break

        return symbols, []  # Generic analyzer does not extract imports
