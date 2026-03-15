"""Variable usage tracking — Task 357."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum


class VariableIssueKind(Enum):
    UNUSED_VARIABLE = "unused_variable"
    SHADOWED_VARIABLE = "shadowed_variable"
    GLOBAL_MISUSE = "global_misuse"       # global declared but var is read-only


@dataclass(frozen=True)
class VariableIssue:
    kind: VariableIssueKind
    name: str
    file: str
    line: int
    detail: str


@dataclass
class VariableReport:
    issues: list[VariableIssue] = field(default_factory=list)
    variables_tracked: int = 0

    def by_kind(self, kind: VariableIssueKind) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind == kind]


class _ScopeVisitor(ast.NodeVisitor):
    """Walk a function body tracking Store/Load/Del for each name."""

    def __init__(self, file_path: str, report: VariableReport) -> None:
        self._file = file_path
        self._report = report
        # Stack of scopes: each scope is {name: {"stores": [lineno...], "loads": int}}
        self._scopes: list[dict[str, dict]] = []

    # ------------------------------------------------------------------ scopes
    def _push(self) -> None:
        self._scopes.append({})

    def _pop(self) -> None:
        scope = self._scopes.pop()
        self._check_scope(scope)

    def _record_store(self, name: str, lineno: int) -> None:
        if not self._scopes:
            return
        scope = self._scopes[-1]
        if name not in scope:
            scope[name] = {"stores": [], "loads": 0, "first_line": lineno}
        scope[name]["stores"].append(lineno)

    def _record_load(self, name: str) -> None:
        # Walk outward to find owning scope
        for scope in reversed(self._scopes):
            if name in scope:
                scope[name]["loads"] += 1
                return

    def _check_scope(self, scope: dict) -> None:
        for name, info in scope.items():
            if name.startswith("_") or name == "self" or name == "cls":
                continue
            # Unused: assigned but never loaded
            if info["stores"] and info["loads"] == 0:
                first = info["stores"][0]
                self._report.variables_tracked += 1
                self._report.issues.append(VariableIssue(
                    kind=VariableIssueKind.UNUSED_VARIABLE,
                    name=name,
                    file=self._file,
                    line=first,
                    detail=f"Variable '{name}' assigned but never used",
                ))
            # Shadowing: more than one store site across different lines
            elif len(info["stores"]) > 1 and info["loads"] > 0:
                self._report.variables_tracked += 1
                self._report.issues.append(VariableIssue(
                    kind=VariableIssueKind.SHADOWED_VARIABLE,
                    name=name,
                    file=self._file,
                    line=info["stores"][-1],
                    detail=f"Variable '{name}' re-assigned (possible shadowing)",
                ))
            elif info["stores"]:
                self._report.variables_tracked += 1

    # ------------------------------------------------------------------ visits
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._push()
        # Args are stores
        for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
            self._record_store(arg.arg, node.lineno)
        if node.args.vararg:
            self._record_store(node.args.vararg.arg, node.lineno)
        if node.args.kwarg:
            self._record_store(node.args.kwarg.arg, node.lineno)
        self.generic_visit(node)
        self._pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self._record_store(node.id, node.lineno)
        elif isinstance(node.ctx, ast.Load):
            self._record_load(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        # Flag global declarations in functions — misuse if only read
        if self._scopes:
            for name in node.names:
                self._report.issues.append(VariableIssue(
                    kind=VariableIssueKind.GLOBAL_MISUSE,
                    name=name,
                    file=self._file,
                    line=node.lineno,
                    detail=f"'{name}' declared global — prefer passing as parameter",
                ))


class VariableTracker:
    """Detect unused variables, shadowing, and global misuse in Python source."""

    def analyze(self, source: str, file_path: str = "") -> VariableReport:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return VariableReport()

        report = VariableReport()
        visitor = _ScopeVisitor(file_path, report)
        visitor._push()   # module scope
        visitor.visit(tree)
        visitor._pop()    # flush module scope
        return report
