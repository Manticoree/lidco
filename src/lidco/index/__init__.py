"""Project index module — SQLite-backed structural analysis of user projects."""

from lidco.index.codemap_generator import CodemapGenerator
from lidco.index.context_enricher import IndexContextEnricher
from lidco.index.db import IndexDatabase
from lidco.index.schema import FileRecord, ImportRecord, IndexStats, SymbolRecord

__all__ = [
    "CodemapGenerator",
    "IndexContextEnricher",
    "IndexDatabase",
    "FileRecord",
    "ImportRecord",
    "IndexStats",
    "SymbolRecord",
]
