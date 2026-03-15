"""Control flow analysis — Task 359."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum


class FlowIssueKind(Enum):
    UNREACHABLE_CODE = "unreachable_code"       # code after return/raise/break/continue
    MISSING_RETURN = "missing_return"           # function with annotation but no return
    INCONSISTENT_RETURN = "inconsistent_return" # some paths return value, some don't
    INFINITE_LOOP = "infinite_loop"             # while True with no break


@dataclass(frozen=True)
class FlowIssue:
    kind: FlowIssueKind
    function: str
    file: str
    line: int
    detail: str


@dataclass
class FlowReport:
    issues: list[FlowIssue] = field(default_factory=list)
    functions_analyzed: int = 0

    def by_kind(self, kind: FlowIssueKind) -> list[FlowIssue]:
        return [i for i in self.issues if i.kind == kind]


def _is_terminator(node: ast.stmt) -> bool:
    return isinstance(node, (ast.Return, ast.Raise, ast.Break, ast.Continue))


def _body_always_returns(stmts: list[ast.stmt]) -> bool:
    """Return True if every execution path through stmts ends with a return/raise."""
    for stmt in stmts:
        if isinstance(stmt, (ast.Return, ast.Raise)):
            return True
        if isinstance(stmt, ast.If):
            if stmt.orelse and _body_always_returns(stmt.body) and _body_always_returns(stmt.orelse):
                return True
        if isinstance(stmt, (ast.For, ast.While)):
            if stmt.orelse and _body_always_returns(stmt.orelse):
                return True
    return False


def _has_return_value(stmts: list[ast.stmt]) -> bool:
    """Return True if any Return node in stmts has a non-None value."""
    for node in ast.walk(ast.Module(body=stmts, type_ignores=[])):
        if isinstance(node, ast.Return) and node.value is not None:
            return True
    return False


def _has_bare_return(stmts: list[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=stmts, type_ignores=[])):
        if isinstance(node, ast.Return) and node.value is None:
            return True
    return False


def _has_break(stmts: list[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=stmts, type_ignores=[])):
        if isinstance(node, ast.Break):
            return True
    return False


class _FunctionFlowVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, report: FlowReport) -> None:
        self._file = file_path
        self._report = report

    def _analyze_fn(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._report.functions_analyzed += 1
        name = node.name
        body = node.body

        # --- Unreachable code ---
        for stmts in [body] + [
            n.body for n in ast.walk(ast.Module(body=body, type_ignores=[]))
            if isinstance(n, (ast.If, ast.For, ast.While, ast.With,
                               ast.Try, ast.ExceptHandler))
        ]:
            for i, stmt in enumerate(stmts[:-1]):
                if _is_terminator(stmt):
                    # anything after is unreachable
                    next_stmt = stmts[i + 1]
                    if not isinstance(next_stmt, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                        self._report.issues.append(FlowIssue(
                            kind=FlowIssueKind.UNREACHABLE_CODE,
                            function=name,
                            file=self._file,
                            line=next_stmt.lineno,
                            detail=f"Unreachable code after {type(stmt).__name__} in '{name}'",
                        ))
                        break

        # --- Missing / inconsistent return ---
        has_annotation = node.returns is not None and not (
            isinstance(node.returns, ast.Constant) and node.returns.value is None
        )
        has_val = _has_return_value(body)
        has_bare = _has_bare_return(body)
        always_returns = _body_always_returns(body)

        if has_val and (has_bare or not always_returns):
            # Some paths return a value, some do not
            self._report.issues.append(FlowIssue(
                kind=FlowIssueKind.INCONSISTENT_RETURN,
                function=name,
                file=self._file,
                line=node.lineno,
                detail=f"'{name}' has paths that return a value and paths that do not",
            ))
        elif has_annotation and not has_val and not has_bare:
            # Function with return annotation but no return statement at all
            self._report.issues.append(FlowIssue(
                kind=FlowIssueKind.MISSING_RETURN,
                function=name,
                file=self._file,
                line=node.lineno,
                detail=f"'{name}' has a return annotation but no return statement",
            ))

        # --- Infinite loop ---
        for child in ast.walk(ast.Module(body=body, type_ignores=[])):
            if isinstance(child, ast.While):
                test = child.test
                is_true = (
                    (isinstance(test, ast.Constant) and test.value is True)
                    or (isinstance(test, ast.Name) and test.id == "True")
                )
                if is_true and not _has_break(child.body):
                    self._report.issues.append(FlowIssue(
                        kind=FlowIssueKind.INFINITE_LOOP,
                        function=name,
                        file=self._file,
                        line=child.lineno,
                        detail=f"'while True' loop in '{name}' has no break statement",
                    ))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._analyze_fn(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


class FlowAnalyzer:
    """Detect control flow issues in Python source."""

    def analyze(self, source: str, file_path: str = "") -> FlowReport:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return FlowReport()

        report = FlowReport()
        visitor = _FunctionFlowVisitor(file_path, report)
        visitor.visit(tree)
        return report
