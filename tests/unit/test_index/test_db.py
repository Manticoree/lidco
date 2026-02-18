"""Tests for IndexDatabase — SQLite data layer."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from lidco.index.db import IndexDatabase
from lidco.index.schema import FileRecord, ImportRecord, IndexStats, SymbolRecord


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path: Path) -> IndexDatabase:
    return IndexDatabase(tmp_path / ".lidco" / "project_index.db")


def _file(path: str = "src/foo.py", role: str = "utility", mtime: float = 1_000.0) -> FileRecord:
    return FileRecord(
        path=path,
        language="python",
        role=role,
        size_bytes=100,
        mtime=mtime,
        lines_count=20,
        indexed_at=time.time(),
    )


def _symbol(file_id: int, name: str = "my_func", kind: str = "function") -> SymbolRecord:
    return SymbolRecord(file_id=file_id, name=name, kind=kind, line_start=5, line_end=10)


def _import(file_id: int, module: str = "os", resolved: str = "") -> ImportRecord:
    return ImportRecord(from_file_id=file_id, imported_module=module, resolved_path=resolved)


# ── Schema & lifecycle ────────────────────────────────────────────────────────


class TestSchemaAndLifecycle:
    def test_db_file_created(self, tmp_path: Path) -> None:
        db_path = tmp_path / ".lidco" / "index.db"
        db = IndexDatabase(db_path)
        db.close()
        assert db_path.exists()

    def test_context_manager(self, tmp_path: Path) -> None:
        db_path = tmp_path / "index.db"
        with IndexDatabase(db_path) as db:
            assert db.get_stats().total_files == 0

    def test_schema_idempotent(self, tmp_path: Path) -> None:
        """Applying schema twice should not raise."""
        db_path = tmp_path / "index.db"
        db = IndexDatabase(db_path)
        db._apply_schema()  # second application
        db.close()

    def test_empty_stats(self, db: IndexDatabase) -> None:
        stats = db.get_stats()
        assert stats.total_files == 0
        assert stats.total_symbols == 0
        assert stats.total_imports == 0
        assert stats.last_indexed_at is None
        assert stats.files_by_role == {}
        assert stats.files_by_language == {}


# ── Files ─────────────────────────────────────────────────────────────────────


class TestFiles:
    def test_upsert_returns_id(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        assert file_id > 0

    def test_get_file_by_path(self, db: IndexDatabase) -> None:
        db.upsert_file(_file("src/bar.py"))
        rec = db.get_file_by_path("src/bar.py")
        assert rec is not None
        assert rec.path == "src/bar.py"
        assert rec.language == "python"
        assert rec.role == "utility"

    def test_get_file_by_path_missing(self, db: IndexDatabase) -> None:
        assert db.get_file_by_path("nonexistent.py") is None

    def test_upsert_updates_existing(self, db: IndexDatabase) -> None:
        db.upsert_file(_file("src/foo.py", role="utility", mtime=100.0))
        db.upsert_file(_file("src/foo.py", role="entrypoint", mtime=200.0))
        rec = db.get_file_by_path("src/foo.py")
        assert rec is not None
        assert rec.role == "entrypoint"
        assert rec.mtime == 200.0

    def test_delete_file(self, db: IndexDatabase) -> None:
        db.upsert_file(_file("src/del.py"))
        db.delete_file("src/del.py")
        assert db.get_file_by_path("src/del.py") is None

    def test_list_file_mtimes(self, db: IndexDatabase) -> None:
        db.upsert_file(_file("a.py", mtime=1.0))
        db.upsert_file(_file("b.py", mtime=2.0))
        mtimes = db.list_file_mtimes()
        assert mtimes == {"a.py": 1.0, "b.py": 2.0}

    def test_query_files_by_role(self, db: IndexDatabase) -> None:
        db.upsert_file(_file("main.py", role="entrypoint"))
        db.upsert_file(_file("util.py", role="utility"))
        db.upsert_file(_file("app.py", role="entrypoint"))
        entrypoints = db.query_files_by_role("entrypoint")
        assert len(entrypoints) == 2
        assert all(r.role == "entrypoint" for r in entrypoints)

    def test_get_file_id(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file("src/foo.py"))
        assert db.get_file_id("src/foo.py") == file_id

    def test_get_file_id_missing(self, db: IndexDatabase) -> None:
        assert db.get_file_id("missing.py") is None


# ── Symbols ───────────────────────────────────────────────────────────────────


class TestSymbols:
    def test_insert_and_query(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        db.insert_symbols([_symbol(file_id, "Foo", "class"), _symbol(file_id, "bar", "function")])
        symbols = db.query_symbols(file_id=file_id)
        assert len(symbols) == 2
        names = {s.name for s in symbols}
        assert names == {"Foo", "bar"}

    def test_query_by_name_like(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        db.insert_symbols([_symbol(file_id, "handle_request"), _symbol(file_id, "handle_error")])
        results = db.query_symbols(name_like="handle%")
        assert len(results) == 2

    def test_query_by_kind(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        db.insert_symbols([
            _symbol(file_id, "MyClass", "class"),
            _symbol(file_id, "my_func", "function"),
        ])
        classes = db.query_symbols(kind="class")
        assert len(classes) == 1
        assert classes[0].name == "MyClass"

    def test_delete_symbols_for_file(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        db.insert_symbols([_symbol(file_id)])
        db.delete_symbols_for_file(file_id)
        assert db.query_symbols(file_id=file_id) == []

    def test_cascade_delete_on_file_removal(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file("src/gone.py"))
        db.insert_symbols([_symbol(file_id, "orphan")])
        db.delete_file("src/gone.py")
        # Symbols deleted via CASCADE
        assert db.query_symbols(file_id=file_id) == []

    def test_insert_empty_symbols_is_noop(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        db.insert_symbols([])  # must not raise
        assert db.query_symbols(file_id=file_id) == []

    def test_symbol_is_exported_flag(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        sym = SymbolRecord(
            file_id=file_id, name="PUBLIC", kind="constant",
            line_start=1, is_exported=True,
        )
        db.insert_symbols([sym])
        results = db.query_symbols(file_id=file_id)
        assert results[0].is_exported is True

    def test_symbol_parent_name(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        sym = SymbolRecord(
            file_id=file_id, name="save", kind="method",
            line_start=10, parent_name="MyModel",
        )
        db.insert_symbols([sym])
        results = db.query_symbols(file_id=file_id)
        assert results[0].parent_name == "MyModel"


# ── Imports ───────────────────────────────────────────────────────────────────


class TestImports:
    def test_insert_and_query(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        db.insert_imports([
            _import(file_id, "os"),
            _import(file_id, "pathlib", resolved="stdlib/pathlib"),
        ])
        imports = db.query_imports_for_file(file_id)
        assert len(imports) == 2

    def test_delete_imports_for_file(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        db.insert_imports([_import(file_id)])
        db.delete_imports_for_file(file_id)
        assert db.query_imports_for_file(file_id) == []

    def test_cascade_delete_on_file_removal(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file("src/gone2.py"))
        db.insert_imports([_import(file_id)])
        db.delete_file("src/gone2.py")
        assert db.query_imports_for_file(file_id) == []

    def test_query_files_importing(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file("src/main.py"))
        db.insert_imports([
            ImportRecord(
                from_file_id=file_id,
                imported_module="lidco.core.session",
                resolved_path="src/lidco/core/session.py",
            )
        ])
        result = db.query_files_importing("session")
        assert "src/main.py" in result

    def test_query_files_importing_no_match(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        db.insert_imports([_import(file_id, "os")])
        assert db.query_files_importing("does_not_exist") == []

    def test_insert_empty_imports_is_noop(self, db: IndexDatabase) -> None:
        file_id = db.upsert_file(_file())
        db.insert_imports([])
        assert db.query_imports_for_file(file_id) == []


# ── Meta ──────────────────────────────────────────────────────────────────────


class TestMeta:
    def test_set_and_get(self, db: IndexDatabase) -> None:
        db.set_meta("last_indexed_at", "1234567890.0")
        assert db.get_meta("last_indexed_at") == "1234567890.0"

    def test_get_missing_key(self, db: IndexDatabase) -> None:
        assert db.get_meta("nonexistent") is None

    def test_set_overwrites(self, db: IndexDatabase) -> None:
        db.set_meta("key", "first")
        db.set_meta("key", "second")
        assert db.get_meta("key") == "second"


# ── Stats ─────────────────────────────────────────────────────────────────────


class TestStats:
    def test_counts_reflect_data(self, db: IndexDatabase) -> None:
        f1 = db.upsert_file(_file("a.py", role="utility"))
        f2 = db.upsert_file(_file("b.py", role="entrypoint"))
        db.insert_symbols([_symbol(f1), _symbol(f1, "Bar", "class"), _symbol(f2)])
        db.insert_imports([_import(f1), _import(f2)])

        stats = db.get_stats()
        assert stats.total_files == 2
        assert stats.total_symbols == 3
        assert stats.total_imports == 2

    def test_files_by_role(self, db: IndexDatabase) -> None:
        db.upsert_file(_file("a.py", role="utility"))
        db.upsert_file(_file("b.py", role="utility"))
        db.upsert_file(_file("c.py", role="config"))

        stats = db.get_stats()
        assert stats.files_by_role["utility"] == 2
        assert stats.files_by_role["config"] == 1

    def test_files_by_language(self, db: IndexDatabase) -> None:
        db.upsert_file(_file("a.py"))  # python
        db.upsert_file(FileRecord(
            path="b.ts", language="typescript", role="utility",
            size_bytes=50, mtime=1.0, lines_count=10, indexed_at=time.time(),
        ))
        stats = db.get_stats()
        assert stats.files_by_language["python"] == 1
        assert stats.files_by_language["typescript"] == 1

    def test_last_indexed_at_from_meta(self, db: IndexDatabase) -> None:
        ts = 1_700_000_000.0
        db.set_meta("last_indexed_at", str(ts))
        stats = db.get_stats()
        assert stats.last_indexed_at == ts

    def test_last_indexed_at_none_when_unset(self, db: IndexDatabase) -> None:
        stats = db.get_stats()
        assert stats.last_indexed_at is None
