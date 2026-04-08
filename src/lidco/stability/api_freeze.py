"""
Q345 — API Contract Stability: Public API Freeze Checker.

Detects breaking changes between API versions, tracks function signatures,
validates deprecations, and enforces correct semver bumps.
"""
from __future__ import annotations

import ast
import re
from typing import Any


class PublicApiFreezeChecker:
    """Check for breaking changes in public Python APIs."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # detect_breaking_changes
    # ------------------------------------------------------------------

    def detect_breaking_changes(
        self, old_api: dict, new_api: dict
    ) -> list[dict]:
        """Detect breaking changes between two API snapshots.

        Each API dict has a ``"functions"`` key containing a list of dicts:
        ``{"name": str, "params": list[str], "return_type": str}``.

        Returns a list of change dicts with keys:
        ``"function"``, ``"change_type"``, ``"severity"``, ``"description"``.
        """
        old_funcs: dict[str, dict] = {
            f["name"]: f for f in old_api.get("functions", [])
        }
        new_funcs: dict[str, dict] = {
            f["name"]: f for f in new_api.get("functions", [])
        }

        changes: list[dict] = []

        # Removed functions — always BREAKING
        for name, old_f in old_funcs.items():
            if name not in new_funcs:
                changes.append(
                    {
                        "function": name,
                        "change_type": "removed",
                        "severity": "BREAKING",
                        "description": f"Function '{name}' was removed from the public API.",
                    }
                )
                continue

            new_f = new_funcs[name]
            old_params: list[str] = old_f.get("params", [])
            new_params: list[str] = new_f.get("params", [])

            old_param_set = set(old_params)
            new_param_set = set(new_params)

            # Removed parameters — BREAKING
            for p in old_params:
                if p not in new_param_set:
                    changes.append(
                        {
                            "function": name,
                            "change_type": "param_removed",
                            "severity": "BREAKING",
                            "description": (
                                f"Parameter '{p}' was removed from '{name}'."
                            ),
                        }
                    )

            # Added required parameters — BREAKING (heuristic: no default marker)
            for p in new_params:
                if p not in old_param_set and not p.startswith("*"):
                    # Treat newly added non-variadic params as required
                    changes.append(
                        {
                            "function": name,
                            "change_type": "param_added_required",
                            "severity": "BREAKING",
                            "description": (
                                f"Required parameter '{p}' was added to '{name}'."
                            ),
                        }
                    )

            # Return type changed — WARNING
            old_ret = old_f.get("return_type", "")
            new_ret = new_f.get("return_type", "")
            if old_ret != new_ret:
                changes.append(
                    {
                        "function": name,
                        "change_type": "return_type_changed",
                        "severity": "WARNING",
                        "description": (
                            f"Return type of '{name}' changed from "
                            f"'{old_ret}' to '{new_ret}'."
                        ),
                    }
                )

        return changes

    # ------------------------------------------------------------------
    # track_signatures
    # ------------------------------------------------------------------

    def track_signatures(self, source_code: str) -> list[dict]:
        """Extract public function/method signatures from Python source code.

        Returns a list of dicts with ``"name"``, ``"params"``,
        ``"return_type"``, ``"line"``.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return []

        signatures: list[dict] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            # Skip private functions (single or double leading underscore)
            if node.name.startswith("_"):
                continue

            params = self._extract_params(node)
            return_type = self._extract_return_type(node)

            signatures.append(
                {
                    "name": node.name,
                    "params": params,
                    "return_type": return_type,
                    "line": node.lineno,
                }
            )

        return signatures

    def _extract_params(self, node: ast.FunctionDef) -> list[str]:
        args = node.args
        params: list[str] = []
        for arg in args.args:
            if arg.arg == "self" or arg.arg == "cls":
                continue
            params.append(arg.arg)
        if args.vararg:
            params.append(f"*{args.vararg.arg}")
        for arg in args.kwonlyargs:
            params.append(arg.arg)
        if args.kwarg:
            params.append(f"**{args.kwarg.arg}")
        return params

    def _extract_return_type(self, node: ast.FunctionDef) -> str:
        if node.returns is None:
            return ""
        try:
            return ast.unparse(node.returns)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # check_deprecations
    # ------------------------------------------------------------------

    def check_deprecations(self, source_code: str) -> list[dict]:
        """Find deprecated functions and verify they emit deprecation warnings.

        Returns a list of dicts with ``"line"``, ``"function"``,
        ``"has_warning"`` (bool), ``"suggestion"``.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return []

        results: list[dict] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Detect @deprecated decorator or "deprecated" in docstring
            is_deprecated = self._is_deprecated(node)
            if not is_deprecated:
                continue

            has_warning = self._has_deprecation_warning(node, source_code)

            suggestion = (
                "Function is deprecated and properly warns callers."
                if has_warning
                else (
                    f"Add 'warnings.warn(\"{node.name} is deprecated\", "
                    "DeprecationWarning, stacklevel=2)' inside the function body."
                )
            )

            results.append(
                {
                    "line": node.lineno,
                    "function": node.name,
                    "has_warning": has_warning,
                    "suggestion": suggestion,
                }
            )

        return results

    def _is_deprecated(self, node: ast.FunctionDef) -> bool:
        # Check decorators for @deprecated
        for dec in node.decorator_list:
            dec_src = ast.unparse(dec) if hasattr(ast, "unparse") else ""
            if "deprecated" in dec_src.lower():
                return True

        # Check docstring for "deprecated" keyword
        docstring = ast.get_docstring(node) or ""
        if "deprecated" in docstring.lower():
            return True

        return False

    def _has_deprecation_warning(
        self, node: ast.FunctionDef, _source_code: str
    ) -> bool:
        """Return True if the function body contains a warnings.warn call."""
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            # warnings.warn(...)
            if isinstance(func, ast.Attribute) and func.attr == "warn":
                return True
            # warn(...) if directly imported
            if isinstance(func, ast.Name) and func.id == "warn":
                return True
        return False

    # ------------------------------------------------------------------
    # validate_semver
    # ------------------------------------------------------------------

    def validate_semver(
        self,
        old_version: str,
        new_version: str,
        has_breaking: bool,
    ) -> dict:
        """Validate that the semver bump matches the nature of the changes.

        Returns a dict with ``"valid"``, ``"old"``, ``"new"``,
        ``"expected_bump"``, ``"actual_bump"``, ``"suggestion"``.
        """
        old_parts = self._parse_version(old_version)
        new_parts = self._parse_version(new_version)

        actual_bump = self._classify_bump(old_parts, new_parts)
        expected_bump = "major" if has_breaking else "minor"

        valid = (actual_bump == expected_bump) or (
            actual_bump == "major" and not has_breaking
        )

        if actual_bump == "major" and not has_breaking:
            # major bump without breaking changes is allowed but over-cautious
            valid = True

        if actual_bump == "minor" and has_breaking:
            valid = False

        if actual_bump == "patch" and has_breaking:
            valid = False

        if actual_bump == "patch" and not has_breaking:
            # patch for no breaking changes is acceptable if no new features
            # For simplicity treat this as valid
            valid = True
            expected_bump = "patch"

        suggestion = self._build_suggestion(
            old_parts, has_breaking, actual_bump, valid
        )

        return {
            "valid": valid,
            "old": old_version,
            "new": new_version,
            "expected_bump": expected_bump,
            "actual_bump": actual_bump,
            "suggestion": suggestion,
        }

    def _parse_version(self, version: str) -> tuple[int, int, int]:
        version = version.lstrip("v")
        parts = version.split(".")
        try:
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2].split("-")[0]) if len(parts) > 2 else 0
        except ValueError:
            major, minor, patch = 0, 0, 0
        return major, minor, patch

    def _classify_bump(
        self,
        old: tuple[int, int, int],
        new: tuple[int, int, int],
    ) -> str:
        if new[0] > old[0]:
            return "major"
        if new[1] > old[1]:
            return "minor"
        if new[2] > old[2]:
            return "patch"
        return "none"

    def _build_suggestion(
        self,
        old_parts: tuple[int, int, int],
        has_breaking: bool,
        actual_bump: str,
        valid: bool,
    ) -> str:
        if valid:
            return "Version bump looks correct."
        if has_breaking and actual_bump in ("minor", "patch"):
            suggested = f"{old_parts[0] + 1}.0.0"
            return (
                f"Breaking changes require a major version bump. "
                f"Consider bumping to {suggested}."
            )
        return "Review version bump strategy."
