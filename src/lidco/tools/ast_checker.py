"""AST Bug Detector — detects 12 Python pitfall patterns using pure AST walk."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


@dataclass(frozen=True)
class ASTIssue:
    """A single issue detected by AST analysis."""

    file: str
    line: int
    rule: str
    message: str
    fix_hint: str


# ---------------------------------------------------------------------------
# AST visitor
# ---------------------------------------------------------------------------


class BugVisitor(ast.NodeVisitor):
    """Walk a parsed AST and collect pitfall issues."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.issues: list[ASTIssue] = []
        self._is_test_file = "test" in Path(filepath).name.lower()
        # Stack of assignment names seen at each scope level, for shadowing
        self._scope_vars: list[set[str]] = [set()]

    def _add(self, node: ast.AST, rule: str, message: str, fix_hint: str) -> None:
        lineno = getattr(node, "lineno", 0)
        self.issues.append(
            ASTIssue(
                file=self.filepath,
                line=lineno,
                rule=rule,
                message=message,
                fix_hint=fix_hint,
            )
        )

    # ------------------------------------------------------------------
    # Rule 1: mutable-default
    # ------------------------------------------------------------------

    def _check_mutable_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for default in node.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                type_name = type(default).__name__.lower()
                self._add(
                    default,
                    "mutable-default",
                    f"Function '{node.name}' has mutable default argument ({type_name})",
                    "Use None as default and set inside function body",
                )

    # ------------------------------------------------------------------
    # Rule 7: unreachable-code — check a statement list for code after
    #          return/raise/continue/break
    # ------------------------------------------------------------------

    _TERMINATORS = (ast.Return, ast.Raise, ast.Continue, ast.Break)

    def _check_unreachable(self, body: list[ast.stmt], scope_name: str) -> None:
        for idx, stmt in enumerate(body):
            if isinstance(stmt, self._TERMINATORS) and idx < len(body) - 1:
                next_stmt = body[idx + 1]
                self._add(
                    next_stmt,
                    "unreachable-code",
                    f"Unreachable code after {type(stmt).__name__.lower()} in '{scope_name}'",
                    "Remove unreachable statements after return/raise/continue/break",
                )
                break  # report only the first occurrence per block

    # ------------------------------------------------------------------
    # Rule 9: implicit-none-return (simplified)
    # ------------------------------------------------------------------

    def _check_implicit_return(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        returns: list[ast.Return] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                returns.append(child)

        if len(returns) < 2:
            return

        has_value = any(r.value is not None for r in returns)
        has_bare = any(r.value is None for r in returns)
        if not (has_value and has_bare):
            return

        self._add(
            node,
            "implicit-none-return",
            f"Function '{node.name}' has mixed return paths (some return a value, some don't)",
            "Add explicit 'return None' to all code paths",
        )

    # ------------------------------------------------------------------
    # Rule 11: loop-variable-leak
    # ------------------------------------------------------------------

    def _check_loop_leak(self, body: list[ast.stmt]) -> None:
        """Check for for-loop variables used after the loop in the same block."""
        for idx, stmt in enumerate(body):
            if not isinstance(stmt, ast.For):
                continue
            # Collect target names from the for-loop
            target_names: set[str] = set()
            if isinstance(stmt.target, ast.Name):
                target_names.add(stmt.target.id)
            elif isinstance(stmt.target, ast.Tuple):
                for elt in stmt.target.elts:
                    if isinstance(elt, ast.Name):
                        target_names.add(elt.id)

            if not target_names:
                continue

            # Check subsequent statements for uses of those names
            for later_stmt in body[idx + 1 :]:
                for node in ast.walk(later_stmt):
                    if isinstance(node, ast.Name) and node.id in target_names:
                        # Make sure it's a load (use), not a new assignment
                        if isinstance(node.ctx, ast.Load):
                            self._add(
                                node,
                                "loop-variable-leak",
                                f"Loop variable '{node.id}' used after the loop",
                                "Save the loop variable before the loop if you need it after",
                            )
                            target_names.discard(node.id)  # report each name once

    # ------------------------------------------------------------------
    # Rule 12: string-format-mismatch (% formatting)
    # ------------------------------------------------------------------

    def _check_percent_format(self, node: ast.BinOp) -> None:
        if not isinstance(node.op, ast.Mod):
            return
        if not isinstance(node.left, ast.Constant) or not isinstance(node.left.value, str):
            return

        fmt_str: str = node.left.value
        placeholders = re.findall(r"%[sdfrg%]", fmt_str)
        real_placeholders = [p for p in placeholders if p != "%%"]

        # RHS must be a tuple for mismatch detection
        if isinstance(node.right, ast.Tuple):
            arg_count = len(node.right.elts)
        else:
            return  # single arg — skip

        if len(real_placeholders) != arg_count:
            self._add(
                node,
                "string-format-mismatch",
                (
                    f"Format string has {len(real_placeholders)} placeholder(s) "
                    f"but {arg_count} argument(s) provided"
                ),
                "Ensure format string placeholders match argument count",
            )

    # ------------------------------------------------------------------
    # Visitors
    # ------------------------------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_mutable_defaults(node)
        self._check_unreachable(node.body, node.name)
        self._check_implicit_return(node)
        self._check_loop_leak(node.body)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_mutable_defaults(node)
        self._check_unreachable(node.body, node.name)
        self._check_implicit_return(node)  # type: ignore[arg-type]
        self._check_loop_leak(node.body)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._check_unreachable(node.body, "<for loop>")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._check_unreachable(node.body, "<while loop>")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Rule 2: bare-except
        if node.type is None:
            self._add(
                node,
                "bare-except",
                "Bare 'except:' catches everything including SystemExit and KeyboardInterrupt",
                "Use 'except Exception as e:' to catch specific exceptions",
            )
        # Rule 3: silenced-exception
        elif len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self._add(
                node,
                "silenced-exception",
                "Exception silenced with 'pass' — error information is discarded",
                "Log the exception or re-raise it instead of silencing",
            )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for op, comparator in zip(node.ops, node.comparators):
            if not isinstance(comparator, ast.Constant):
                continue
            val = comparator.value

            # Rule 4: none-comparison
            if val is None and isinstance(op, (ast.Eq, ast.NotEq)):
                self._add(
                    node,
                    "none-comparison",
                    f"Comparison to None using '{'==' if isinstance(op, ast.Eq) else '!='}'",
                    "Use 'x is None' or 'x is not None'",
                )

            # Rule 5: bool-comparison
            if isinstance(val, bool) and isinstance(op, ast.Eq):
                self._add(
                    node,
                    "bool-comparison",
                    f"Comparison to {val} using '=='",
                    "Use 'if x:' or 'if not x:' directly",
                )

        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        # Rule 6: assert-in-prod (skip test files)
        if not self._is_test_file:
            self._add(
                node,
                "assert-in-prod",
                "assert statement found in non-test code (disabled by -O flag)",
                "Use 'if not condition: raise ValueError(msg)' in production code",
            )
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        # Rule 8: broad-raise
        if node.exc is not None and isinstance(node.exc, ast.Call):
            func = node.exc.func
            if isinstance(func, ast.Name) and func.id == "Exception":
                self._add(
                    node,
                    "broad-raise",
                    "Raising base Exception class is too broad",
                    "Use a specific exception class like ValueError, RuntimeError, etc.",
                )
        self.generic_visit(node)

    def _check_comprehension_shadowing(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    ) -> None:
        # Rule 10: var-shadowing
        # Collect comprehension target names
        generators = node.generators if hasattr(node, "generators") else []
        for gen in generators:
            target = gen.target
            target_names: list[str] = []
            if isinstance(target, ast.Name):
                target_names.append(target.id)
            elif isinstance(target, ast.Tuple):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        target_names.append(elt.id)

            for name in target_names:
                # Check if this name is in the outer scope vars
                for scope in self._scope_vars:
                    if name in scope:
                        self._add(
                            node,
                            "var-shadowing",
                            f"Comprehension variable '{name}' shadows outer scope variable",
                            "Rename comprehension variable to avoid shadowing outer scope",
                        )
                        break

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._check_comprehension_shadowing(node)
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._check_comprehension_shadowing(node)
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._check_comprehension_shadowing(node)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._check_comprehension_shadowing(node)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Track assigned names for shadowing detection
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._scope_vars[-1].add(target.id)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self._check_percent_format(node)
        self.generic_visit(node)


# ---------------------------------------------------------------------------
# Public check_file function
# ---------------------------------------------------------------------------


def check_file(filepath: str, rules: list[str]) -> list[ASTIssue]:
    """Parse *filepath* with ast and return detected issues.

    If *rules* is non-empty, only issues matching those rule names are returned.
    """
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as exc:
        issue = ASTIssue(
            file=filepath,
            line=exc.lineno or 0,
            rule="syntax-error",
            message=str(exc),
            fix_hint="Fix the syntax error",
        )
        return [issue]
    except Exception:
        return []

    visitor = BugVisitor(filepath)
    visitor.visit(tree)

    all_issues = visitor.issues
    if rules:
        all_issues = [i for i in all_issues if i.rule in rules]
    return all_issues


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class ASTBugCheckerTool(BaseTool):
    """Detect common Python pitfall patterns using AST analysis."""

    @property
    def name(self) -> str:
        return "check_ast_bugs"

    @property
    def description(self) -> str:
        return (
            "Detect common Python pitfall patterns using AST analysis "
            "(no subprocess needed)."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Python file or directory to check.",
                required=True,
            ),
            ToolParameter(
                name="rules",
                type="array",
                description="Specific rule names to check. Empty = all rules.",
                required=False,
                default=[],
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        path_str: str = kwargs["path"]
        rules: list[str] = list(kwargs.get("rules", []))

        path = Path(path_str)
        if path.is_dir():
            py_files = sorted(path.rglob("*.py"))
        elif path.is_file():
            py_files = [path]
        else:
            return ToolResult(
                output=f"Path not found: {path_str}",
                success=False,
                error=f"Path not found: {path_str}",
            )

        all_issues: list[ASTIssue] = []
        for py_file in py_files:
            all_issues.extend(check_file(str(py_file), rules))

        total = len(all_issues)
        files_checked = len(py_files)

        lines: list[str] = [
            f"AST Bug Check: {total} issues found in {files_checked} file(s)"
        ]
        if all_issues:
            lines.append("")
            for issue in all_issues:
                lines.append(f"{issue.file}:{issue.line} [{issue.rule}] {issue.message}")
                lines.append(f"  Fix: {issue.fix_hint}")

        output = "\n".join(lines)

        return ToolResult(
            output=output,
            success=(total == 0),
            metadata={
                "total": total,
                "files": files_checked,
                "issues": [
                    {
                        "file": i.file,
                        "line": i.line,
                        "rule": i.rule,
                        "message": i.message,
                        "fix_hint": i.fix_hint,
                    }
                    for i in all_issues
                ],
            },
        )
