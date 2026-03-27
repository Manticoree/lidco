"""Tests for src/lidco/imports/resolver.py."""
import pytest

from lidco.imports.resolver import (
    ImportResolver,
    ImportResolverError,
    ImportSuggestion,
    ResolverResult,
)


class TestImportSuggestion:
    def test_fields(self):
        s = ImportSuggestion(name="Path", module="pathlib",
                             import_stmt="from pathlib import Path")
        assert s.name == "Path"
        assert s.module == "pathlib"
        assert s.is_stdlib is True

    def test_confidence_default(self):
        s = ImportSuggestion(name="x", module="m", import_stmt="import m")
        assert s.confidence == 1.0


class TestResolverResult:
    def test_has_suggestions_true(self):
        r = ResolverResult(
            undefined_names=["Path"],
            suggestions=[ImportSuggestion("Path", "pathlib", "from pathlib import Path")],
            source_imports=[],
        )
        assert r.has_suggestions() is True

    def test_has_suggestions_false(self):
        r = ResolverResult(undefined_names=[], suggestions=[], source_imports=[])
        assert r.has_suggestions() is False

    def test_import_block_deduplication(self):
        stmt = "from pathlib import Path"
        r = ResolverResult(
            undefined_names=["Path"],
            suggestions=[
                ImportSuggestion("Path", "pathlib", stmt),
                ImportSuggestion("Path", "pathlib", stmt),
            ],
            source_imports=[],
        )
        assert r.import_block().count(stmt) == 1

    def test_import_block_empty(self):
        r = ResolverResult(undefined_names=[], suggestions=[], source_imports=[])
        assert r.import_block() == ""


class TestImportResolver:
    def test_resolve_known_name(self):
        resolver = ImportResolver()
        result = resolver.resolve("p = Path('.')\n")
        assert "Path" in result.undefined_names

    def test_resolve_suggests_pathlib(self):
        resolver = ImportResolver()
        result = resolver.resolve("p = Path('.')\n")
        stmts = [s.import_stmt for s in result.suggestions]
        assert "from pathlib import Path" in stmts

    def test_resolve_no_undefined_when_imported(self):
        resolver = ImportResolver()
        result = resolver.resolve("from pathlib import Path\np = Path('.')\n")
        assert "Path" not in result.undefined_names

    def test_resolve_builtin_not_flagged(self):
        resolver = ImportResolver()
        result = resolver.resolve("print('hello')\nlen([1, 2])\n")
        assert "print" not in result.undefined_names
        assert "len" not in result.undefined_names

    def test_resolve_multiple_names(self):
        resolver = ImportResolver()
        result = resolver.resolve("x = json.dumps({})\ny = Path('.')\n")
        assert "json" in result.undefined_names
        assert "Path" in result.undefined_names

    def test_resolve_syntax_error_raises(self):
        resolver = ImportResolver()
        with pytest.raises(ImportResolverError):
            resolver.resolve("def (broken")

    def test_source_imports_tracked(self):
        resolver = ImportResolver()
        result = resolver.resolve("import os\nos.getcwd()\n")
        assert "os" in result.source_imports

    def test_suggest_for_name_known(self):
        resolver = ImportResolver()
        s = resolver.suggest_for_name("Path")
        assert s is not None
        assert "pathlib" in s.import_stmt

    def test_suggest_for_name_unknown(self):
        resolver = ImportResolver()
        assert resolver.suggest_for_name("totally_unknown_xyz") is None

    def test_add_mapping(self):
        resolver = ImportResolver()
        resolver.add_mapping("MyClass", "mymodule", "from mymodule import MyClass")
        s = resolver.suggest_for_name("MyClass")
        assert s is not None
        assert "mymodule" in s.import_stmt

    def test_known_names_nonempty(self):
        resolver = ImportResolver()
        assert len(resolver.known_names()) > 0

    def test_prepend_imports_adds_block(self):
        resolver = ImportResolver()
        source = "p = Path('.')\n"
        result = resolver.resolve(source)
        new_src = resolver.prepend_imports(source, result)
        assert "from pathlib import Path" in new_src
        assert "Path('.')" in new_src

    def test_prepend_imports_no_change_when_nothing(self):
        resolver = ImportResolver()
        source = "x = 1\n"
        result = resolver.resolve(source)
        new_src = resolver.prepend_imports(source, result)
        assert new_src == source

    def test_stdlib_is_stdlib_flag(self):
        resolver = ImportResolver()
        s = resolver.suggest_for_name("Path")
        assert s.is_stdlib is True

    def test_third_party_flag(self):
        resolver = ImportResolver()
        s = resolver.suggest_for_name("requests")
        assert s is not None
        assert s.is_stdlib is False
        assert s.confidence < 1.0

    def test_dataclass_suggestion(self):
        resolver = ImportResolver()
        result = resolver.resolve("@dataclass\nclass Foo:\n    pass\n")
        stmts = [s.import_stmt for s in result.suggestions]
        assert "from dataclasses import dataclass" in stmts

    def test_enum_suggestion(self):
        resolver = ImportResolver()
        result = resolver.resolve("class Color(Enum):\n    RED = 1\n")
        stmts = [s.import_stmt for s in result.suggestions]
        assert "from enum import Enum" in stmts
