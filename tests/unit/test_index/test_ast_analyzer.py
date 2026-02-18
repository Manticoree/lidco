"""Tests for AstAnalyzer — static symbol and import extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.index.ast_analyzer import AstAnalyzer
from lidco.index.schema import SymbolRecord


@pytest.fixture()
def analyzer() -> AstAnalyzer:
    return AstAnalyzer()


def _py(tmp_path: Path, name: str, source: str) -> Path:
    p = tmp_path / name
    p.write_text(source, encoding="utf-8")
    return p


def _ts(tmp_path: Path, name: str, source: str) -> Path:
    p = tmp_path / name
    p.write_text(source, encoding="utf-8")
    return p


# ── Python: symbols ───────────────────────────────────────────────────────────


class TestPythonSymbols:
    def test_top_level_function(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "def greet(name: str) -> str:\n    return name\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "greet" and s.kind == "function" for s in symbols)

    def test_async_function(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "async def fetch() -> None:\n    pass\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "fetch" and s.kind == "function" for s in symbols)

    def test_class(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "class MyService:\n    pass\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "MyService" and s.kind == "class" for s in symbols)

    def test_class_methods(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        src = "class Repo:\n    def save(self): pass\n    def delete(self): pass\n"
        f = _py(tmp_path, "repo.py", src)
        symbols, _ = analyzer.analyze(f, file_id=2)
        methods = [s for s in symbols if s.kind == "method"]
        names = {m.name for m in methods}
        assert names == {"save", "delete"}
        assert all(m.parent_name == "Repo" for m in methods)

    def test_private_not_exported(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "def _helper(): pass\nclass _Internal: pass\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert all(not s.is_exported for s in symbols)

    def test_public_is_exported(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "def public_func(): pass\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert symbols[0].is_exported is True

    def test_all_caps_constant(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "MAX_RETRIES = 3\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "MAX_RETRIES" and s.kind == "constant" for s in symbols)

    def test_annotated_constant(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "TIMEOUT: int = 30\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "TIMEOUT" and s.kind == "constant" for s in symbols)

    def test_line_numbers(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        src = "x = 1\n\ndef foo():\n    pass\n"
        f = _py(tmp_path, "foo.py", src)
        symbols, _ = analyzer.analyze(f, file_id=1)
        func = next(s for s in symbols if s.name == "foo")
        assert func.line_start == 3

    def test_syntax_error_returns_empty(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "bad.py", "def broken(\n")
        symbols, imports = analyzer.analyze(f, file_id=1)
        assert symbols == []
        assert imports == []

    def test_empty_file_returns_empty(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "empty.py", "   \n\n")
        symbols, imports = analyzer.analyze(f, file_id=1)
        assert symbols == []
        assert imports == []


# ── Python: imports ───────────────────────────────────────────────────────────


class TestPythonImports:
    def test_import_module(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "import os\nimport sys\n")
        _, imports = analyzer.analyze(f, file_id=1)
        modules = {i.imported_module for i in imports}
        assert modules == {"os", "sys"}
        assert all(i.import_kind == "module" for i in imports)

    def test_from_import(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "from pathlib import Path\nfrom typing import Any\n")
        _, imports = analyzer.analyze(f, file_id=1)
        modules = {i.imported_module for i in imports}
        assert "pathlib" in modules
        assert "typing" in modules
        assert all(i.import_kind == "from" for i in imports)

    def test_relative_import(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "from .base import BaseClass\n")
        _, imports = analyzer.analyze(f, file_id=1)
        # relative import: module is "" (from . import X) or "base"
        assert len(imports) == 1
        assert imports[0].import_kind == "from"

    def test_file_id_propagated(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "import os\ndef fn(): pass\n")
        symbols, imports = analyzer.analyze(f, file_id=42)
        assert all(s.file_id == 42 for s in symbols)
        assert all(i.from_file_id == 42 for i in imports)


# ── JS/TS: symbols ────────────────────────────────────────────────────────────


class TestJsTsSymbols:
    def test_function_declaration(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "auth.ts", "function login(user: string): void {}\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "login" and s.kind == "function" for s in symbols)

    def test_export_function(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "auth.ts", "export function logout(): void {}\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        sym = next(s for s in symbols if s.name == "logout")
        assert sym.is_exported is True

    def test_class_declaration(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "service.ts", "class UserService {\n  find() {}\n}\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "UserService" and s.kind == "class" for s in symbols)

    def test_export_class(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "service.ts", "export class AuthService {}\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        sym = next(s for s in symbols if s.name == "AuthService")
        assert sym.is_exported is True

    def test_arrow_function(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "utils.ts", "const transform = (x: number) => x * 2;\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "transform" and s.kind == "function" for s in symbols)

    def test_export_arrow_function(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "utils.ts", "export const handler = async (req: Request) => {};\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        sym = next(s for s in symbols if s.name == "handler")
        assert sym.is_exported is True

    def test_all_caps_constant(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "config.ts", "const MAX_SIZE = 100;\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "MAX_SIZE" and s.kind == "constant" for s in symbols)

    def test_export_const(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "config.ts", "export const API_URL = 'https://api.example.com';\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "API_URL" and s.is_exported for s in symbols)

    def test_js_file(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "index.js", "function init() {}\nclass App {}\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        names = {s.name for s in symbols}
        assert "init" in names
        assert "App" in names

    def test_async_function(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _ts(tmp_path, "api.ts", "export async function fetchUser(): Promise<User> {}\n")
        symbols, _ = analyzer.analyze(f, file_id=1)
        assert any(s.name == "fetchUser" for s in symbols)

    def test_comments_skipped(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        src = "// function fakeFunc() {}\nfunction realFunc() {}\n"
        f = _ts(tmp_path, "foo.ts", src)
        symbols, _ = analyzer.analyze(f, file_id=1)
        names = {s.name for s in symbols}
        assert "realFunc" in names
        assert "fakeFunc" not in names


# ── JS/TS: imports ────────────────────────────────────────────────────────────


class TestJsTsImports:
    def test_import_from(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        src = "import { useState } from 'react';\n"
        f = _ts(tmp_path, "comp.tsx", src)
        _, imports = analyzer.analyze(f, file_id=1)
        assert any(i.imported_module == "react" and i.import_kind == "from" for i in imports)

    def test_import_default(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        src = "import express from 'express';\n"
        f = _ts(tmp_path, "app.ts", src)
        _, imports = analyzer.analyze(f, file_id=1)
        assert any(i.imported_module == "express" for i in imports)

    def test_require(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        src = "const path = require('path');\n"
        f = _ts(tmp_path, "app.js", src)
        _, imports = analyzer.analyze(f, file_id=1)
        assert any(i.imported_module == "path" and i.import_kind == "require" for i in imports)

    def test_relative_import(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        src = "import { Session } from '../core/session';\n"
        f = _ts(tmp_path, "app.ts", src)
        _, imports = analyzer.analyze(f, file_id=1)
        assert any("session" in i.imported_module for i in imports)


# ── File role detection ───────────────────────────────────────────────────────


class TestDetectFileRole:
    def _role(self, path: str, symbols: list[SymbolRecord] | None = None) -> str:
        return AstAnalyzer.detect_file_role(Path(path), symbols or [])

    def test_test_file_prefix(self) -> None:
        assert self._role("tests/test_auth.py") == "test"

    def test_test_file_suffix(self) -> None:
        assert self._role("src/auth_test.py") == "test"

    def test_test_in_path(self) -> None:
        assert self._role("src/tests/auth.py") == "test"

    def test_spec_file(self) -> None:
        assert self._role("src/auth.spec.ts") == "test"

    def test_config_name(self) -> None:
        assert self._role("src/config.py") == "config"

    def test_settings_name(self) -> None:
        assert self._role("src/settings.py") == "config"

    def test_pyproject(self) -> None:
        assert self._role("pyproject.toml") == "config"

    def test_entrypoint_main(self) -> None:
        assert self._role("src/__main__.py") == "entrypoint"

    def test_entrypoint_app(self) -> None:
        assert self._role("src/app.py") == "entrypoint"

    def test_entrypoint_cli(self) -> None:
        assert self._role("src/cli.py") == "entrypoint"

    def test_router_stem(self) -> None:
        assert self._role("src/router.py") == "router"

    def test_router_views(self) -> None:
        assert self._role("src/views.py") == "router"

    def test_model_stem(self) -> None:
        assert self._role("src/models.py") == "model"

    def test_model_via_class_name(self) -> None:
        sym = SymbolRecord(file_id=1, name="UserModel", kind="class", line_start=1)
        assert self._role("src/user.py", [sym]) == "model"

    def test_schema_via_class_name(self) -> None:
        sym = SymbolRecord(file_id=1, name="UserSchema", kind="class", line_start=1)
        assert self._role("src/serializers.py", [sym]) == "model"

    def test_utility_default(self) -> None:
        assert self._role("src/utils.py") == "utility"

    def test_test_wins_over_entrypoint(self) -> None:
        # A file named test_main.py should be classified as test, not entrypoint
        assert self._role("tests/test_main.py") == "test"


# ── Unsupported / edge cases ──────────────────────────────────────────────────


class TestEdgeCases:
    def test_unsupported_extension(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = tmp_path / "readme.md"
        f.write_text("# Hello\n")
        symbols, imports = analyzer.analyze(f, file_id=1)
        assert symbols == []
        assert imports == []

    def test_missing_file(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        symbols, imports = analyzer.analyze(tmp_path / "ghost.py", file_id=1)
        assert symbols == []
        assert imports == []

    def test_file_id_zero_default(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        f = _py(tmp_path, "foo.py", "def fn(): pass\n")
        symbols, _ = analyzer.analyze(f)  # no file_id argument
        assert symbols[0].file_id == 0

    def test_complex_python_module(self, analyzer: AstAnalyzer, tmp_path: Path) -> None:
        src = """\
from __future__ import annotations
import os
from pathlib import Path
from typing import Any

TIMEOUT: int = 30
MAX_WORKERS = 4

class BaseHandler:
    def handle(self, request: Any) -> None:
        pass
    def _internal(self) -> None:
        pass

class SpecialHandler(BaseHandler):
    async def handle(self, request: Any) -> None:
        pass

def create_handler() -> BaseHandler:
    return BaseHandler()
"""
        f = _py(tmp_path, "handlers.py", src)
        symbols, imports = analyzer.analyze(f, file_id=7)

        symbol_names = {s.name for s in symbols}
        assert "BaseHandler" in symbol_names
        assert "SpecialHandler" in symbol_names
        assert "create_handler" in symbol_names
        assert "handle" in symbol_names
        assert "TIMEOUT" in symbol_names
        assert "MAX_WORKERS" in symbol_names

        import_modules = {i.imported_module for i in imports}
        assert "os" in import_modules
        assert "pathlib" in import_modules

        # Private method should not be exported
        internal = next(s for s in symbols if s.name == "_internal")
        assert internal.is_exported is False
