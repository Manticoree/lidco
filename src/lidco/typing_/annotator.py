"""Type Annotator — suggest type annotations for untyped Python code (stdlib only).

Analyses function signatures via AST:
- Infers types from default values (int, str, bool, float, list, dict, None)
- Uses naming conventions (is_/has_ → bool, url/path → str, count/n_ → int)
- Checks return patterns (always returns literal → infer type)
- Outputs ready-to-use annotation suggestions
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any


class AnnotatorError(Exception):
    """Raised when annotation inference fails."""


@dataclass
class ParamAnnotation:
    name: str
    suggested_type: str
    confidence: float        # 0.0–1.0
    reason: str              # why this type was inferred


@dataclass
class FunctionAnnotation:
    """Suggested annotations for a single function."""

    name: str
    lineno: int
    params: list[ParamAnnotation] = field(default_factory=list)
    return_type: str = ""
    return_confidence: float = 0.0
    return_reason: str = ""

    def has_suggestions(self) -> bool:
        return bool(self.params) or bool(self.return_type)

    def signature(self) -> str:
        """Render suggested function signature with annotations."""
        param_parts = []
        for p in self.params:
            param_parts.append(f"{p.name}: {p.suggested_type}")
        params_str = ", ".join(param_parts)
        ret = f" -> {self.return_type}" if self.return_type else ""
        return f"def {self.name}({params_str}){ret}:"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "lineno": self.lineno,
            "params": [
                {"name": p.name, "type": p.suggested_type,
                 "confidence": p.confidence, "reason": p.reason}
                for p in self.params
            ],
            "return_type": self.return_type,
            "return_confidence": self.return_confidence,
        }


# ------------------------------------------------------------------ #
# Heuristic tables                                                     #
# ------------------------------------------------------------------ #

_NAME_PATTERNS: list[tuple[re.Pattern, str, float, str]] = [
    # (pattern, type, confidence, reason)
    (re.compile(r"^is_|^has_|^can_|^should_|^enable|^disable|^flag"),
     "bool", 0.8, "bool naming convention"),
    (re.compile(r"url|uri|endpoint|host|domain|path|filename|filepath"),
     "str", 0.75, "string naming convention"),
    (re.compile(r"^(n_|num_|count_|count$|size$|length$|limit$|offset$|index$|idx$|port$)"),
     "int", 0.8, "integer naming convention"),
    (re.compile(r"^(name$|label$|title$|description$|message$|text$|content$|key$|value$)"),
     "str", 0.7, "string naming convention"),
    (re.compile(r"^(items$|values$|keys$|elements$|entries$|rows$|cols$|lines$)"),
     "list", 0.65, "list naming convention"),
    (re.compile(r"^(config$|options$|settings$|params$|kwargs$|data$|payload$|mapping$)"),
     "dict", 0.65, "dict naming convention"),
    (re.compile(r"^(callback$|handler$|func$|fn$)"),
     "Callable", 0.6, "callable naming convention"),
    (re.compile(r"^(rate$|ratio$|score$|weight$|factor$|prob$|probability$)"),
     "float", 0.7, "float naming convention"),
    (re.compile(r"^(timeout$|delay$|interval$|duration$|seconds$|minutes$)"),
     "float", 0.7, "duration naming convention"),
]

_DEFAULT_TYPE_MAP: dict[type, str] = {
    int: "int",
    float: "float",
    bool: "bool",
    str: "str",
    bytes: "bytes",
    list: "list",
    dict: "dict",
    tuple: "tuple",
    set: "set",
    type(None): "None",
}


class TypeAnnotator:
    """Infer and suggest type annotations for untyped Python source.

    Usage::

        ann = TypeAnnotator()
        source = '''
        def process(name, count=0, verbose=False):
            if verbose:
                print(name)
            return name * count
        '''
        suggestions = ann.annotate(source)
        for s in suggestions:
            print(s.signature())
    """

    def __init__(self, min_confidence: float = 0.5) -> None:
        self._min_confidence = min_confidence

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def annotate(self, source: str) -> list[FunctionAnnotation]:
        """Return annotation suggestions for all unannotated functions."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise AnnotatorError(f"Syntax error: {exc}") from exc

        results: list[FunctionAnnotation] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ann = self._annotate_function(node)
                if ann.has_suggestions():
                    results.append(ann)
        return results

    def annotate_function(self, source: str, func_name: str) -> FunctionAnnotation | None:
        """Annotate a specific function by name."""
        all_annotations = self.annotate(source)
        return next((a for a in all_annotations if a.name == func_name), None)

    def coverage(self, source: str) -> dict[str, Any]:
        """Return annotation coverage stats for the source."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise AnnotatorError(f"Syntax error: {exc}") from exc

        total_params = 0
        annotated_params = 0
        total_returns = 0
        annotated_returns = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in node.args.args:
                    if arg.arg in ("self", "cls"):
                        continue
                    total_params += 1
                    if arg.annotation:
                        annotated_params += 1
                total_returns += 1
                if node.returns:
                    annotated_returns += 1

        return {
            "total_params": total_params,
            "annotated_params": annotated_params,
            "total_returns": total_returns,
            "annotated_returns": annotated_returns,
            "param_coverage": annotated_params / total_params if total_params else 1.0,
            "return_coverage": annotated_returns / total_returns if total_returns else 1.0,
        }

    # ------------------------------------------------------------------ #
    # Inference engine                                                     #
    # ------------------------------------------------------------------ #

    def _annotate_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> FunctionAnnotation:
        result = FunctionAnnotation(name=node.name, lineno=node.lineno)
        args = node.args
        n_args = len(args.args)
        n_defaults = len(args.defaults)
        defaults_start = n_args - n_defaults

        for i, arg in enumerate(args.args):
            if arg.arg in ("self", "cls"):
                continue
            if arg.annotation:
                continue  # already annotated

            default_node = args.defaults[i - defaults_start] if i >= defaults_start else None
            ann = self._infer_param(arg.arg, default_node)
            if ann and ann.confidence >= self._min_confidence:
                result.params.append(ann)

        # Return type inference
        if not node.returns:
            ret_type, confidence, reason = self._infer_return(node)
            if ret_type and confidence >= self._min_confidence:
                result.return_type = ret_type
                result.return_confidence = confidence
                result.return_reason = reason

        return result

    def _infer_param(
        self, name: str, default_node: ast.expr | None
    ) -> ParamAnnotation | None:
        # 1. From default value (highest confidence)
        if default_node is not None:
            inferred = self._type_from_node(default_node)
            if inferred:
                return ParamAnnotation(
                    name=name,
                    suggested_type=inferred,
                    confidence=0.9,
                    reason="inferred from default value",
                )
            if isinstance(default_node, ast.Constant) and default_node.value is None:
                # default=None → Optional[something]
                type_from_name = self._type_from_name(name)
                if type_from_name:
                    return ParamAnnotation(
                        name=name,
                        suggested_type=f"{type_from_name} | None",
                        confidence=0.7,
                        reason="default=None + naming convention",
                    )
                return ParamAnnotation(
                    name=name,
                    suggested_type="object | None",
                    confidence=0.5,
                    reason="default=None",
                )

        # 2. From naming convention
        type_from_name = self._type_from_name(name)
        if type_from_name:
            return ParamAnnotation(
                name=name,
                suggested_type=type_from_name,
                confidence=self._name_confidence(name),
                reason="naming convention",
            )

        return None

    def _type_from_node(self, node: ast.expr) -> str:
        if isinstance(node, ast.Constant):
            return _DEFAULT_TYPE_MAP.get(type(node.value), "")
        if isinstance(node, ast.List):
            return "list"
        if isinstance(node, ast.Dict):
            return "dict"
        if isinstance(node, ast.Set):
            return "set"
        if isinstance(node, ast.Tuple):
            return "tuple"
        return ""

    def _type_from_name(self, name: str) -> str:
        lower = name.lower()
        for pattern, typ, _, _ in _NAME_PATTERNS:
            if pattern.search(lower):
                return typ
        return ""

    def _name_confidence(self, name: str) -> float:
        lower = name.lower()
        for pattern, _, confidence, _ in _NAME_PATTERNS:
            if pattern.search(lower):
                return confidence
        return 0.5

    def _infer_return(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> tuple[str, float, str]:
        """Try to infer return type from the function body."""
        return_values: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value is not None:
                t = self._type_from_node(child.value)
                if t:
                    return_values.append(t)

        if not return_values:
            # Check if function has any return with value
            has_return = any(
                isinstance(n, ast.Return) and n.value is not None
                for n in ast.walk(node)
            )
            if not has_return:
                return "None", 0.8, "no return value found"
            return "", 0.0, ""

        unique = set(return_values)
        if len(unique) == 1:
            return unique.pop(), 0.75, "consistent return type"
        return "", 0.0, "mixed return types"
