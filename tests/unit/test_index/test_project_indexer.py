"""Tests for ProjectIndexer — full and incremental indexing."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from lidco.index.db import IndexDatabase
from lidco.index.project_indexer import ProjectIndexer


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path: Path) -> IndexDatabase:
    return IndexDatabase(tmp_path / ".lidco" / "project_index.db")


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """A minimal fake project directory."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    (src / "utils.py").write_text("def helper(): pass\nHELPER_CONST = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def indexer(project: Path, db: IndexDatabase) -> ProjectIndexer:
    return ProjectIndexer(project_dir=project, db=db)


# ── Full index ────────────────────────────────────────────────────────────────


class TestFullIndex:
    def test_indexes_python_files(self, indexer: ProjectIndexer) -> None:
        result = indexer.run_full_index()
        assert result.stats.total_files == 3

    def test_extracts_symbols(self, indexer: ProjectIndexer) -> None:
        indexer.run_full_index()
        symbols = indexer.db.query_symbols(name_like="main")
        assert any(s.name == "main" for s in symbols)

    def test_extracts_constants(self, indexer: ProjectIndexer) -> None:
        indexer.run_full_index()
        symbols = indexer.db.query_symbols(name_like="HELPER_CONST")
        assert len(symbols) == 1
        assert symbols[0].kind == "constant"

    def test_detects_test_role(self, indexer: ProjectIndexer) -> None:
        indexer.run_full_index()
        test_files = indexer.db.query_files_by_role("test")
        assert len(test_files) == 1
        assert "test_main" in test_files[0].path

    def test_detects_entrypoint_role(self, indexer: ProjectIndexer) -> None:
        indexer.run_full_index()
        entrypoints = indexer.db.query_files_by_role("entrypoint")
        assert any("main" in f.path for f in entrypoints)

    def test_sets_last_indexed_at(self, indexer: ProjectIndexer) -> None:
        before = time.time()
        indexer.run_full_index()
        after = time.time()
        val = indexer.db.get_meta("last_indexed_at")
        assert val is not None
        ts = float(val)
        assert before <= ts <= after

    def test_sets_max_file_mtime(self, indexer: ProjectIndexer) -> None:
        indexer.run_full_index()
        val = indexer.db.get_meta("max_file_mtime")
        assert val is not None
        assert float(val) > 0

    def test_result_counts(self, indexer: ProjectIndexer) -> None:
        result = indexer.run_full_index()
        assert result.added == 3
        assert result.updated == 0
        assert result.deleted == 0

    def test_full_index_twice_updates_not_adds(self, indexer: ProjectIndexer) -> None:
        indexer.run_full_index()
        result2 = indexer.run_full_index()
        # Second run: all files exist → all become "updated"
        assert result2.added == 0
        assert result2.updated == 3

    def test_skips_skip_dirs(self, project: Path, db: IndexDatabase) -> None:
        node_modules = project / "node_modules"
        node_modules.mkdir()
        (node_modules / "lib.js").write_text("function x() {}", encoding="utf-8")
        indexer = ProjectIndexer(project_dir=project, db=db)
        result = indexer.run_full_index()
        paths = {f.path for f in db.query_files_by_role("utility")}
        assert not any("node_modules" in p for p in paths)

    def test_skips_unsupported_extensions(self, project: Path, db: IndexDatabase) -> None:
        (project / "README.md").write_text("# Hello", encoding="utf-8")
        (project / "data.json").write_text("{}", encoding="utf-8")
        indexer = ProjectIndexer(project_dir=project, db=db)
        result = indexer.run_full_index()
        assert result.stats.total_files == 3  # same as before

    def test_skips_large_files(self, project: Path, db: IndexDatabase) -> None:
        big = project / "src" / "generated.py"
        big.write_text("x = 1\n" * 100_000, encoding="utf-8")
        indexer = ProjectIndexer(project_dir=project, db=db, max_file_size_kb=1)
        result = indexer.run_full_index()
        paths = [f.path for f in db.query_files_by_role("utility")]
        assert not any("generated" in p for p in paths)

    def test_removes_deleted_files(self, project: Path, db: IndexDatabase) -> None:
        indexer = ProjectIndexer(project_dir=project, db=db)
        indexer.run_full_index()
        # Delete a file and re-run full index
        (project / "src" / "utils.py").unlink()
        result = indexer.run_full_index()
        assert result.deleted == 1
        assert result.stats.total_files == 2

    def test_progress_callback_called(self, indexer: ProjectIndexer) -> None:
        calls: list[tuple[int, int, str]] = []
        indexer.run_full_index(progress_callback=lambda i, n, name: calls.append((i, n, name)))
        assert len(calls) == 3
        assert calls[-1][0] == calls[-1][1]  # last call: i == n

    def test_progress_callback_exception_ignored(self, indexer: ProjectIndexer) -> None:
        def bad_cb(*_: object) -> None:
            raise RuntimeError("callback error")

        # Must not raise
        result = indexer.run_full_index(progress_callback=bad_cb)
        assert result.stats.total_files == 3


# ── Incremental index ─────────────────────────────────────────────────────────


class TestIncrementalIndex:
    def test_first_run_adds_all(self, indexer: ProjectIndexer) -> None:
        result = indexer.run_incremental_index()
        assert result.added == 3
        assert result.updated == 0
        assert result.deleted == 0

    def test_unchanged_files_skipped(self, indexer: ProjectIndexer) -> None:
        indexer.run_incremental_index()
        result2 = indexer.run_incremental_index()
        assert result2.added == 0
        assert result2.updated == 0
        assert result2.skipped == 3

    def test_modified_file_updated(self, project: Path, db: IndexDatabase) -> None:
        indexer = ProjectIndexer(project_dir=project, db=db)
        indexer.run_incremental_index()

        # Modify a file (change content + bump mtime)
        target = project / "src" / "utils.py"
        target.write_text("def new_func(): pass\n", encoding="utf-8")
        # Ensure mtime actually differs (some filesystems have 1s resolution)
        new_mtime = target.stat().st_mtime + 1
        import os
        os.utime(target, (new_mtime, new_mtime))

        result2 = indexer.run_incremental_index()
        assert result2.updated == 1
        assert result2.skipped == 2

    def test_new_file_added(self, project: Path, db: IndexDatabase) -> None:
        indexer = ProjectIndexer(project_dir=project, db=db)
        indexer.run_incremental_index()

        (project / "src" / "new_module.py").write_text("def fresh(): pass\n", encoding="utf-8")
        result2 = indexer.run_incremental_index()
        assert result2.added == 1
        assert result2.skipped == 3

    def test_deleted_file_removed(self, project: Path, db: IndexDatabase) -> None:
        indexer = ProjectIndexer(project_dir=project, db=db)
        indexer.run_incremental_index()

        (project / "src" / "utils.py").unlink()
        result2 = indexer.run_incremental_index()
        assert result2.deleted == 1
        assert db.get_file_by_path("src/utils.py") is None

    def test_symbols_updated_on_reindex(self, project: Path, db: IndexDatabase) -> None:
        indexer = ProjectIndexer(project_dir=project, db=db)
        indexer.run_incremental_index()

        # Verify original symbol exists
        assert db.query_symbols(name_like="helper")

        # Rewrite file with different content
        target = project / "src" / "utils.py"
        target.write_text("def brand_new(): pass\n", encoding="utf-8")
        new_mtime = target.stat().st_mtime + 1
        import os
        os.utime(target, (new_mtime, new_mtime))

        indexer.run_incremental_index()

        # Old symbol gone, new symbol present
        assert db.query_symbols(name_like="brand_new")
        assert not db.query_symbols(name_like="helper")

    def test_cascade_deletes_symbols_on_file_delete(
        self, project: Path, db: IndexDatabase
    ) -> None:
        indexer = ProjectIndexer(project_dir=project, db=db)
        indexer.run_incremental_index()

        file_id = db.get_file_id("src/utils.py")
        assert file_id is not None
        assert db.query_symbols(file_id=file_id)

        (project / "src" / "utils.py").unlink()
        indexer.run_incremental_index()

        assert db.query_symbols(file_id=file_id) == []

    def test_sets_last_indexed_at(self, indexer: ProjectIndexer) -> None:
        before = time.time()
        indexer.run_incremental_index()
        after = time.time()
        val = indexer.db.get_meta("last_indexed_at")
        assert val is not None
        assert before <= float(val) <= after


# ── Staleness helpers ─────────────────────────────────────────────────────────


class TestStaleness:
    def test_is_stale_when_never_indexed(self, indexer: ProjectIndexer) -> None:
        assert indexer.is_stale() is True

    def test_is_stale_false_after_index(self, indexer: ProjectIndexer) -> None:
        indexer.run_full_index()
        assert indexer.is_stale(max_age_hours=24) is False

    def test_is_stale_true_when_old(self, indexer: ProjectIndexer) -> None:
        # Store a timestamp 25 hours in the past
        past = time.time() - 25 * 3600
        indexer.db.set_meta("last_indexed_at", str(past))
        assert indexer.is_stale(max_age_hours=24) is True

    def test_is_stale_false_when_recent(self, indexer: ProjectIndexer) -> None:
        recent = time.time() - 60  # 1 minute ago
        indexer.db.set_meta("last_indexed_at", str(recent))
        assert indexer.is_stale(max_age_hours=24) is False

    def test_has_new_files_when_no_meta(self, indexer: ProjectIndexer) -> None:
        assert indexer.has_new_files() is True

    def test_has_new_files_false_after_index(self, indexer: ProjectIndexer) -> None:
        indexer.run_full_index()
        assert indexer.has_new_files() is False

    def test_has_new_files_true_after_new_file(
        self, project: Path, db: IndexDatabase
    ) -> None:
        indexer = ProjectIndexer(project_dir=project, db=db)
        indexer.run_full_index()

        # Add a new file with a future mtime
        new_file = project / "src" / "added.py"
        new_file.write_text("x = 1\n", encoding="utf-8")
        future = time.time() + 10
        import os
        os.utime(new_file, (future, future))

        assert indexer.has_new_files() is True


# ── Stats delegation ──────────────────────────────────────────────────────────


class TestStats:
    def test_get_stats_delegates_to_db(self, indexer: ProjectIndexer) -> None:
        indexer.run_full_index()
        stats = indexer.get_stats()
        assert stats.total_files == 3
        assert stats.total_symbols > 0

    def test_db_property(self, indexer: ProjectIndexer) -> None:
        assert indexer.db is indexer._db


# ── Integration: real project layout ─────────────────────────────────────────


class TestRealLayout:
    def test_typescript_project(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "index.ts").write_text(
            "export function main(): void {}\n", encoding="utf-8"
        )
        (src / "auth.ts").write_text(
            "export class AuthService {}\nexport function login(): void {}\n",
            encoding="utf-8",
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "auth.spec.ts").write_text(
            "describe('auth', () => {});\n", encoding="utf-8"
        )

        db = IndexDatabase(tmp_path / ".lidco" / "index.db")
        indexer = ProjectIndexer(project_dir=tmp_path, db=db)
        result = indexer.run_full_index()

        assert result.stats.total_files == 3
        assert result.stats.files_by_language.get("typescript", 0) == 3

        entrypoints = db.query_files_by_role("entrypoint")
        assert any("index" in f.path for f in entrypoints)

        tests = db.query_files_by_role("test")
        assert len(tests) == 1

        symbols = db.query_symbols(name_like="AuthService")
        assert symbols[0].kind == "class"

    def test_mixed_language_project(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("def run(): pass\n", encoding="utf-8")
        (tmp_path / "helper.js").write_text("function util() {}\n", encoding="utf-8")

        db = IndexDatabase(tmp_path / ".lidco" / "index.db")
        indexer = ProjectIndexer(project_dir=tmp_path, db=db)
        indexer.run_full_index()

        stats = indexer.get_stats()
        assert stats.files_by_language.get("python", 0) == 1
        assert stats.files_by_language.get("javascript", 0) == 1
