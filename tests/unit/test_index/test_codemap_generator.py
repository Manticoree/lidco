"""Tests for CodemapGenerator — Markdown codemap renderer."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from lidco.index.codemap_generator import CodemapGenerator
from lidco.index.db import IndexDatabase
from lidco.index.project_indexer import ProjectIndexer
from lidco.index.schema import FileRecord, SymbolRecord


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path: Path) -> IndexDatabase:
    return IndexDatabase(tmp_path / ".lidco" / "index.db")


@pytest.fixture()
def gen(db: IndexDatabase) -> CodemapGenerator:
    return CodemapGenerator(db)


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
    parent_name: str = "",
) -> None:
    db.insert_symbols([
        SymbolRecord(
            file_id=file_id,
            name=name,
            kind=kind,
            line_start=line_start,
            is_exported=is_exported,
            parent_name=parent_name,
        )
    ])


# ── Header ────────────────────────────────────────────────────────────────────


class TestHeader:
    def test_title_present(self, gen: CodemapGenerator) -> None:
        out = gen.generate()
        assert "# Project Codemap" in out

    def test_empty_index_zero_counts(self, gen: CodemapGenerator) -> None:
        out = gen.generate()
        assert "0 files" in out
        assert "0 symbols" in out
        assert "0 imports" in out

    def test_timestamp_included_after_index(
        self, tmp_path: Path, db: IndexDatabase
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass\n", encoding="utf-8")
        indexer = ProjectIndexer(project_dir=tmp_path, db=db)
        indexer.run_full_index()

        out = CodemapGenerator(db).generate()
        assert "Indexed:" in out

    def test_no_timestamp_when_never_indexed(self, gen: CodemapGenerator) -> None:
        out = gen.generate()
        assert "Indexed:" not in out

    def test_file_count_in_header(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/a.py")
        _insert_file(db, "src/b.py")
        out = CodemapGenerator(db).generate()
        assert "2 files" in out

    def test_single_language_no_breakdown(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/a.py", language="python")
        out = CodemapGenerator(db).generate()
        assert "Languages:" not in out

    def test_multi_language_breakdown(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/a.py", language="python")
        _insert_file(db, "src/b.ts", language="typescript")
        out = CodemapGenerator(db).generate()
        assert "Languages:" in out
        assert "python" in out
        assert "typescript" in out


# ── Sections ──────────────────────────────────────────────────────────────────


class TestSections:
    def test_entrypoint_section(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/main.py", role="entrypoint")
        out = CodemapGenerator(db).generate()
        assert "## Entrypoints" in out
        assert "src/main.py" in out

    def test_config_section(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/config.py", role="config")
        out = CodemapGenerator(db).generate()
        assert "## Config" in out

    def test_model_section(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/models.py", role="model")
        out = CodemapGenerator(db).generate()
        assert "## Models" in out

    def test_router_section(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/router.py", role="router")
        out = CodemapGenerator(db).generate()
        assert "## Routers" in out

    def test_utility_section(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/utils.py", role="utility")
        out = CodemapGenerator(db).generate()
        assert "## Utilities" in out

    def test_test_section(self, db: IndexDatabase) -> None:
        _insert_file(db, "tests/test_foo.py", role="test")
        out = CodemapGenerator(db).generate()
        assert "## Tests" in out

    def test_empty_role_section_omitted(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/utils.py", role="utility")
        out = CodemapGenerator(db).generate()
        # No entrypoints inserted — section should be absent
        assert "## Entrypoints" not in out

    def test_role_order_entrypoint_before_test(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/main.py", role="entrypoint")
        _insert_file(db, "tests/test_x.py", role="test")
        out = CodemapGenerator(db).generate()
        assert out.index("## Entrypoints") < out.index("## Tests")

    def test_files_sorted_within_section(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/z_module.py", role="utility")
        _insert_file(db, "src/a_module.py", role="utility")
        out = CodemapGenerator(db).generate()
        assert out.index("a_module") < out.index("z_module")


# ── Symbol rendering ──────────────────────────────────────────────────────────


class TestSymbolRendering:
    def test_function_listed(self, db: IndexDatabase) -> None:
        fid = _insert_file(db, "src/utils.py")
        _insert_symbol(db, fid, "my_func", kind="function")
        out = CodemapGenerator(db).generate()
        assert "`my_func` function" in out

    def test_constant_listed(self, db: IndexDatabase) -> None:
        fid = _insert_file(db, "src/utils.py")
        _insert_symbol(db, fid, "MAX_RETRIES", kind="constant")
        out = CodemapGenerator(db).generate()
        assert "`MAX_RETRIES` constant" in out

    def test_class_listed(self, db: IndexDatabase) -> None:
        fid = _insert_file(db, "src/models.py", role="model")
        _insert_symbol(db, fid, "UserModel", kind="class")
        out = CodemapGenerator(db).generate()
        assert "`UserModel` class" in out

    def test_method_indented_under_class(self, db: IndexDatabase) -> None:
        fid = _insert_file(db, "src/models.py", role="model")
        _insert_symbol(db, fid, "User", kind="class", line_start=1)
        _insert_symbol(db, fid, "save", kind="method", line_start=2, parent_name="User")
        out = CodemapGenerator(db).generate()
        # Method line must start with two spaces (indented under class)
        assert "  - `save` method" in out

    def test_private_symbol_marked(self, db: IndexDatabase) -> None:
        fid = _insert_file(db, "src/utils.py")
        _insert_symbol(db, fid, "_helper", kind="function", is_exported=False)
        out = CodemapGenerator(db).generate()
        assert "*(private)*" in out

    def test_exported_symbol_not_marked_private(self, db: IndexDatabase) -> None:
        fid = _insert_file(db, "src/utils.py")
        _insert_symbol(db, fid, "public_func", kind="function", is_exported=True)
        out = CodemapGenerator(db).generate()
        assert "*(private)*" not in out

    def test_no_symbols_placeholder(self, db: IndexDatabase) -> None:
        _insert_file(db, "src/empty.py")
        out = CodemapGenerator(db).generate()
        assert "*(no symbols)*" in out

    def test_symbols_sorted_by_line_number(self, db: IndexDatabase) -> None:
        fid = _insert_file(db, "src/utils.py")
        _insert_symbol(db, fid, "later_func", kind="function", line_start=20)
        _insert_symbol(db, fid, "early_func", kind="function", line_start=5)
        out = CodemapGenerator(db).generate()
        assert out.index("early_func") < out.index("later_func")

    def test_multiple_classes_with_methods(self, db: IndexDatabase) -> None:
        fid = _insert_file(db, "src/handlers.py")
        _insert_symbol(db, fid, "BaseHandler", kind="class", line_start=1)
        _insert_symbol(db, fid, "handle", kind="method", line_start=2, parent_name="BaseHandler")
        _insert_symbol(db, fid, "SpecialHandler", kind="class", line_start=10)
        _insert_symbol(db, fid, "handle", kind="method", line_start=11, parent_name="SpecialHandler")
        out = CodemapGenerator(db).generate()
        assert "BaseHandler" in out
        assert "SpecialHandler" in out
        # Both classes have "handle" methods indented
        assert out.count("  - `handle` method") == 2


# ── write() ───────────────────────────────────────────────────────────────────


class TestWrite:
    def test_creates_file(self, tmp_path: Path, gen: CodemapGenerator) -> None:
        out = tmp_path / "CODEMAPS.md"
        gen.write(out)
        assert out.exists()

    def test_creates_parent_dirs(self, tmp_path: Path, gen: CodemapGenerator) -> None:
        out = tmp_path / "docs" / "deep" / "CODEMAPS.md"
        gen.write(out)
        assert out.exists()

    def test_file_contains_title(self, tmp_path: Path, gen: CodemapGenerator) -> None:
        out = tmp_path / "CODEMAPS.md"
        gen.write(out)
        content = out.read_text(encoding="utf-8")
        assert "# Project Codemap" in content


# ── Integration: real project ─────────────────────────────────────────────────


class TestIntegration:
    def test_full_project_codemap(self, tmp_path: Path, db: IndexDatabase) -> None:
        """Index a real fake project and verify the codemap is coherent."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass\n", encoding="utf-8")
        (src / "utils.py").write_text(
            "def helper(): pass\nHELPER_CONST = 1\n", encoding="utf-8"
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text(
            "def test_ok(): pass\n", encoding="utf-8"
        )

        indexer = ProjectIndexer(project_dir=tmp_path, db=db)
        indexer.run_full_index()

        out = CodemapGenerator(db).generate()

        assert "# Project Codemap" in out
        assert "3 files" in out
        # Entry point found
        assert "main.py" in out
        # Utils file in Utilities section
        assert "## Utilities" in out
        assert "utils.py" in out
        # Symbols present
        assert "helper" in out
        assert "HELPER_CONST" in out
        # Test section present
        assert "## Tests" in out
        assert "test_main" in out
