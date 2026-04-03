"""Test scaffolder — parse Python source and generate test file skeletons (stdlib only)."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScaffoldResult:
    """Result of scaffolding a test file."""

    test_file: str
    test_classes: list[str] = field(default_factory=list)
    test_methods: list[str] = field(default_factory=list)


class TestScaffolder:
    """Generate test skeletons from Python source code."""

    def extract_functions(self, source: str) -> list[str]:
        """Return top-level function names from *source*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        return [
            node.name
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        ]

    def extract_classes(self, source: str) -> list[dict]:
        """Return ``[{name, methods}]`` for each class in *source*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        results: list[dict] = []
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            methods = [
                m.name
                for m in ast.iter_child_nodes(node)
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not m.name.startswith("_")
            ]
            results.append({"name": node.name, "methods": methods})
        return results

    def scaffold(self, source: str, class_name: str = "") -> ScaffoldResult:
        """Parse *source* for defs/classes and generate a test skeleton.

        If *class_name* is given, only scaffold tests for that class.
        """
        classes = self.extract_classes(source)
        functions = self.extract_functions(source)

        if class_name:
            classes = [c for c in classes if c["name"] == class_name]

        test_classes: list[str] = []
        test_methods: list[str] = []
        lines: list[str] = [
            '"""Auto-generated test scaffold."""',
            "from __future__ import annotations",
            "",
            "import unittest",
            "",
            "",
        ]

        for cls in classes:
            tc_name = f"Test{cls['name']}"
            test_classes.append(tc_name)
            lines.append(f"class {tc_name}(unittest.TestCase):")
            if not cls["methods"]:
                lines.append("    pass")
            for method in cls["methods"]:
                m_name = f"test_{method}"
                test_methods.append(m_name)
                lines.append(f"    def {m_name}(self):")
                cname = cls["name"]
                lines.append(f"        self.fail('TODO: test {cname}.{method}')")
                lines.append("")
            lines.append("")

        if functions:
            tc_name = "TestFunctions"
            test_classes.append(tc_name)
            lines.append(f"class {tc_name}(unittest.TestCase):")
            for fn in functions:
                m_name = f"test_{fn}"
                test_methods.append(m_name)
                lines.append(f"    def {m_name}(self):")
                lines.append(f"        self.fail('TODO: test {fn}')")
                lines.append("")
            lines.append("")

        if not test_classes:
            lines.append("# No classes or functions found to scaffold.")
            lines.append("")

        content = "\n".join(lines)
        return ScaffoldResult(
            test_file=content,
            test_classes=test_classes,
            test_methods=test_methods,
        )

    def scaffold_for_file(self, filename: str, source: str) -> str:
        """Generate a full test file for *filename* with the given *source*."""
        module_name = re.sub(r"\.py$", "", filename.replace("/", ".").replace("\\", "."))
        # Strip leading dots
        module_name = module_name.lstrip(".")

        result = self.scaffold(source)
        # Prepend an import for the module under test
        header = (
            f'"""Tests for {filename}."""\n'
            "from __future__ import annotations\n"
            "\n"
            "import unittest\n"
            "\n"
            f"# import {module_name}  # TODO: adjust import\n"
            "\n"
            "\n"
        )

        # Strip the generic header from scaffold result (first 6 lines)
        body_lines = result.test_file.split("\n")[6:]
        return header + "\n".join(body_lines)
