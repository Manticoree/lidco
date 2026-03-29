"""RulesResolver — match rules files to a list of file paths.

Task 728: Q119.
"""
from __future__ import annotations

import fnmatch

from lidco.rules.rules_loader import RulesFile, RulesFileLoader


class RulesResolver:
    """Resolve which rules apply to a given set of file paths."""

    def __init__(self, loader: RulesFileLoader) -> None:
        self._loader = loader

    def resolve(self, file_paths: list[str]) -> list[RulesFile]:
        """Return rules whose glob_pattern matches at least one path in *file_paths*."""
        rules = self._loader.load_all()
        if not file_paths:
            return []

        matched: list[RulesFile] = []
        for rule in rules:
            pattern = rule.glob_pattern
            for path in file_paths:
                if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path.replace("\\", "/"), pattern):
                    matched.append(rule)
                    break

        return matched

    def resolve_for_file(self, file_path: str) -> list[RulesFile]:
        """Return all rules that match a single file path."""
        return self.resolve([file_path])

    def resolve_text(self, file_paths: list[str], separator: str = "\n\n") -> str:
        """Return concatenated content of all matching rules."""
        matched = self.resolve(file_paths)
        return separator.join(r.content for r in matched)
