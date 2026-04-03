"""TypeInferrer — infer types from Python source code (stdlib only)."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InferredType:
    """A single inferred type for a name."""

    name: str
    type: str
    confidence: float
    source: str = "usage"


# Mapping from literal AST node types to Python type names.
_LITERAL_MAP: dict[type, str] = {
    ast.Constant: "",  # handled specially
    ast.List: "list",
    ast.ListComp: "list",
    ast.Dict: "dict",
    ast.DictComp: "dict",
    ast.Set: "set",
    ast.SetComp: "set",
    ast.Tuple: "tuple",
    ast.GeneratorExp: "Generator",
}

_BUILTIN_CALL_MAP: dict[str, str] = {
    "int": "int",
    "float": "float",
    "str": "str",
    "bool": "bool",
    "list": "list",
    "dict": "dict",
    "set": "set",
    "tuple": "tuple",
    "bytes": "bytes",
    "bytearray": "bytearray",
    "frozenset": "frozenset",
    "complex": "complex",
    "range": "range",
    "sorted": "list",
    "reversed": "iterator",
    "enumerate": "enumerate",
    "zip": "zip",
    "map": "map",
    "filter": "filter",
    "open": "TextIO",
    "len": "int",
    "abs": "int",
    "round": "int",
    "sum": "int",
    "min": "int",
    "max": "int",
    "hash": "int",
    "id": "int",
    "ord": "int",
    "chr": "str",
    "repr": "str",
    "hex": "str",
    "oct": "str",
    "bin": "str",
    "format": "str",
    "type": "type",
    "isinstance": "bool",
    "issubclass": "bool",
    "callable": "bool",
    "hasattr": "bool",
    "any": "bool",
    "all": "bool",
}

# Simple regex patterns for quick assignment inference.
_SIMPLE_PATTERNS: list[tuple[str, str, float]] = [
    (r"^(\w+)\s*=\s*(\d+)$", "int", 0.95),
    (r"^(\w+)\s*=\s*(\d+\.\d+)$", "float", 0.95),
    (r'^(\w+)\s*=\s*["\']', "str", 0.90),
    (r'^(\w+)\s*=\s*f["\']', "str", 0.90),
    (r'^(\w+)\s*=\s*b["\']', "bytes", 0.90),
    (r"^(\w+)\s*=\s*True$", "bool", 0.95),
    (r"^(\w+)\s*=\s*False$", "bool", 0.95),
    (r"^(\w+)\s*=\s*None$", "None", 0.85),
    (r"^(\w+)\s*=\s*\[\]$", "list", 0.90),
    (r"^(\w+)\s*=\s*\[", "list", 0.85),
    (r"^(\w+)\s*=\s*\{\}$", "dict", 0.80),
    (r"^(\w+)\s*=\s*\{", "dict", 0.75),
    (r"^(\w+)\s*=\s*\(\)$", "tuple", 0.80),
    (r"^(\w+)\s*=\s*\(", "tuple", 0.70),
    (r"^(\w+)\s*=\s*set\(", "set", 0.90),
    (r"^(\w+)\s*=\s*frozenset\(", "frozenset", 0.90),
]


class TypeInferrer:
    """Infer Python types from source code without executing it."""

    def __init__(self, *, confidence_threshold: float = 0.5) -> None:
        self._confidence_threshold = confidence_threshold

    @property
    def confidence_threshold(self) -> float:
        return self._confidence_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def infer_from_assignment(self, line: str) -> InferredType | None:
        """Infer the type from a single assignment line like ``x = 5``."""
        stripped = line.strip()
        if not stripped or "=" not in stripped:
            return None

        for pattern, type_name, conf in _SIMPLE_PATTERNS:
            m = re.match(pattern, stripped)
            if m:
                name = m.group(1)
                result = InferredType(name=name, type=type_name, confidence=conf, source="assignment")
                if result.confidence >= self._confidence_threshold:
                    return result
                return None

        # Try AST-based inference for more complex assignments.
        return self._infer_assignment_ast(stripped)

    def infer_from_return(self, source: str, func_name: str) -> InferredType | None:
        """Infer the return type of *func_name* from its ``return`` statements."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name != func_name:
                continue
            return self._infer_return_from_func(node, func_name)
        return None

    def infer_all(self, source: str) -> list[InferredType]:
        """Infer types for all assignments and function returns in *source*."""
        results: list[InferredType] = []
        seen_names: set[str] = set()

        # Assignment-level inference (line by line).
        for line in source.splitlines():
            inferred = self.infer_from_assignment(line)
            if inferred and inferred.name not in seen_names:
                seen_names.add(inferred.name)
                results.append(inferred)

        # Function return inference.
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return results

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            ret = self._infer_return_from_func(node, node.name)
            if ret and ret.name not in seen_names:
                seen_names.add(ret.name)
                results.append(ret)

        return results

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _infer_assignment_ast(self, line: str) -> InferredType | None:
        try:
            tree = ast.parse(line)
        except SyntaxError:
            return None

        if not tree.body or not isinstance(tree.body[0], ast.Assign):
            return None

        stmt = tree.body[0]
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            return None

        name = stmt.targets[0].id
        inferred = self._type_from_value(stmt.value)
        if inferred is None:
            return None

        type_name, conf = inferred
        if conf < self._confidence_threshold:
            return None
        return InferredType(name=name, type=type_name, confidence=conf, source="assignment")

    def _type_from_value(self, node: ast.expr) -> tuple[str, float] | None:
        if isinstance(node, ast.Constant):
            return self._type_from_constant(node.value)
        if isinstance(node, ast.Call):
            return self._type_from_call(node)
        type_name = _LITERAL_MAP.get(type(node))
        if type_name:
            return (type_name, 0.85)
        if isinstance(node, ast.BoolOp):
            return ("bool", 0.80)
        if isinstance(node, ast.Compare):
            return ("bool", 0.85)
        if isinstance(node, ast.BinOp):
            return self._type_from_binop(node)
        if isinstance(node, ast.JoinedStr):
            return ("str", 0.95)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return ("bool", 0.85)
        return None

    @staticmethod
    def _type_from_constant(value: object) -> tuple[str, float] | None:
        if isinstance(value, bool):
            return ("bool", 0.95)
        if isinstance(value, int):
            return ("int", 0.95)
        if isinstance(value, float):
            return ("float", 0.95)
        if isinstance(value, str):
            return ("str", 0.95)
        if isinstance(value, bytes):
            return ("bytes", 0.95)
        if value is None:
            return ("None", 0.85)
        return None

    @staticmethod
    def _type_from_call(node: ast.Call) -> tuple[str, float] | None:
        if isinstance(node.func, ast.Name):
            type_name = _BUILTIN_CALL_MAP.get(node.func.id)
            if type_name:
                return (type_name, 0.90)
        return None

    def _type_from_binop(self, node: ast.BinOp) -> tuple[str, float] | None:
        left = self._type_from_value(node.left)
        right = self._type_from_value(node.right)
        if left and right:
            if left[0] == right[0]:
                return (left[0], min(left[1], right[1]) * 0.9)
            if {left[0], right[0]} == {"int", "float"}:
                return ("float", 0.80)
        if left:
            return (left[0], left[1] * 0.7)
        if right:
            return (right[0], right[1] * 0.7)
        return None

    def _infer_return_from_func(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, func_name: str
    ) -> InferredType | None:
        returns: list[ast.expr] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value is not None:
                returns.append(child.value)

        if not returns:
            # Only ``return`` / implicit return → None
            return InferredType(
                name=func_name, type="None", confidence=0.60, source="return"
            )

        types: list[tuple[str, float]] = []
        for ret_val in returns:
            inferred = self._type_from_value(ret_val)
            if inferred:
                types.append(inferred)

        if not types:
            return None

        # All return types agree → high confidence.
        type_names = {t for t, _ in types}
        if len(type_names) == 1:
            t = types[0][0]
            avg_conf = sum(c for _, c in types) / len(types)
            return InferredType(
                name=func_name, type=t, confidence=avg_conf, source="return"
            )

        # Mixed return types → union with lower confidence.
        sorted_types = sorted(type_names)
        union = " | ".join(sorted_types)
        return InferredType(
            name=func_name, type=union, confidence=0.50, source="return"
        )
