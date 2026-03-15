"""Public API extraction — Task 350."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ApiParam:
    name: str
    annotation: str   # "" if not annotated
    default: str      # "" if no default
    kind: str         # "positional" | "keyword" | "vararg" | "kwarg"


@dataclass(frozen=True)
class ApiFunction:
    name: str
    file: str
    line: int
    params: tuple[ApiParam, ...]
    return_annotation: str   # "" if not annotated
    docstring: str           # "" if no docstring
    is_async: bool = False
    is_method: bool = False
    class_name: str = ""     # set for methods


@dataclass
class ApiReport:
    functions: list[ApiFunction] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)

    def find(self, name: str) -> list[ApiFunction]:
        return [f for f in self.functions if f.name == name]

    def public_functions(self) -> list[ApiFunction]:
        return [f for f in self.functions if not f.name.startswith("_")]

    def by_class(self, class_name: str) -> list[ApiFunction]:
        return [f for f in self.functions if f.class_name == class_name]


def _annotation_str(node: ast.expr | None) -> str:
    if node is None:
        return ""
    return ast.unparse(node)


def _default_str(node: ast.expr | None) -> str:
    if node is None:
        return ""
    return ast.unparse(node)


def _get_docstring(node: ast.AST) -> str:
    body = getattr(node, "body", [])
    if body and isinstance(body[0], ast.Expr):
        v = body[0].value
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            return v.value
    return ""


def _extract_params(args: ast.arguments) -> tuple[ApiParam, ...]:
    params: list[ApiParam] = []

    # positional-only
    for arg in args.posonlyargs:
        params.append(ApiParam(
            name=arg.arg,
            annotation=_annotation_str(arg.annotation),
            default="",
            kind="positional",
        ))

    # regular args
    n_defaults = len(args.defaults)
    n_args = len(args.args)
    for i, arg in enumerate(args.args):
        default_idx = i - (n_args - n_defaults)
        default = _default_str(args.defaults[default_idx]) if default_idx >= 0 else ""
        params.append(ApiParam(
            name=arg.arg,
            annotation=_annotation_str(arg.annotation),
            default=default,
            kind="positional",
        ))

    # *args
    if args.vararg:
        params.append(ApiParam(
            name=f"*{args.vararg.arg}",
            annotation=_annotation_str(args.vararg.annotation),
            default="",
            kind="vararg",
        ))

    # keyword-only
    for i, arg in enumerate(args.kwonlyargs):
        default = _default_str(args.kw_defaults[i]) if args.kw_defaults[i] is not None else ""
        params.append(ApiParam(
            name=arg.arg,
            annotation=_annotation_str(arg.annotation),
            default=default,
            kind="keyword",
        ))

    # **kwargs
    if args.kwarg:
        params.append(ApiParam(
            name=f"**{args.kwarg.arg}",
            annotation=_annotation_str(args.kwarg.annotation),
            default="",
            kind="kwarg",
        ))

    return tuple(params)


class ApiExtractor:
    """Extract public API signatures from Python source."""

    def extract(self, source: str, file_path: str = "") -> ApiReport:
        """Parse *source* and return an ApiReport."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ApiReport()

        report = ApiReport()

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn = self._make_fn(node, file_path, is_method=False)
                report.functions.append(fn)

            elif isinstance(node, ast.ClassDef):
                report.classes.append(node.name)
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        fn = self._make_fn(
                            child, file_path, is_method=True, class_name=node.name
                        )
                        report.functions.append(fn)

        return report

    def _make_fn(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        is_method: bool,
        class_name: str = "",
    ) -> ApiFunction:
        params = _extract_params(node.args)
        # Remove self/cls from method params for API display
        if is_method and params and params[0].name in ("self", "cls"):
            params = params[1:]
        return ApiFunction(
            name=node.name,
            file=file_path,
            line=node.lineno,
            params=params,
            return_annotation=_annotation_str(node.returns),
            docstring=_get_docstring(node),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=is_method,
            class_name=class_name,
        )
