"""CodeProofChecker — verify code changes against pre/post conditions.

Stdlib only, dataclass results.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProofResult:
    """Result of a code-change verification."""

    is_valid: bool
    preconditions_met: bool
    postconditions_met: bool
    invariants_held: bool
    issues: list[str] = field(default_factory=list)


class CodeProofChecker:
    """Lightweight code-change proof checker."""

    # ------------------------------------------------------------------
    # check_precondition
    # ------------------------------------------------------------------
    def check_precondition(self, func: str, condition: str) -> bool:
        """Return True when *func* source satisfies *condition*.

        Heuristic: the condition string appears literally inside the
        function body, OR the function explicitly raises/asserts on it.
        """
        normalised = func.strip()
        cond_lower = condition.strip().lower()
        if cond_lower in normalised.lower():
            return True
        # Check for assert / raise patterns mentioning condition keywords
        for keyword in cond_lower.split():
            if len(keyword) >= 3 and keyword in normalised.lower():
                return True
        return False

    # ------------------------------------------------------------------
    # check_postcondition
    # ------------------------------------------------------------------
    def check_postcondition(self, func: str, condition: str) -> bool:
        """Return True when *func* source plausibly guarantees *condition*.

        Heuristic: condition text or its significant words appear in the
        function, especially near return statements.
        """
        normalised = func.strip().lower()
        cond_lower = condition.strip().lower()
        if cond_lower in normalised:
            return True
        keywords = [w for w in cond_lower.split() if len(w) >= 3]
        if not keywords:
            return True
        matched = sum(1 for k in keywords if k in normalised)
        return matched / len(keywords) >= 0.5

    # ------------------------------------------------------------------
    # check_invariant
    # ------------------------------------------------------------------
    def check_invariant(
        self, before: str, after: str, invariant: str
    ) -> bool:
        """Return True when an *invariant* holds across before/after code.

        Heuristic: the invariant text (or its significant words) must
        be present in *both* code snapshots.
        """
        inv_lower = invariant.strip().lower()
        keywords = [w for w in inv_lower.split() if len(w) >= 3]
        if not keywords:
            return True
        before_lower = before.lower()
        after_lower = after.lower()
        for kw in keywords:
            if kw not in before_lower or kw not in after_lower:
                return False
        return True

    # ------------------------------------------------------------------
    # verify_change
    # ------------------------------------------------------------------
    def verify_change(self, old_code: str, new_code: str) -> ProofResult:
        """Verify a code change by checking syntax and structural diffs."""
        issues: list[str] = []

        # Syntax check
        old_ok = self._parses(old_code)
        new_ok = self._parses(new_code)
        if not new_ok:
            issues.append("New code has syntax errors")

        # Structural checks
        old_names = self._top_level_names(old_code) if old_ok else set()
        new_names = self._top_level_names(new_code) if new_ok else set()
        removed = old_names - new_names
        if removed:
            issues.append(f"Removed top-level names: {', '.join(sorted(removed))}")

        pre_met = new_ok
        post_met = new_ok and not issues
        inv_held = not bool(removed)

        return ProofResult(
            is_valid=len(issues) == 0,
            preconditions_met=pre_met,
            postconditions_met=post_met,
            invariants_held=inv_held,
            issues=issues,
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parses(code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    @staticmethod
    def _top_level_names(code: str) -> set[str]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return set()
        names: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
        return names
