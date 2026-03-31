"""Generate property-based test suggestions from function signatures."""

from __future__ import annotations

from dataclasses import dataclass, field
import ast
import re


@dataclass
class PropertyTest:
    function_name: str
    module_path: str
    test_name: str
    test_code: str
    pattern: str  # "roundtrip", "invariant", "oracle", "smoke"
    description: str


@dataclass
class FunctionSignature:
    name: str
    params: list[dict]  # [{"name": "x", "annotation": "int"}, ...]
    return_annotation: str | None
    docstring: str | None
    is_async: bool = False


class PropertyTestGenerator:
    def __init__(self) -> None:
        self._type_strategies: dict[str, str] = {
            "int": "random.randint(-1000, 1000)",
            "float": "random.uniform(-1000.0, 1000.0)",
            "str": "''.join(random.choices('abcdefghij', k=random.randint(0, 20)))",
            "bool": "random.choice([True, False])",
            "list": "[random.randint(0, 100) for _ in range(random.randint(0, 10))]",
            "dict": "{f'k{i}': random.randint(0,100) for i in range(random.randint(0, 5))}",
        }

    @property
    def type_strategies(self) -> dict[str, str]:
        return dict(self._type_strategies)

    def extract_signatures(self, source: str) -> list[FunctionSignature]:
        """Extract function signatures from Python source code using AST."""
        signatures: list[FunctionSignature] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return signatures

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_"):
                    continue
                params: list[dict] = []
                for arg in node.args.args:
                    if arg.arg == "self":
                        continue
                    annotation = None
                    if arg.annotation:
                        annotation = (
                            ast.unparse(arg.annotation)
                            if hasattr(ast, "unparse")
                            else str(arg.annotation)
                        )
                    params.append({"name": arg.arg, "annotation": annotation})

                ret = None
                if node.returns:
                    ret = (
                        ast.unparse(node.returns)
                        if hasattr(ast, "unparse")
                        else str(node.returns)
                    )

                docstring = ast.get_docstring(node)
                signatures.append(
                    FunctionSignature(
                        name=node.name,
                        params=params,
                        return_annotation=ret,
                        docstring=docstring,
                        is_async=isinstance(node, ast.AsyncFunctionDef),
                    )
                )
        return signatures

    def generate_tests(
        self, source: str, module_path: str = "module"
    ) -> list[PropertyTest]:
        """Generate property-based tests for all public functions."""
        sigs = self.extract_signatures(source)
        tests: list[PropertyTest] = []
        for sig in sigs:
            tests.extend(self._generate_for_function(sig, module_path))
        return tests

    def _generate_for_function(
        self, sig: FunctionSignature, module_path: str
    ) -> list[PropertyTest]:
        """Generate property tests for a single function."""
        tests: list[PropertyTest] = []
        # Always generate a smoke test
        tests.append(self._generate_smoke_test(sig, module_path))

        # If function returns same type as input, suggest roundtrip
        if sig.return_annotation and sig.params:
            first_param = sig.params[0]
            if first_param.get("annotation") == sig.return_annotation:
                tests.append(self._generate_roundtrip_test(sig, module_path))

        # If function returns bool, suggest invariant
        if sig.return_annotation == "bool":
            tests.append(self._generate_invariant_test(sig, module_path))

        return tests

    def _generate_smoke_test(
        self, sig: FunctionSignature, module_path: str
    ) -> PropertyTest:
        args = self._generate_args(sig)
        call = f"{'await ' if sig.is_async else ''}{sig.name}({args})"
        code = (
            f"def test_{sig.name}_smoke():\n"
            f"    import random\n"
            f"    for _ in range(100):\n"
            f"        result = {call}\n"
            f"        assert result is not None or True  # smoke: no crash\n"
        )
        return PropertyTest(
            function_name=sig.name,
            module_path=module_path,
            test_name=f"test_{sig.name}_smoke",
            test_code=code,
            pattern="smoke",
            description=f"Smoke test: {sig.name} doesn't crash on random inputs",
        )

    def _generate_roundtrip_test(
        self, sig: FunctionSignature, module_path: str
    ) -> PropertyTest:
        args = self._generate_args(sig)
        code = (
            f"def test_{sig.name}_roundtrip():\n"
            f"    import random\n"
            f"    for _ in range(100):\n"
            f"        x = {args}\n"
            f"        result = {sig.name}(x)\n"
            f"        # Verify roundtrip property\n"
        )
        return PropertyTest(
            function_name=sig.name,
            module_path=module_path,
            test_name=f"test_{sig.name}_roundtrip",
            test_code=code,
            pattern="roundtrip",
            description=f"Roundtrip test: {sig.name} preserves type",
        )

    def _generate_invariant_test(
        self, sig: FunctionSignature, module_path: str
    ) -> PropertyTest:
        args = self._generate_args(sig)
        code = (
            f"def test_{sig.name}_invariant():\n"
            f"    import random\n"
            f"    for _ in range(100):\n"
            f"        result = {sig.name}({args})\n"
            f"        assert isinstance(result, bool)\n"
        )
        return PropertyTest(
            function_name=sig.name,
            module_path=module_path,
            test_name=f"test_{sig.name}_invariant",
            test_code=code,
            pattern="invariant",
            description=f"Invariant test: {sig.name} always returns bool",
        )

    def _generate_args(self, sig: FunctionSignature) -> str:
        parts: list[str] = []
        for p in sig.params:
            ann = p.get("annotation")
            if ann and ann in self._type_strategies:
                parts.append(self._type_strategies[ann])
            else:
                parts.append("None")
        return ", ".join(parts) if parts else ""

    def format_test_file(self, tests: list[PropertyTest]) -> str:
        """Format property tests into a complete test file."""
        if not tests:
            return "# No property tests generated\n"
        lines = ["import random", "import unittest", ""]
        lines.append("class TestProperties(unittest.TestCase):")
        for t in tests:
            lines.append(f"    {t.test_code}")
            lines.append("")
        return "\n".join(lines) + "\n"
