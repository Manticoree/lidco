"""Class structure analysis — Task 358."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum


class ClassIssueKind(Enum):
    DEEP_INHERITANCE = "deep_inheritance"   # MRO depth > 3
    TOO_MANY_METHODS = "too_many_methods"   # > 20 public methods
    GOD_CLASS = "god_class"                 # > 30 total attributes + methods
    NO_DOCSTRING = "no_docstring"


@dataclass(frozen=True)
class ClassInfo:
    name: str
    file: str
    line: int
    bases: list[str]
    method_count: int
    attribute_count: int
    has_docstring: bool
    inheritance_depth: int   # len(bases) as proxy for direct parent count


@dataclass(frozen=True)
class ClassIssue:
    kind: ClassIssueKind
    class_name: str
    file: str
    line: int
    detail: str


@dataclass
class ClassReport:
    classes: list[ClassInfo] = field(default_factory=list)
    issues: list[ClassIssue] = field(default_factory=list)

    def by_kind(self, kind: ClassIssueKind) -> list[ClassIssue]:
        return [i for i in self.issues if i.kind == kind]

    @property
    def class_count(self) -> int:
        return len(self.classes)


def _get_docstring(node: ast.ClassDef) -> bool:
    if not node.body:
        return False
    first = node.body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


def _base_names(bases: list[ast.expr]) -> list[str]:
    result = []
    for b in bases:
        if isinstance(b, ast.Name):
            result.append(b.id)
        elif isinstance(b, ast.Attribute):
            result.append(b.attr)
    return result


class ClassAnalyzer:
    """Analyze class structure and flag design issues."""

    def analyze(self, source: str, file_path: str = "") -> ClassReport:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ClassReport()

        report = ClassReport()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            bases = _base_names(node.bases)
            has_doc = _get_docstring(node)

            # Count methods and attributes
            methods = 0
            public_methods = 0
            attributes = 0
            for child in ast.walk(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child is not node:  # skip nested classes' methods
                        methods += 1
                        if not child.name.startswith("_"):
                            public_methods += 1
                elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                    attributes += 1

            inh_depth = len(bases)

            info = ClassInfo(
                name=node.name,
                file=file_path,
                line=node.lineno,
                bases=bases,
                method_count=methods,
                attribute_count=attributes,
                has_docstring=has_doc,
                inheritance_depth=inh_depth,
            )
            report.classes.append(info)

            # Issue: deep inheritance (more than 2 direct bases = complex MRO)
            if inh_depth > 2:
                report.issues.append(ClassIssue(
                    kind=ClassIssueKind.DEEP_INHERITANCE,
                    class_name=node.name,
                    file=file_path,
                    line=node.lineno,
                    detail=f"'{node.name}' has {inh_depth} base classes (threshold: 2)",
                ))

            # Issue: too many public methods
            if public_methods > 20:
                report.issues.append(ClassIssue(
                    kind=ClassIssueKind.TOO_MANY_METHODS,
                    class_name=node.name,
                    file=file_path,
                    line=node.lineno,
                    detail=f"'{node.name}' has {public_methods} public methods (threshold: 20)",
                ))

            # Issue: god class
            total = methods + attributes
            if total > 30:
                report.issues.append(ClassIssue(
                    kind=ClassIssueKind.GOD_CLASS,
                    class_name=node.name,
                    file=file_path,
                    line=node.lineno,
                    detail=f"'{node.name}' has {total} methods+attrs (threshold: 30)",
                ))

            # Issue: no docstring
            if not has_doc:
                report.issues.append(ClassIssue(
                    kind=ClassIssueKind.NO_DOCSTRING,
                    class_name=node.name,
                    file=file_path,
                    line=node.lineno,
                    detail=f"'{node.name}' is missing a class docstring",
                ))

        return report
