"""AST-based Python symbol extractor — Q125."""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Callable, Optional

from lidco.analysis.symbol_index2 import SymbolDef


@dataclass
class ExtractionResult:
    module: str
    definitions: list[SymbolDef] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _get_docstring(node: ast.AST) -> str:
    """Extract docstring from first Constant in body, if any."""
    body = getattr(node, "body", [])
    if body and isinstance(body[0], ast.Expr):
        val = body[0].value
        if isinstance(val, ast.Constant) and isinstance(val.value, str):
            return val.value
    return ""


class PythonExtractor:
    """Extract symbols from Python source via AST."""

    def extract(self, source: str, module_name: str = "<unknown>") -> ExtractionResult:
        result = ExtractionResult(module=module_name)
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            result.errors.append(str(exc))
            return result

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result.definitions.append(
                    SymbolDef(
                        name=node.name,
                        kind="function",
                        module=module_name,
                        line=node.lineno,
                        docstring=_get_docstring(node),
                    )
                )
            elif isinstance(node, ast.ClassDef):
                result.definitions.append(
                    SymbolDef(
                        name=node.name,
                        kind="class",
                        module=module_name,
                        line=node.lineno,
                        docstring=_get_docstring(node),
                    )
                )
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        result.definitions.append(
                            SymbolDef(
                                name=target.id,
                                kind="variable",
                                module=module_name,
                                line=node.lineno,
                            )
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    result.imports.append(name)
                    result.definitions.append(
                        SymbolDef(
                            name=name,
                            kind="import",
                            module=module_name,
                            line=node.lineno,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    result.imports.append(name)
                    result.definitions.append(
                        SymbolDef(
                            name=name,
                            kind="import",
                            module=module_name,
                            line=node.lineno,
                        )
                    )

        return result

    def extract_file(self, path: str, read_fn: Callable = None) -> ExtractionResult:
        try:
            if read_fn is not None:
                source = read_fn(path)
            else:
                with open(path, encoding="utf-8", errors="replace") as f:
                    source = f.read()
        except OSError as exc:
            result = ExtractionResult(module=path)
            result.errors.append(str(exc))
            return result
        module_name = path.replace("/", ".").replace("\\", ".").rstrip(".py")
        if module_name.endswith(".py"):
            module_name = module_name[:-3]
        return self.extract(source, module_name=path)
