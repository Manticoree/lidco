"""Tests for IndexContextEnricher — compact structural context for agents."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from lidco.index.context_enricher import IndexContextEnricher
from lidco.index.db import IndexDatabase
from lidco.index.project_indexer import ProjectIndexer
from lidco.index.schema import FileRecord, SymbolRecord


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path: Path) -> IndexDatabase:
    return IndexDatabase(tmp_path / ".lidco" / "index.db")


@pytest.fixture()
def enricher(db: IndexDatabase) -> IndexContextEnricher:
    return IndexContextEnricher(db)


def _insert_file(
    db: IndexDatabase,
    path: str,
    role: str = "utility",
    language: str = "python",
    lines: int = 10,
) -> int:
    rec = FileRecord(
        path=path,
        language=language,
        role=role,
        size_bytes=100,
        mtime=time.time(),
        lines_count=lines,
        indexed_at=time.time(),
    )
    return db.upsert_file(rec)


def _insert_symbol(
    db: IndexDatabase,
    file_id: int,
    name: str,
    kind: str = "function",
    line_start: int = 1,
    is_exported: bool = True,
) -> None:
    db.insert_symbols([
        SymbolRecord(
            file_id=file_id,
            name=name,
            kind=kind,
            line_start=line_start,
            is_exported=is_exported,
        )
    ])


# ── is_indexed ────────────────────────────────────────────────────────────────


class TestIsIndexed:
    def test_false_on_empty_db(self, enricher: IndexContextEnricher) -> None:
        assert enricher.is_indexed() is False

    def test_true_after_file_inserted(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        _insert_file(db, "src/main.py")
        assert enricher.is_indexed() is True


# ── get_project_summary ───────────────────────────────────────────────────────


class TestGetProjectSummary:
    def test_empty_returns_empty_string(self, enricher: IndexContextEnricher) -> None:
        assert enricher.get_project_summary() == ""

    def test_contains_file_count(self, db: IndexDatabase, enricher: IndexContextEnricher) -> None:
        _insert_file(db, "src/a.py")
        _insert_file(db, "src/b.py")
        summary = enricher.get_project_summary()
        assert "2 files" in summary

    def test_contains_symbol_count(self, db: IndexDatabase, enricher: IndexContextEnricher) -> None:
        fid = _insert_file(db, "src/a.py")
        _insert_symbol(db, fid, "my_func")
        summary = enricher.get_project_summary()
        assert "1 symbols" in summary

    def test_contains_language(self, db: IndexDatabase, enricher: IndexContextEnricher) -> None:
        _insert_file(db, "src/a.py", language="python")
        summary = enricher.get_project_summary()
        assert "python" in summary

    def test_multiple_languages(self, db: IndexDatabase, enricher: IndexContextEnricher) -> None:
        _insert_file(db, "src/a.py", language="python")
        _insert_file(db, "src/b.ts", language="typescript")
        summary = enricher.get_project_summary()
        assert "python" in summary
        assert "typescript" in summary

    def test_starts_with_prefix(self, db: IndexDatabase, enricher: IndexContextEnricher) -> None:
        _insert_file(db, "src/a.py")
        summary = enricher.get_project_summary()
        assert summary.startswith("Project index:")


# ── get_entrypoints ───────────────────────────────────────────────────────────


class TestGetEntrypoints:
    def test_empty_when_none(self, enricher: IndexContextEnricher) -> None:
        assert enricher.get_entrypoints() == []

    def test_returns_entrypoint_files(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        _insert_file(db, "src/main.py", role="entrypoint")
        _insert_file(db, "src/utils.py", role="utility")
        eps = enricher.get_entrypoints()
        assert len(eps) == 1
        assert eps[0].path == "src/main.py"


# ── find_relevant_files ───────────────────────────────────────────────────────


class TestFindRelevantFiles:
    def test_empty_query_returns_empty(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        _insert_file(db, "src/main.py")
        assert enricher.find_relevant_files("") == []

    def test_whitespace_query_returns_empty(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        _insert_file(db, "src/main.py")
        assert enricher.find_relevant_files("   ") == []

    def test_symbol_name_match(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        fid = _insert_file(db, "src/auth.py")
        _insert_symbol(db, fid, "authenticate_user")
        result = enricher.find_relevant_files("authenticate user")
        assert any(f.path == "src/auth.py" for f in result)

    def test_path_match(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        _insert_file(db, "src/auth.py")
        _insert_file(db, "src/utils.py")
        result = enricher.find_relevant_files("auth login")
        paths = [f.path for f in result]
        assert "src/auth.py" in paths

    def test_higher_scored_file_first(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        # auth.py matches both symbol and path; utils.py matches only path
        fid_auth = _insert_file(db, "src/auth.py")
        _insert_symbol(db, fid_auth, "auth_service")
        _insert_file(db, "src/utils.py")
        result = enricher.find_relevant_files("auth")
        assert result[0].path == "src/auth.py"

    def test_limit_respected(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        for i in range(10):
            fid = _insert_file(db, f"src/module_{i}.py")
            _insert_symbol(db, fid, f"func_{i}")
        result = enricher.find_relevant_files("func", limit=3)
        assert len(result) <= 3

    def test_no_match_returns_empty(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        _insert_file(db, "src/main.py")
        result = enricher.find_relevant_files("xyz_nonexistent_zzz")
        assert result == []

    def test_all_short_terms_returns_empty(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        # All tokens ≤ 2 chars → terms list is empty → []
        _insert_file(db, "src/main.py")
        result = enricher.find_relevant_files("a b")
        assert result == []


# ── get_context ───────────────────────────────────────────────────────────────


class TestGetContext:
    def test_empty_db_returns_empty_string(self, enricher: IndexContextEnricher) -> None:
        assert enricher.get_context() == ""

    def test_contains_summary(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        _insert_file(db, "src/main.py")
        ctx = enricher.get_context()
        assert "files" in ctx

    def test_contains_entrypoint(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        _insert_file(db, "src/main.py", role="entrypoint")
        ctx = enricher.get_context()
        assert "Entrypoints" in ctx
        assert "src/main.py" in ctx

    def test_no_entrypoints_section_when_absent(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        _insert_file(db, "src/utils.py", role="utility")
        ctx = enricher.get_context()
        assert "Entrypoints" not in ctx

    def test_query_adds_relevant_section(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        fid = _insert_file(db, "src/auth.py")
        _insert_symbol(db, fid, "authenticate")
        ctx = enricher.get_context(query="authenticate user")
        assert "Relevant files" in ctx
        assert "src/auth.py" in ctx

    def test_no_query_no_relevant_section(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        fid = _insert_file(db, "src/auth.py")
        _insert_symbol(db, fid, "authenticate")
        ctx = enricher.get_context()
        assert "Relevant files" not in ctx

    def test_respects_max_chars(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        for i in range(50):
            fid = _insert_file(db, f"src/module_{i:03d}.py")
            _insert_symbol(db, fid, f"some_function_{i}")
        ctx = enricher.get_context(max_chars=200)
        assert len(ctx) <= 203  # 200 + "..." possible

    def test_symbols_included_in_query_context(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        fid = _insert_file(db, "src/models.py", role="model")
        _insert_symbol(db, fid, "UserModel", kind="class")
        ctx = enricher.get_context(query="user model")
        assert "UserModel" in ctx

    def test_methods_excluded_from_query_context(
        self, db: IndexDatabase, enricher: IndexContextEnricher
    ) -> None:
        fid = _insert_file(db, "src/models.py", role="model")
        _insert_symbol(db, fid, "UserModel", kind="class")
        _insert_symbol(db, fid, "save", kind="method")
        ctx = enricher.get_context(query="user model")
        # save is a method — should not appear in the compact context
        assert "save" not in ctx


# ── from_project_dir ──────────────────────────────────────────────────────────


class TestFromProjectDir:
    def test_returns_none_when_no_db(self, tmp_path: Path) -> None:
        result = IndexContextEnricher.from_project_dir(tmp_path)
        assert result is None

    def test_returns_enricher_when_db_exists(self, tmp_path: Path) -> None:
        # Create the DB by running a full index
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass\n", encoding="utf-8")

        db = IndexDatabase(tmp_path / ".lidco" / "project_index.db")
        ProjectIndexer(project_dir=tmp_path, db=db).run_full_index()
        db.close()

        enricher = IndexContextEnricher.from_project_dir(tmp_path)
        assert enricher is not None
        assert enricher.is_indexed() is True

    def test_returns_none_on_db_open_error(self, tmp_path: Path) -> None:
        # Create the DB file so path check passes, then make IndexDatabase raise
        db_path = tmp_path / ".lidco" / "project_index.db"
        db_path.parent.mkdir(parents=True)
        db_path.write_bytes(b"not a sqlite db")  # corrupt file
        result = IndexContextEnricher.from_project_dir(tmp_path)
        # Should return None (or a valid enricher if sqlite is forgiving) — either way no crash
        # On corrupt file sqlite raises DatabaseError, caught as Exception → None
        assert result is None or not result.is_indexed()

    def test_enricher_has_correct_data(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass\n", encoding="utf-8")

        db = IndexDatabase(tmp_path / ".lidco" / "project_index.db")
        ProjectIndexer(project_dir=tmp_path, db=db).run_full_index()
        db.close()

        enricher = IndexContextEnricher.from_project_dir(tmp_path)
        assert enricher is not None
        ctx = enricher.get_context(query="main")
        assert "main.py" in ctx


# ── Integration: real project ─────────────────────────────────────────────────


class TestIntegration:
    def test_full_project_context(self, tmp_path: Path, db: IndexDatabase) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass\n", encoding="utf-8")
        (src / "auth.py").write_text(
            "def login(user): pass\ndef logout(): pass\n", encoding="utf-8"
        )
        (src / "models.py").write_text("class User: pass\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_auth.py").write_text(
            "def test_login(): pass\n", encoding="utf-8"
        )

        indexer = ProjectIndexer(project_dir=tmp_path, db=db)
        indexer.run_full_index()

        enricher = IndexContextEnricher(db)
        assert enricher.is_indexed()

        # Summary has right file count
        summary = enricher.get_project_summary()
        assert "4 files" in summary

        # Query for auth returns auth.py high in the list
        relevant = enricher.find_relevant_files("login authentication")
        assert any("auth.py" in f.path for f in relevant)

        # Full context is non-empty and under budget
        ctx = enricher.get_context(query="login")
        assert ctx
        assert len(ctx) <= 3000
