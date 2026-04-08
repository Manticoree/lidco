"""Q329 — Knowledge Updater: keep knowledge graph fresh with incremental updates."""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lidco.knowledge.extractor import ConceptType, KnowledgeExtractor
from lidco.knowledge.graph import (
    Entity,
    EntityType,
    KnowledgeGraph,
    Relationship,
    RelationType,
)

logger = logging.getLogger(__name__)

# Map concept types to entity types
_CONCEPT_TO_ENTITY: dict[ConceptType, EntityType] = {
    ConceptType.DESIGN_PATTERN: EntityType.PATTERN,
    ConceptType.ARCHITECTURE_DECISION: EntityType.CONCEPT,
    ConceptType.BUSINESS_RULE: EntityType.RULE,
    ConceptType.INVARIANT: EntityType.RULE,
    ConceptType.API_ENDPOINT: EntityType.FUNCTION,
    ConceptType.DATA_MODEL: EntityType.CLASS,
    ConceptType.ALGORITHM: EntityType.FUNCTION,
    ConceptType.CONFIGURATION: EntityType.CONCEPT,
}


@dataclass
class FileState:
    """Tracks the state of a file for change detection."""

    path: str
    content_hash: str
    last_updated: float
    entity_ids: list[str] = field(default_factory=list)


@dataclass
class UpdateResult:
    """Result of an incremental update."""

    files_scanned: int = 0
    files_changed: int = 0
    entities_added: int = 0
    entities_removed: int = 0
    entities_updated: int = 0
    conflicts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def total_changes(self) -> int:
        return self.entities_added + self.entities_removed + self.entities_updated


class KnowledgeUpdater:
    """Keeps a KnowledgeGraph synchronized with the codebase."""

    def __init__(
        self,
        graph: KnowledgeGraph,
        extractor: KnowledgeExtractor | None = None,
    ) -> None:
        self._graph = graph
        self._extractor = extractor or KnowledgeExtractor()
        self._file_states: dict[str, FileState] = {}

    @property
    def graph(self) -> KnowledgeGraph:
        return self._graph

    @property
    def tracked_files(self) -> list[str]:
        return list(self._file_states.keys())

    # ------------------------------------------------------------------
    # Change detection
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def has_changed(self, file_path: str, content: str) -> bool:
        """Check if file content differs from last known state."""
        new_hash = self._hash_content(content)
        state = self._file_states.get(file_path)
        if state is None:
            return True
        return state.content_hash != new_hash

    def detect_changes(self, file_paths: list[str]) -> list[str]:
        """Return file paths that have changed since last update."""
        changed: list[str] = []
        for fp in file_paths:
            try:
                with open(fp, encoding="utf-8") as fh:
                    content = fh.read()
                if self.has_changed(fp, content):
                    changed.append(fp)
            except (OSError, UnicodeDecodeError):
                changed.append(fp)  # treat unreadable as changed
        return changed

    # ------------------------------------------------------------------
    # Incremental update
    # ------------------------------------------------------------------

    def update_file(self, file_path: str, content: str | None = None) -> UpdateResult:
        """Update graph for a single file. Reads from disk if content is None."""
        result = UpdateResult(files_scanned=1)

        if content is None:
            try:
                with open(file_path, encoding="utf-8") as fh:
                    content = fh.read()
            except (OSError, UnicodeDecodeError) as exc:
                result.errors.append(f"Cannot read {file_path}: {exc}")
                return result

        new_hash = self._hash_content(content)
        old_state = self._file_states.get(file_path)

        if old_state and old_state.content_hash == new_hash:
            return result  # no change

        result.files_changed = 1

        # Remove old entities for this file
        if old_state:
            for eid in old_state.entity_ids:
                if self._graph.remove_entity(eid):
                    result.entities_removed += 1

        # Extract new concepts
        extraction = self._extractor.extract_from_source(content, file_path)
        result.errors.extend(extraction.errors)

        # Create file entity
        file_entity_id = f"file:{file_path}"
        file_entity = Entity(
            id=file_entity_id,
            name=Path(file_path).name,
            entity_type=EntityType.FILE,
            source_file=file_path,
            description=f"Source file {Path(file_path).name}",
        )
        self._graph.add_entity(file_entity)
        new_entity_ids = [file_entity_id]

        # Add concept entities
        for concept in extraction.concepts:
            entity_id = f"{file_path}:{concept.name}:{concept.line_number}"
            entity_type = _CONCEPT_TO_ENTITY.get(concept.concept_type, EntityType.CONCEPT)
            entity = Entity(
                id=entity_id,
                name=concept.name,
                entity_type=entity_type,
                description=concept.description,
                source_file=file_path,
                line_number=concept.line_number,
                tags=list(concept.tags),
                metadata={"confidence": concept.confidence},
            )

            # Conflict check: same name, different file
            existing = [
                e
                for e in self._graph.all_entities()
                if e.name == concept.name
                and e.id != entity_id
                and e.source_file != file_path
            ]
            if existing:
                result.conflicts.append(
                    f"'{concept.name}' also defined in {existing[0].source_file}"
                )

            self._graph.add_entity(entity)
            new_entity_ids.append(entity_id)
            result.entities_added += 1

            # Add CONTAINS relationship from file to concept
            try:
                self._graph.add_relationship(
                    Relationship(
                        source_id=file_entity_id,
                        target_id=entity_id,
                        relation_type=RelationType.CONTAINS,
                    )
                )
            except KeyError:
                pass

        # Update file state
        self._file_states[file_path] = FileState(
            path=file_path,
            content_hash=new_hash,
            last_updated=time.time(),
            entity_ids=new_entity_ids,
        )

        return result

    def update_files(self, file_paths: list[str]) -> UpdateResult:
        """Update graph for multiple files."""
        combined = UpdateResult()
        for fp in file_paths:
            r = self.update_file(fp)
            combined.files_scanned += r.files_scanned
            combined.files_changed += r.files_changed
            combined.entities_added += r.entities_added
            combined.entities_removed += r.entities_removed
            combined.entities_updated += r.entities_updated
            combined.conflicts.extend(r.conflicts)
            combined.errors.extend(r.errors)
        return combined

    def full_update(self, project_dir: str, extensions: tuple[str, ...] = (".py",)) -> UpdateResult:
        """Scan entire project directory and update graph."""
        root = Path(project_dir)
        files: list[str] = []
        for ext in extensions:
            files.extend(str(p) for p in root.rglob(f"*{ext}"))
        return self.update_files(files)

    # ------------------------------------------------------------------
    # Conflict resolution
    # ------------------------------------------------------------------

    def resolve_conflict(self, entity_id: str, keep: bool = True) -> bool:
        """Resolve a conflict by keeping or removing an entity."""
        if not keep:
            return self._graph.remove_entity(entity_id)
        return entity_id in {e.id for e in self._graph.all_entities()}

    def remove_stale(self, max_age_seconds: float = 86400.0) -> int:
        """Remove entities from files not updated within max_age_seconds."""
        now = time.time()
        removed = 0
        stale_files = [
            fp
            for fp, state in self._file_states.items()
            if now - state.last_updated > max_age_seconds
        ]
        for fp in stale_files:
            state = self._file_states.pop(fp, None)
            if state:
                for eid in state.entity_ids:
                    if self._graph.remove_entity(eid):
                        removed += 1
        return removed
