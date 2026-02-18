"""SQLite schema DDL and immutable dataclass models for the project index."""

from __future__ import annotations

from dataclasses import dataclass


# ── DDL ───────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    path        TEXT    NOT NULL UNIQUE,
    language    TEXT    NOT NULL DEFAULT 'unknown',
    role        TEXT    NOT NULL DEFAULT 'unknown',
    size_bytes  INTEGER NOT NULL DEFAULT 0,
    mtime       REAL    NOT NULL,
    lines_count INTEGER NOT NULL DEFAULT 0,
    indexed_at  REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime);
CREATE INDEX IF NOT EXISTS idx_files_role  ON files(role);
CREATE INDEX IF NOT EXISTS idx_files_lang  ON files(language);

CREATE TABLE IF NOT EXISTS symbols (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    kind        TEXT    NOT NULL,
    line_start  INTEGER NOT NULL,
    line_end    INTEGER NOT NULL DEFAULT 0,
    is_exported INTEGER NOT NULL DEFAULT 0,
    parent_name TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);

CREATE TABLE IF NOT EXISTS imports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    imported_module TEXT    NOT NULL,
    resolved_path   TEXT    NOT NULL DEFAULT '',
    import_kind     TEXT    NOT NULL DEFAULT 'module'
);

CREATE INDEX IF NOT EXISTS idx_imports_from     ON imports(from_file_id);
CREATE INDEX IF NOT EXISTS idx_imports_resolved ON imports(resolved_path);
"""

# Valid values for FileRecord.role
FILE_ROLES = frozenset({
    "entrypoint",
    "config",
    "test",
    "model",
    "router",
    "utility",
    "unknown",
})

# Valid values for SymbolRecord.kind
SYMBOL_KINDS = frozenset({
    "function",
    "class",
    "method",
    "variable",
    "constant",
})

# Valid values for ImportRecord.import_kind
IMPORT_KINDS = frozenset({
    "module",
    "from",
    "dynamic",
    "require",
})


# ── Dataclass models ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FileRecord:
    """Immutable representation of an indexed file."""

    path: str           # relative path from project root
    language: str
    role: str
    size_bytes: int
    mtime: float        # Unix timestamp
    lines_count: int
    indexed_at: float   # Unix timestamp
    id: int = 0         # 0 = not yet persisted


@dataclass(frozen=True)
class SymbolRecord:
    """Immutable representation of a code symbol (function, class, etc.)."""

    file_id: int
    name: str
    kind: str           # see SYMBOL_KINDS
    line_start: int
    line_end: int = 0
    is_exported: bool = False
    parent_name: str = ""
    id: int = 0


@dataclass(frozen=True)
class ImportRecord:
    """Immutable representation of an import statement."""

    from_file_id: int
    imported_module: str
    resolved_path: str = ""
    import_kind: str = "module"  # see IMPORT_KINDS
    id: int = 0


@dataclass(frozen=True)
class IndexStats:
    """Snapshot statistics of the project index."""

    total_files: int
    total_symbols: int
    total_imports: int
    last_indexed_at: float | None   # Unix timestamp, None if never indexed
    files_by_role: dict[str, int]
    files_by_language: dict[str, int]
