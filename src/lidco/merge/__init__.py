"""Merge tools — three-way merge, conflict resolution, diff stats, patch generation."""

from lidco.merge.detector import ConflictDetector
from lidco.merge.resolver import ConflictResolver
from lidco.merge.strategy import MergeStrategy
from lidco.merge.verifier import PostMergeVerifier

__all__ = [
    "ConflictDetector",
    "ConflictResolver",
    "MergeStrategy",
    "PostMergeVerifier",
]
