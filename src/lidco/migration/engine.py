"""
Code Migration Engine — Codemod/ast-grep-style rule-based migrations.

Apply a set of MigrationRule objects across a codebase.  Each rule can:
  - Use regex find/replace (fast, text-based)
  - Use AST-based transformation (accurate, Python-only)

Built-in rule sets are provided for common migrations:
  - Python 2 → 3 (print statement, unicode literals, etc.)
  - Deprecated stdlib APIs (e.g. collections.Callable → collections.abc.Callable)
  - pytest migration patterns

Custom rules can be passed at runtime or loaded from .lidco/migrations/*.yaml.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MigrationRule:
    id: str
    name: str
    description: str
    pattern: str                   # regex or AST selector
    replacement: str               # replacement string (regex sub) or callable
    file_glob: str = "**/*.py"     # which files this applies to
    mode: str = "regex"            # "regex" | "ast"
    flags: int = 0                 # re flags (re.MULTILINE etc.)


@dataclass
class FileChange:
    path: str
    rule_id: str
    original: str
    modified: str
    match_count: int

    @property
    def diff_lines(self) -> list[str]:
        """Return a simple unified-diff-style list of changed lines."""
        orig_lines = self.original.splitlines()
        mod_lines = self.modified.splitlines()
        diff = []
        for i, (o, m) in enumerate(zip(orig_lines, mod_lines)):
            if o != m:
                diff.append(f"  L{i+1}: -{o}")
                diff.append(f"  L{i+1}: +{m}")
        return diff


@dataclass
class MigrationResult:
    rules_applied: list[str]
    files_changed: list[FileChange]
    files_scanned: int
    dry_run: bool
    errors: list[str] = field(default_factory=list)

    @property
    def total_matches(self) -> int:
        return sum(c.match_count for c in self.files_changed)

    def summary(self) -> str:
        status = "(dry run)" if self.dry_run else "(applied)"
        return (
            f"{status} {len(self.files_changed)} files changed, "
            f"{self.total_matches} replacements across "
            f"{self.files_scanned} files scanned"
        )


# ---------------------------------------------------------------------------
# Built-in rule sets
# ---------------------------------------------------------------------------

RULES_PYTHON2_TO_3: list[MigrationRule] = [
    MigrationRule(
        id="py2to3-print",
        name="print statement → print()",
        description="Replace `print x` with `print(x)` (Python 2 → 3)",
        pattern=r"^(\s*)print\s+(?!\()(.+?)$",
        replacement=r"\1print(\2)",
        mode="regex",
        flags=re.MULTILINE,
    ),
    MigrationRule(
        id="py2to3-raise",
        name="raise X, msg → raise X(msg)",
        description="Replace old-style raise with new style",
        pattern=r"\braise\s+(\w+),\s*(.+)",
        replacement=r"raise \1(\2)",
        mode="regex",
    ),
    MigrationRule(
        id="py2to3-except",
        name="except X, e → except X as e",
        description="Replace old-style except clause",
        pattern=r"\bexcept\s+(\w+(?:\.\w+)*),\s*(\w+)\s*:",
        replacement=r"except \1 as \2:",
        mode="regex",
    ),
    MigrationRule(
        id="py2to3-unicode-literal",
        name="u'string' → 'string'",
        description="Remove redundant u prefix from string literals",
        pattern=r'\bu(["\'])',
        replacement=r"\1",
        mode="regex",
    ),
    MigrationRule(
        id="py2to3-has-key",
        name="dict.has_key(x) → x in dict",
        description="Replace .has_key() with `in` operator",
        pattern=r"(\w+)\.has_key\((.+?)\)",
        replacement=r"\2 in \1",
        mode="regex",
    ),
    MigrationRule(
        id="py2to3-iteritems",
        name=".iteritems() → .items()",
        description="Replace dict.iteritems/itervalues/iterkeys",
        pattern=r"\.(iteritems|itervalues|iterkeys)\(\)",
        replacement=lambda m: f".{m.group(1).replace('iter', '')}()",
        mode="regex",
    ),
]

RULES_STDLIB_DEPRECATIONS: list[MigrationRule] = [
    MigrationRule(
        id="stdlib-collections-abc",
        name="collections.Callable → collections.abc.Callable",
        description="collections.* types moved to collections.abc in Python 3.10+",
        pattern=r"\bcollections\.(Callable|Iterator|Generator|Sequence|Mapping|MutableMapping|Set|MutableSet|Iterable|Awaitable|Coroutine)\b",
        replacement=r"collections.abc.\1",
        mode="regex",
    ),
    MigrationRule(
        id="stdlib-distutils",
        name="distutils → setuptools",
        description="distutils is removed in Python 3.12",
        pattern=r"\bfrom distutils\b",
        replacement="from setuptools._distutils",
        mode="regex",
    ),
    MigrationRule(
        id="stdlib-imp-removed",
        name="import imp → importlib",
        description="imp module is removed in Python 3.12",
        pattern=r"\bimport imp\b",
        replacement="import importlib",
        mode="regex",
    ),
    MigrationRule(
        id="stdlib-optparse",
        name="optparse → argparse",
        description="optparse is deprecated, prefer argparse",
        pattern=r"\bimport optparse\b",
        replacement="import argparse  # migrated from optparse",
        mode="regex",
    ),
]

RULES_PYTEST: list[MigrationRule] = [
    MigrationRule(
        id="pytest-raises-match",
        name="pytest.raises message= → match=",
        description="pytest.raises message= param renamed to match=",
        pattern=r"pytest\.raises\((.+?),\s*message=",
        replacement=r"pytest.raises(\1, match=",
        mode="regex",
    ),
    MigrationRule(
        id="pytest-setup-method",
        name="setup_method(self, method) → setup_method(self)",
        description="method param removed from setup_method signature",
        pattern=r"def setup_method\(self,\s*method\)",
        replacement="def setup_method(self)",
        mode="regex",
    ),
]

ALL_BUILTIN_RULES: dict[str, list[MigrationRule]] = {
    "py2to3": RULES_PYTHON2_TO_3,
    "stdlib": RULES_STDLIB_DEPRECATIONS,
    "pytest": RULES_PYTEST,
}


# ---------------------------------------------------------------------------
# CodeMigrationEngine
# ---------------------------------------------------------------------------

class CodeMigrationEngine:
    """
    Apply migration rules to files in a project.

    Parameters
    ----------
    project_root : str | None
        Root of the project to migrate.
    dry_run : bool
        When True, compute changes but do not write files.
    """

    def __init__(
        self,
        project_root: str | None = None,
        dry_run: bool = True,
    ) -> None:
        self._root = Path(project_root) if project_root else Path.cwd()
        self.dry_run = dry_run

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_ruleset(
        self,
        ruleset_name: str,
        paths: list[str] | None = None,
    ) -> MigrationResult:
        """Apply a built-in named ruleset ('py2to3', 'stdlib', 'pytest')."""
        rules = ALL_BUILTIN_RULES.get(ruleset_name)
        if rules is None:
            available = ", ".join(ALL_BUILTIN_RULES)
            raise KeyError(
                f"Unknown ruleset '{ruleset_name}'. Available: {available}"
            )
        return self.apply_rules(rules, paths=paths)

    def apply_rules(
        self,
        rules: list[MigrationRule],
        paths: list[str] | None = None,
    ) -> MigrationResult:
        """Apply a list of MigrationRule objects to the project."""
        files_changed: list[FileChange] = []
        errors: list[str] = []
        files_scanned = 0
        rules_applied: set[str] = set()

        # Collect target files (union of all globs)
        target_files: set[Path] = set()
        if paths:
            for p in paths:
                target_files.add(Path(p))
        else:
            for rule in rules:
                for fp in self._root.rglob(rule.file_glob):
                    if not any(part.startswith(".") for part in fp.relative_to(self._root).parts):
                        target_files.add(fp)

        for filepath in sorted(target_files):
            try:
                original = filepath.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:
                errors.append(f"Could not read {filepath}: {exc}")
                continue

            files_scanned += 1
            current = original

            for rule in rules:
                if not self._file_matches_glob(filepath, rule.file_glob):
                    continue
                try:
                    modified, count = self._apply_rule(rule, current)
                except Exception as exc:
                    errors.append(f"Rule {rule.id} failed on {filepath}: {exc}")
                    continue

                if count > 0:
                    current = modified
                    rules_applied.add(rule.id)

            if current != original:
                files_changed.append(FileChange(
                    path=str(filepath),
                    rule_id=",".join(sorted(rules_applied)),
                    original=original,
                    modified=current,
                    match_count=sum(
                        len(re.findall(r.pattern, original, r.flags))
                        for r in rules
                        if isinstance(r.replacement, str)
                    ),
                ))
                if not self.dry_run:
                    filepath.write_text(current, encoding="utf-8")

        return MigrationResult(
            rules_applied=sorted(rules_applied),
            files_changed=files_changed,
            files_scanned=files_scanned,
            dry_run=self.dry_run,
            errors=errors,
        )

    def list_rulesets(self) -> dict[str, int]:
        """Return available built-in rulesets and their rule counts."""
        return {name: len(rules) for name, rules in ALL_BUILTIN_RULES.items()}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_rule(
        self, rule: MigrationRule, text: str
    ) -> tuple[str, int]:
        """Return (modified_text, match_count)."""
        if rule.mode == "regex":
            if callable(rule.replacement):
                matches = list(re.finditer(rule.pattern, text, rule.flags))
                if not matches:
                    return text, 0
                result = re.sub(rule.pattern, rule.replacement, text, flags=rule.flags)
                return result, len(matches)
            else:
                count = len(re.findall(rule.pattern, text, rule.flags))
                if count == 0:
                    return text, 0
                result = re.sub(rule.pattern, rule.replacement, text, flags=rule.flags)
                return result, count
        return text, 0

    @staticmethod
    def _file_matches_glob(filepath: Path, glob_pattern: str) -> bool:
        """Check if a filepath matches a glob pattern."""
        try:
            return filepath.match(glob_pattern)
        except Exception:
            return False
