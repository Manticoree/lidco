"""Type annotation coverage analysis — Task 340."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class TypeCoverageResult:
    file: str
    annotated_params: int
    total_params: int
    annotated_returns: int
    total_functions: int

    @property
    def coverage(self) -> float:
        """Fraction of annotation slots (params + returns) that are annotated."""
        total = self.total_params + self.total_functions
        if total == 0:
            return 1.0
        annotated = self.annotated_params + self.annotated_returns
        return annotated / total


class TypeCoverageChecker:
    """Measure type annotation coverage in Python source via AST."""

    def check_source(self, source: str, file_path: str = "") -> TypeCoverageResult:
        """Parse *source* and return a TypeCoverageResult."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return TypeCoverageResult(
                file=file_path,
                annotated_params=0,
                total_params=0,
                annotated_returns=0,
                total_functions=0,
            )

        annotated_params = 0
        total_params = 0
        annotated_returns = 0
        total_functions = 0

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            total_functions += 1

            # Return annotation
            if node.returns is not None:
                annotated_returns += 1

            args = node.args
            all_args = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)

            # Exclude self/cls (first positional arg of methods inside a class)
            if all_args and all_args[0].arg in ("self", "cls"):
                all_args = all_args[1:]

            # *args
            if args.vararg:
                all_args.append(args.vararg)
            # **kwargs
            if args.kwarg:
                all_args.append(args.kwarg)

            for arg in all_args:
                total_params += 1
                if arg.annotation is not None:
                    annotated_params += 1

        return TypeCoverageResult(
            file=file_path,
            annotated_params=annotated_params,
            total_params=total_params,
            annotated_returns=annotated_returns,
            total_functions=total_functions,
        )
