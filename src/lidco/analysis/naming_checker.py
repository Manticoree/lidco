"""Naming convention checker — Task 347."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from enum import Enum


class NamingViolationKind(Enum):
    FUNCTION_NOT_SNAKE = "function_not_snake_case"
    CLASS_NOT_PASCAL = "class_not_pascal_case"
    CONSTANT_NOT_UPPER = "constant_not_upper_case"
    VARIABLE_NOT_SNAKE = "variable_not_snake_case"


@dataclass(frozen=True)
class NamingViolation:
    kind: NamingViolationKind
    name: str
    file: str
    line: int
    suggestion: str


_SNAKE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_PASCAL_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
_UPPER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Names to skip
_SKIP_FUNCTION_NAMES = frozenset({
    "__init__", "__new__", "__repr__", "__str__", "__len__",
    "__eq__", "__hash__", "__call__", "__enter__", "__exit__",
    "__iter__", "__next__", "__getitem__", "__setitem__",
    "__delitem__", "__contains__", "__del__",
})


def _to_snake(name: str) -> str:
    """Convert PascalCase/camelCase to snake_case suggestion."""
    s1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


def _to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase suggestion."""
    return "".join(part.capitalize() for part in name.split("_") if part)


def _to_upper(name: str) -> str:
    return _to_snake(name).upper()


class NamingChecker:
    """Check Python naming conventions using AST."""

    def check_source(
        self, source: str, file_path: str = ""
    ) -> list[NamingViolation]:
        """Return all naming convention violations in *source*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        violations: list[NamingViolation] = []

        for node in ast.walk(tree):
            # Functions and methods
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if name in _SKIP_FUNCTION_NAMES or name.startswith("_"):
                    continue
                if not _SNAKE_RE.match(name):
                    violations.append(
                        NamingViolation(
                            kind=NamingViolationKind.FUNCTION_NOT_SNAKE,
                            name=name,
                            file=file_path,
                            line=node.lineno,
                            suggestion=_to_snake(name),
                        )
                    )

            # Classes
            elif isinstance(node, ast.ClassDef):
                name = node.name
                if name.startswith("_"):
                    continue
                if not _PASCAL_RE.match(name):
                    violations.append(
                        NamingViolation(
                            kind=NamingViolationKind.CLASS_NOT_PASCAL,
                            name=name,
                            file=file_path,
                            line=node.lineno,
                            suggestion=_to_pascal(name),
                        )
                    )

            # Module-level assignments
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    name = target.id
                    if name.startswith("_"):
                        continue
                    # ALL_CAPS or snake_case are both ok for variables
                    # Only flag clearly wrong patterns (PascalCase variable names)
                    if (
                        _PASCAL_RE.match(name)
                        and not _UPPER_RE.match(name)
                        and len(name) > 1
                    ):
                        violations.append(
                            NamingViolation(
                                kind=NamingViolationKind.VARIABLE_NOT_SNAKE,
                                name=name,
                                file=file_path,
                                line=node.lineno,
                                suggestion=_to_snake(name),
                            )
                        )

        return violations
