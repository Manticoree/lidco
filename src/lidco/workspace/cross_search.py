"""Cross-repo / cross-package text search."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """A single search hit."""

    repo: str
    file: str
    line: int
    match: str


class CrossRepoSearch:
    """Search across multiple repos/packages for a text pattern."""

    _default_ignore: list[str] = [
        "*.pyc",
        "__pycache__/*",
        ".git/*",
        "node_modules/*",
        "*.egg-info/*",
    ]

    def search(
        self,
        query: str,
        repos: list[str],
        ignore_patterns: list[str] | None = None,
    ) -> list[SearchResult]:
        """Search *query* (substring) in every file under each repo path."""
        if not query:
            return []

        ignore = ignore_patterns if ignore_patterns is not None else self._default_ignore
        results: list[SearchResult] = []

        for repo_path in repos:
            repo_path = os.path.abspath(repo_path)
            repo_name = os.path.basename(repo_path)
            if not os.path.isdir(repo_path):
                continue
            self._search_dir(repo_path, repo_name, query, ignore, results)

        return results

    # -- internal helpers ----------------------------------------------------

    def _search_dir(
        self,
        base: str,
        repo_name: str,
        query: str,
        ignore: list[str],
        results: list[SearchResult],
    ) -> None:
        for dirpath, dirnames, filenames in os.walk(base):
            # prune ignored directories
            dirnames[:] = [
                d
                for d in dirnames
                if not self._is_ignored(os.path.relpath(os.path.join(dirpath, d), base), ignore)
            ]
            for fname in sorted(filenames):
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, base)
                if self._is_ignored(rel, ignore):
                    continue
                self._search_file(full, rel, repo_name, query, results)

    @staticmethod
    def _is_ignored(rel_path: str, patterns: list[str]) -> bool:
        rel_path = rel_path.replace("\\", "/")
        for pat in patterns:
            if fnmatch.fnmatch(rel_path, pat):
                return True
            # also match just the basename
            if fnmatch.fnmatch(os.path.basename(rel_path), pat):
                return True
        return False

    @staticmethod
    def _search_file(
        full_path: str,
        rel_path: str,
        repo_name: str,
        query: str,
        results: list[SearchResult],
    ) -> None:
        try:
            with open(full_path, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if query in line:
                        results.append(
                            SearchResult(
                                repo=repo_name,
                                file=rel_path,
                                line=lineno,
                                match=line.rstrip("\n\r"),
                            )
                        )
        except (OSError, UnicodeDecodeError):
            pass
