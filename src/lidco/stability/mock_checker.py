"""
Mock Integrity Checker.

Detects mock signature drift, unused mocks, and over-mocking in test code.
"""
from __future__ import annotations

import ast
import importlib
import inspect


class MockIntegrityChecker:
    """Analyzes test source for mock integrity problems."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_signature_match(self, mock_specs: list[dict]) -> list[dict]:
        """Verify mock specs against real class signatures.

        Args:
            mock_specs: List of dicts with "mock_target", "spec_class", "methods".

        Returns:
            List of dicts with "mock_target", "issue", "severity".
        """
        findings: list[dict] = []

        for spec in mock_specs:
            mock_target = spec.get("mock_target", "")
            spec_class_path = spec.get("spec_class", "")
            declared_methods: list[str] = spec.get("methods", [])

            if not spec_class_path:
                continue

            real_methods = self._get_real_methods(spec_class_path)
            if real_methods is None:
                findings.append(
                    {
                        "mock_target": mock_target,
                        "issue": f"Cannot import spec class '{spec_class_path}' to verify",
                        "severity": "LOW",
                    }
                )
                continue

            for method in declared_methods:
                if method not in real_methods:
                    findings.append(
                        {
                            "mock_target": mock_target,
                            "issue": (
                                f"Method '{method}' does not exist on '{spec_class_path}'"
                            ),
                            "severity": "HIGH",
                        }
                    )

            # Check for methods on the real class not in the mock spec
            for method in real_methods:
                if method not in declared_methods and not method.startswith("_"):
                    findings.append(
                        {
                            "mock_target": mock_target,
                            "issue": (
                                f"Real method '{method}' on '{spec_class_path}' "
                                "is not declared in mock spec"
                            ),
                            "severity": "MEDIUM",
                        }
                    )

        return findings

    def find_signature_drift(self, source_code: str) -> list[dict]:
        """Find mocked return values that may not match current API.

        Looks for Mock(return_value=...) or mock.return_value = ... patterns
        and flags them as potential drift points.

        Returns:
            List of dicts with "line", "mock_target", "issue".
        """
        findings: list[dict] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            # mock.return_value = something
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "return_value":
                        mock_name = self._attr_to_str(target.value)
                        findings.append(
                            {
                                "line": node.lineno,
                                "mock_target": mock_name,
                                "issue": (
                                    "Hardcoded return_value may drift from real API; "
                                    "verify against current implementation."
                                ),
                            }
                        )

            # MagicMock(return_value=...) or patch(..., return_value=...)
            elif isinstance(node, ast.Call):
                func_name = self._call_func_name(node)
                if func_name in ("MagicMock", "Mock", "patch", "patch.object"):
                    for kw in node.keywords:
                        if kw.arg == "return_value":
                            findings.append(
                                {
                                    "line": node.lineno,
                                    "mock_target": func_name,
                                    "issue": (
                                        "return_value kwarg may drift from real API; "
                                        "verify the value matches current return type."
                                    ),
                                }
                            )

        return findings

    def find_unused_mocks(self, source_code: str) -> list[dict]:
        """Find mocks that are created but never asserted or used.

        Returns:
            List of dicts with "line", "mock_name", "suggestion".
        """
        findings: list[dict] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        for func_node in ast.walk(tree):
            if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            mock_assignments: dict[str, int] = {}  # name -> line
            # Names that appear as assignment targets (definition sites)
            assignment_target_names: set[str] = set()
            # Names used in value/load positions
            used_names: set[str] = set()

            for node in ast.walk(func_node):
                # Track: name = MagicMock() / Mock() / patch(...)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            assignment_target_names.add(target.id)
                            value = node.value
                            if self._is_mock_call(value):
                                mock_assignments[target.id] = node.lineno
                    # Collect names used on the RIGHT side of the assignment
                    for child in ast.walk(node.value):
                        if isinstance(child, ast.Name):
                            used_names.add(child.id)
                    continue

                # Track uses (attribute access on mock objects)
                if isinstance(node, ast.Attribute):
                    obj = self._attr_to_str(node.value)
                    if obj:
                        used_names.add(obj)

                # assert_called_with(mock), etc.
                if isinstance(node, ast.Call):
                    call_str = self._call_func_name(node)
                    if call_str.startswith("assert_"):
                        base = self._attr_to_str(
                            node.func.value
                            if isinstance(node.func, ast.Attribute)
                            else node.func
                        )
                        if base:
                            used_names.add(base)
                    # Names passed as arguments
                    for arg in node.args:
                        if isinstance(arg, ast.Name):
                            used_names.add(arg.id)

                # Generic Name in load context (not assignment target)
                if isinstance(node, ast.Name) and node.id not in assignment_target_names:
                    used_names.add(node.id)

            for mock_name, line_no in mock_assignments.items():
                if mock_name not in used_names:
                    findings.append(
                        {
                            "line": line_no,
                            "mock_name": mock_name,
                            "suggestion": (
                                f"Mock '{mock_name}' is created but never "
                                "asserted or referenced; consider removing it."
                            ),
                        }
                    )

        return findings

    def detect_over_mocking(self, source_code: str) -> list[dict]:
        """Find test functions that mock more than 5 things.

        Returns:
            List of dicts with "line", "test_name", "mock_count", "suggestion".
        """
        findings: list[dict] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue

            mock_count = 0

            # Count decorator patches
            for dec in node.decorator_list:
                if self._is_patch_decorator(dec):
                    mock_count += 1

            # Count Mock/MagicMock/patch calls in function body
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Name):
                            if self._is_mock_call(child.value):
                                mock_count += 1

                if isinstance(child, ast.Call):
                    func_name = self._call_func_name(child)
                    if func_name in ("patch", "patch.object", "patch.dict"):
                        mock_count += 1

            if mock_count > 5:
                findings.append(
                    {
                        "line": node.lineno,
                        "test_name": node.name,
                        "mock_count": mock_count,
                        "suggestion": (
                            f"'{node.name}' uses {mock_count} mocks (>5). "
                            "Consider splitting into smaller, focused tests or "
                            "introducing a test fixture / factory."
                        ),
                    }
                )

        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_real_methods(self, class_path: str) -> list[str] | None:
        """Import a class and return its public method names."""
        try:
            parts = class_path.rsplit(".", 1)
            if len(parts) != 2:
                return None
            module_path, class_name = parts
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            return [
                name
                for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
            ]
        except Exception:
            return None

    def _attr_to_str(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._attr_to_str(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ""

    def _call_func_name(self, call: ast.Call) -> str:
        if isinstance(call.func, ast.Name):
            return call.func.id
        if isinstance(call.func, ast.Attribute):
            return call.func.attr
        return ""

    def _is_mock_call(self, node: ast.expr) -> bool:
        if not isinstance(node, ast.Call):
            return False
        name = self._call_func_name(node)
        return name in ("Mock", "MagicMock", "AsyncMock", "NonCallableMock", "patch")

    def _is_patch_decorator(self, dec: ast.expr) -> bool:
        if isinstance(dec, ast.Call):
            name = self._call_func_name(dec)
            return name in ("patch", "patch.object", "patch.dict")
        if isinstance(dec, ast.Attribute):
            return dec.attr == "patch"
        if isinstance(dec, ast.Name):
            return dec.id == "patch"
        return False
