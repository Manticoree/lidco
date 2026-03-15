"""Import optimization analysis — Task 354."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import Enum


class ImportIssueKind(Enum):
    UNUSED_IMPORT = "unused_import"
    STAR_IMPORT = "star_import"
    DUPLICATE_IMPORT = "duplicate_import"
    CIRCULAR_RISK = "circular_risk"   # same module imported multiple ways


@dataclass(frozen=True)
class ImportIssue:
    kind: ImportIssueKind
    module: str
    name: str     # specific imported name, or "" for module-level issues
    file: str
    line: int
    suggestion: str


@dataclass
class ImportReport:
    issues: list[ImportIssue] = field(default_factory=list)
    all_imports: list[tuple[str, str, int]] = field(default_factory=list)  # (module, name, line)

    def by_kind(self, kind: ImportIssueKind) -> list[ImportIssue]:
        return [i for i in self.issues if i.kind == kind]

    @property
    def unused_count(self) -> int:
        return len(self.by_kind(ImportIssueKind.UNUSED_IMPORT))

    @property
    def star_count(self) -> int:
        return len(self.by_kind(ImportIssueKind.STAR_IMPORT))


class ImportOptimizer:
    """Analyze Python imports and suggest optimizations."""

    def analyze(self, source: str, file_path: str = "") -> ImportReport:
        """Analyze imports in *source* and return an ImportReport."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ImportReport()

        report = ImportReport()
        imported: dict[str, int] = {}     # name -> line
        seen_modules: dict[str, int] = {} # module -> first line

        # Collect all imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name.split(".")[0]
                    report.all_imports.append((alias.name, local_name, node.lineno))

                    # Duplicate
                    if alias.name in seen_modules:
                        report.issues.append(
                            ImportIssue(
                                kind=ImportIssueKind.DUPLICATE_IMPORT,
                                module=alias.name,
                                name=local_name,
                                file=file_path,
                                line=node.lineno,
                                suggestion=f"'{alias.name}' already imported on line {seen_modules[alias.name]}",
                            )
                        )
                    else:
                        seen_modules[alias.name] = node.lineno
                        imported[local_name] = node.lineno

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    if alias.name == "*":
                        report.issues.append(
                            ImportIssue(
                                kind=ImportIssueKind.STAR_IMPORT,
                                module=module,
                                name="*",
                                file=file_path,
                                line=node.lineno,
                                suggestion=f"Replace 'from {module} import *' with explicit imports",
                            )
                        )
                    else:
                        local_name = alias.asname or alias.name
                        report.all_imports.append((module, local_name, node.lineno))
                        key = f"{module}.{alias.name}"
                        if key in seen_modules:
                            report.issues.append(
                                ImportIssue(
                                    kind=ImportIssueKind.DUPLICATE_IMPORT,
                                    module=module,
                                    name=local_name,
                                    file=file_path,
                                    line=node.lineno,
                                    suggestion=f"'{alias.name}' from '{module}' already imported",
                                )
                            )
                        else:
                            seen_modules[key] = node.lineno
                            imported[local_name] = node.lineno

        # Check unused: find all Load-context Name references
        used_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        for local_name, line in imported.items():
            if local_name not in used_names:
                # Find the module for this import
                module = next(
                    (m for m, n, _ in report.all_imports if n == local_name),
                    local_name,
                )
                report.issues.append(
                    ImportIssue(
                        kind=ImportIssueKind.UNUSED_IMPORT,
                        module=module,
                        name=local_name,
                        file=file_path,
                        line=line,
                        suggestion=f"Remove unused import '{local_name}'",
                    )
                )

        return report
