"""Breaking change and migration pattern detection — Task 352."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum


class BreakingKind(Enum):
    REMOVED_FUNCTION = "removed_function"
    REMOVED_CLASS = "removed_class"
    SIGNATURE_CHANGED = "signature_changed"
    RENAMED_SYMBOL = "renamed_symbol"
    REMOVED_PARAM = "removed_param"
    ADDED_REQUIRED_PARAM = "added_required_param"


@dataclass(frozen=True)
class BreakingChange:
    kind: BreakingKind
    symbol: str
    detail: str
    file: str = ""
    line: int = 0


@dataclass
class MigrationReport:
    breaking_changes: list[BreakingChange] = field(default_factory=list)
    deprecations: list[str] = field(default_factory=list)

    @property
    def has_breaking_changes(self) -> bool:
        return len(self.breaking_changes) > 0

    def by_kind(self, kind: BreakingKind) -> list[BreakingChange]:
        return [c for c in self.breaking_changes if c.kind == kind]


def _extract_public_api(source: str) -> dict[str, dict]:
    """Extract public functions/classes with their signatures."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    api: dict[str, dict] = {}

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                params = _get_param_names(node.args)
                required = _get_required_params(node.args)
                api[node.name] = {
                    "kind": "function",
                    "params": params,
                    "required": required,
                    "line": node.lineno,
                }
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                api[node.name] = {"kind": "class", "line": node.lineno}

    return api


def _get_param_names(args: ast.arguments) -> list[str]:
    all_args = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
    names = [a.arg for a in all_args if a.arg not in ("self", "cls")]
    if args.vararg:
        names.append(f"*{args.vararg.arg}")
    if args.kwarg:
        names.append(f"**{args.kwarg.arg}")
    return names


def _get_required_params(args: ast.arguments) -> set[str]:
    """Return params with no default value (required)."""
    all_args = list(args.posonlyargs) + list(args.args)
    n_defaults = len(args.defaults)
    n_required = len(all_args) - n_defaults
    required = {a.arg for a in all_args[:n_required] if a.arg not in ("self", "cls")}

    # kwonly without defaults are also required
    for i, arg in enumerate(args.kwonlyargs):
        if args.kw_defaults[i] is None:
            required.add(arg.arg)

    return required


class MigrationDetector:
    """Detect breaking API changes between two versions of a module."""

    def compare(
        self,
        old_source: str,
        new_source: str,
        file_path: str = "",
    ) -> MigrationReport:
        """Compare old and new source, returning breaking changes."""
        old_api = _extract_public_api(old_source)
        new_api = _extract_public_api(new_source)
        report = MigrationReport()

        # Removed symbols
        for name, info in old_api.items():
            if name not in new_api:
                kind = (
                    BreakingKind.REMOVED_FUNCTION
                    if info["kind"] == "function"
                    else BreakingKind.REMOVED_CLASS
                )
                report.breaking_changes.append(
                    BreakingChange(
                        kind=kind,
                        symbol=name,
                        detail=f"{info['kind']} '{name}' was removed",
                        file=file_path,
                        line=info.get("line", 0),
                    )
                )

        # Changed signatures
        for name, old_info in old_api.items():
            if name not in new_api:
                continue
            new_info = new_api[name]
            if old_info["kind"] != "function" or new_info["kind"] != "function":
                continue

            old_params = set(old_info["params"])
            new_params = set(new_info["params"])
            old_required = old_info["required"]
            new_required = new_info["required"]

            # Removed params
            removed = old_params - new_params
            for p in removed:
                report.breaking_changes.append(
                    BreakingChange(
                        kind=BreakingKind.REMOVED_PARAM,
                        symbol=name,
                        detail=f"Parameter '{p}' removed from '{name}'",
                        file=file_path,
                        line=new_info.get("line", 0),
                    )
                )

            # Added required params
            added_required = new_required - old_required - old_params
            for p in sorted(added_required):
                report.breaking_changes.append(
                    BreakingChange(
                        kind=BreakingKind.ADDED_REQUIRED_PARAM,
                        symbol=name,
                        detail=f"New required parameter '{p}' added to '{name}'",
                        file=file_path,
                        line=new_info.get("line", 0),
                    )
                )

        # Detect deprecation comments
        for line in new_source.splitlines():
            stripped = line.strip().lower()
            if "deprecated" in stripped or "will be removed" in stripped:
                report.deprecations.append(line.strip())

        return report
