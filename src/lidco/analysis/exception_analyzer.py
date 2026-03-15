"""Exception handling quality analysis — Task 355."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum


class ExceptionIssueKind(Enum):
    BARE_EXCEPT = "bare_except"
    BROAD_EXCEPT = "broad_except"          # except Exception:
    SWALLOWED_EXCEPTION = "swallowed_exception"  # empty except body (pass)
    MISSING_FINALLY = "missing_finally"    # try/except with no finally for resource
    RERAISE_LOST = "reraise_lost"          # raise X from None (loses original)


@dataclass(frozen=True)
class ExceptionIssue:
    kind: ExceptionIssueKind
    file: str
    line: int
    detail: str


@dataclass
class ExceptionReport:
    issues: list[ExceptionIssue]

    def by_kind(self, kind: ExceptionIssueKind) -> list[ExceptionIssue]:
        return [i for i in self.issues if i.kind == kind]

    @property
    def bare_except_count(self) -> int:
        return len(self.by_kind(ExceptionIssueKind.BARE_EXCEPT))

    @property
    def swallowed_count(self) -> int:
        return len(self.by_kind(ExceptionIssueKind.SWALLOWED_EXCEPTION))


def _is_empty_body(body: list[ast.stmt]) -> bool:
    """Return True if body contains only Pass, Ellipsis, or string constant."""
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Constant):
                continue  # docstring or ellipsis
        return False
    return True


def _handler_type_name(handler: ast.ExceptHandler) -> str:
    """Return the exception type name or '' for bare except."""
    if handler.type is None:
        return ""
    if isinstance(handler.type, ast.Name):
        return handler.type.id
    if isinstance(handler.type, ast.Attribute):
        return handler.type.attr
    return ""


class ExceptionAnalyzer:
    """Analyze exception handling patterns in Python source."""

    def analyze(self, source: str, file_path: str = "") -> ExceptionReport:
        """Return ExceptionReport for *source*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ExceptionReport(issues=[])

        issues: list[ExceptionIssue] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue

            for handler in node.handlers:
                exc_type = _handler_type_name(handler)

                # Bare except:
                if exc_type == "":
                    issues.append(
                        ExceptionIssue(
                            kind=ExceptionIssueKind.BARE_EXCEPT,
                            file=file_path,
                            line=handler.lineno,
                            detail="Bare 'except:' catches all exceptions including SystemExit",
                        )
                    )

                # Broad except Exception:
                elif exc_type == "Exception":
                    issues.append(
                        ExceptionIssue(
                            kind=ExceptionIssueKind.BROAD_EXCEPT,
                            file=file_path,
                            line=handler.lineno,
                            detail="'except Exception:' is too broad; catch specific exception types",
                        )
                    )

                # Swallowed exception (empty handler body)
                if _is_empty_body(handler.body):
                    issues.append(
                        ExceptionIssue(
                            kind=ExceptionIssueKind.SWALLOWED_EXCEPTION,
                            file=file_path,
                            line=handler.lineno,
                            detail="Exception handler is empty (exception silently swallowed)",
                        )
                    )

            # Check for raise X from None (loses traceback)
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Raise)
                    and child.cause is not None
                    and isinstance(child.cause, ast.Constant)
                    and child.cause.value is None
                ):
                    issues.append(
                        ExceptionIssue(
                            kind=ExceptionIssueKind.RERAISE_LOST,
                            file=file_path,
                            line=child.lineno,
                            detail="'raise X from None' suppresses the original traceback",
                        )
                    )

        return ExceptionReport(issues=issues)
