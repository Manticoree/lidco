"""Design pattern detection — Task 353."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum


class PatternKind(Enum):
    SINGLETON = "singleton"
    FACTORY = "factory"
    OBSERVER = "observer"
    DECORATOR_PATTERN = "decorator_pattern"
    CONTEXT_MANAGER = "context_manager"
    ITERATOR = "iterator"


@dataclass(frozen=True)
class PatternMatch:
    kind: PatternKind
    symbol: str
    file: str
    line: int
    confidence: float   # 0.0–1.0
    evidence: str


class PatternMatcher:
    """Detect common design patterns in Python source via AST heuristics."""

    def detect(self, source: str, file_path: str = "") -> list[PatternMatch]:
        """Return all detected patterns in *source*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        results: list[PatternMatch] = []

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            results.extend(self._check_class(node, file_path))

        return results

    # ------------------------------------------------------------------ #

    def _check_class(
        self, cls: ast.ClassDef, file_path: str
    ) -> list[PatternMatch]:
        results: list[PatternMatch] = []
        method_names = {
            n.name
            for n in ast.iter_child_nodes(cls)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        # Singleton: class with _instance attribute + __new__ or get_instance
        if "_instance" in self._class_assignments(cls) or "get_instance" in method_names:
            if "__new__" in method_names or "get_instance" in method_names:
                results.append(
                    PatternMatch(
                        kind=PatternKind.SINGLETON,
                        symbol=cls.name,
                        file=file_path,
                        line=cls.lineno,
                        confidence=0.8,
                        evidence="class has _instance and __new__/get_instance",
                    )
                )

        # Factory: class with create/build/make methods
        factory_methods = {"create", "build", "make", "from_", "new"} & method_names
        if factory_methods:
            results.append(
                PatternMatch(
                    kind=PatternKind.FACTORY,
                    symbol=cls.name,
                    file=file_path,
                    line=cls.lineno,
                    confidence=0.7,
                    evidence=f"factory method(s): {', '.join(sorted(factory_methods))}",
                )
            )

        # Observer: class with subscribe/notify/register/unsubscribe methods
        observer_methods = {"subscribe", "notify", "register", "unsubscribe", "emit", "on"} & method_names
        if len(observer_methods) >= 2:
            results.append(
                PatternMatch(
                    kind=PatternKind.OBSERVER,
                    symbol=cls.name,
                    file=file_path,
                    line=cls.lineno,
                    confidence=0.75,
                    evidence=f"observer method(s): {', '.join(sorted(observer_methods))}",
                )
            )

        # Context manager: __enter__ + __exit__
        if "__enter__" in method_names and "__exit__" in method_names:
            results.append(
                PatternMatch(
                    kind=PatternKind.CONTEXT_MANAGER,
                    symbol=cls.name,
                    file=file_path,
                    line=cls.lineno,
                    confidence=1.0,
                    evidence="implements __enter__ and __exit__",
                )
            )

        # Iterator: __iter__ + __next__
        if "__iter__" in method_names and "__next__" in method_names:
            results.append(
                PatternMatch(
                    kind=PatternKind.ITERATOR,
                    symbol=cls.name,
                    file=file_path,
                    line=cls.lineno,
                    confidence=1.0,
                    evidence="implements __iter__ and __next__",
                )
            )

        # Decorator pattern: class wraps another (has _wrapped / _component attr)
        if "_wrapped" in self._class_assignments(cls) or "_component" in self._class_assignments(cls):
            results.append(
                PatternMatch(
                    kind=PatternKind.DECORATOR_PATTERN,
                    symbol=cls.name,
                    file=file_path,
                    line=cls.lineno,
                    confidence=0.7,
                    evidence="class holds _wrapped/_component attribute",
                )
            )

        return results

    def _class_assignments(self, cls: ast.ClassDef) -> set[str]:
        """Collect attribute names set via self.X = ... in the class."""
        names: set[str] = set()
        for node in ast.walk(cls):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        names.add(target.attr)
                    elif isinstance(target, ast.Name):
                        names.add(target.id)
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Attribute):
                    names.add(node.target.attr)
                elif isinstance(node.target, ast.Name):
                    names.add(node.target.id)
        return names
