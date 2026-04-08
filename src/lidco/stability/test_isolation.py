"""
Test Isolation Enforcer.

Detects shared state, global mutations, fixture leaks, and missing
setUp/tearDown pairing in Python test source code.
"""
from __future__ import annotations

import ast
import re


class TestIsolationEnforcer:
    """Analyzes Python test source for isolation problems."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_shared_state(self, source_code: str) -> list[dict]:
        """Detect module-level mutable variables and class-level lists/dicts.

        Returns:
            List of dicts with "line", "variable", "type", "risk".
        """
        findings: list[dict] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        lines = source_code.splitlines()

        # Module-level mutable assignments
        for node in ast.walk(tree):
            if not isinstance(node, ast.Module):
                continue
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            value = stmt.value
                            var_type, risk = self._classify_mutable(value)
                            if var_type:
                                findings.append(
                                    {
                                        "line": stmt.lineno,
                                        "variable": target.id,
                                        "type": "module_global",
                                        "risk": risk,
                                    }
                                )

        # Class-level mutable attributes
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            value = stmt.value
                            var_type, risk = self._classify_mutable(value)
                            if var_type:
                                findings.append(
                                    {
                                        "line": stmt.lineno,
                                        "variable": target.id,
                                        "type": "class_variable",
                                        "risk": risk,
                                    }
                                )

        return findings

    def find_global_mutations(self, source_code: str) -> list[dict]:
        """Find code that mutates global state.

        Detects:
        - os.environ modifications
        - sys.path modifications
        - global keyword usage

        Returns:
            List of dicts with "line", "target", "mutation_type", "suggestion".
        """
        findings: list[dict] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            # global keyword usage
            if isinstance(node, ast.Global):
                for name in node.names:
                    findings.append(
                        {
                            "line": node.lineno,
                            "target": name,
                            "mutation_type": "global_keyword",
                            "suggestion": (
                                f"Avoid 'global {name}'; pass state as parameter or use fixtures."
                            ),
                        }
                    )

            # Subscript assignment: os.environ['KEY'] = val  or  sys.path[...] = val
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    attr_str = self._attr_to_str(target)
                    if attr_str and self._is_global_mutation_target(attr_str):
                        mut_type, suggestion = self._global_mutation_info(attr_str)
                        findings.append(
                            {
                                "line": node.lineno,
                                "target": attr_str,
                                "mutation_type": mut_type,
                                "suggestion": suggestion,
                            }
                        )

            # Augmented assignment: sys.path += [...]
            elif isinstance(node, ast.AugAssign):
                attr_str = self._attr_to_str(node.target)
                if attr_str and self._is_global_mutation_target(attr_str):
                    mut_type, suggestion = self._global_mutation_info(attr_str)
                    findings.append(
                        {
                            "line": node.lineno,
                            "target": attr_str,
                            "mutation_type": mut_type,
                            "suggestion": suggestion,
                        }
                    )

            # Method calls: os.environ.update/pop, sys.path.append/insert/extend
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                call_str = self._call_to_str(call)
                if call_str and self._is_global_mutation_call(call_str):
                    mut_type, suggestion = self._global_mutation_info(call_str)
                    findings.append(
                        {
                            "line": node.lineno,
                            "target": call_str,
                            "mutation_type": mut_type,
                            "suggestion": suggestion,
                        }
                    )

        return findings

    def detect_fixture_leaks(self, source_code: str) -> list[dict]:
        """Find fixtures that don't clean up resources.

        Looks for pytest fixtures (functions decorated with @pytest.fixture or
        @fixture) that either:
        - contain resource-opening calls but no yield
        - have a yield but no code after the yield (no teardown)

        Returns:
            List of dicts with "line", "fixture_name", "issue", "fix".
        """
        findings: list[dict] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not self._has_fixture_decorator(node):
                continue

            func_name = node.name
            has_yield = self._has_yield(node)
            has_teardown = self._has_teardown_after_yield(node)
            opens_resource = self._opens_resource(node)
            has_context_manager = self._has_context_manager_with(node)

            if opens_resource and not has_yield and not has_context_manager:
                findings.append(
                    {
                        "line": node.lineno,
                        "fixture_name": func_name,
                        "issue": "Opens resource but has no yield-based cleanup",
                        "fix": (
                            "Use 'yield' to separate setup from teardown, "
                            "then close the resource after yield."
                        ),
                    }
                )
            elif has_yield and not has_teardown:
                findings.append(
                    {
                        "line": node.lineno,
                        "fixture_name": func_name,
                        "issue": "yield-based fixture has no teardown code after yield",
                        "fix": "Add cleanup code after the yield statement.",
                    }
                )

        return findings

    def verify_cleanup(self, source_code: str) -> list[dict]:
        """Verify setUp/tearDown methods are properly paired.

        Returns:
            List of dicts with "line", "method", "status", "suggestion".
        """
        findings: list[dict] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            method_names = {
                stmt.name
                for stmt in node.body
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            method_map = {
                stmt.name: stmt
                for stmt in node.body
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

            # Check setUp / tearDown pairing
            if "setUp" in method_names:
                stmt = method_map["setUp"]
                if "tearDown" not in method_names:
                    findings.append(
                        {
                            "line": stmt.lineno,
                            "method": "setUp",
                            "status": "missing_cleanup",
                            "suggestion": (
                                f"Class '{node.name}' has setUp but no tearDown. "
                                "Add tearDown to release resources."
                            ),
                        }
                    )
                else:
                    findings.append(
                        {
                            "line": stmt.lineno,
                            "method": "setUp",
                            "status": "ok",
                            "suggestion": "",
                        }
                    )

            if "tearDown" in method_names:
                stmt = method_map["tearDown"]
                if "setUp" not in method_names:
                    findings.append(
                        {
                            "line": stmt.lineno,
                            "method": "tearDown",
                            "status": "missing_cleanup",
                            "suggestion": (
                                f"Class '{node.name}' has tearDown but no setUp."
                            ),
                        }
                    )
                else:
                    findings.append(
                        {
                            "line": stmt.lineno,
                            "method": "tearDown",
                            "status": "ok",
                            "suggestion": "",
                        }
                    )

            # setUpClass / tearDownClass
            if "setUpClass" in method_names and "tearDownClass" not in method_names:
                stmt = method_map["setUpClass"]
                findings.append(
                    {
                        "line": stmt.lineno,
                        "method": "setUpClass",
                        "status": "missing_cleanup",
                        "suggestion": (
                            f"Class '{node.name}' has setUpClass but no tearDownClass."
                        ),
                    }
                )

        return findings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _classify_mutable(self, value_node: ast.expr) -> tuple[str, str]:
        """Return (type_label, risk) for mutable nodes, or ('', '') otherwise."""
        if isinstance(value_node, ast.List):
            return ("list", "HIGH")
        if isinstance(value_node, ast.Dict):
            return ("dict", "HIGH")
        if isinstance(value_node, ast.Set):
            return ("set", "HIGH")
        if isinstance(value_node, ast.Call):
            func = value_node.func
            func_name = ""
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            if func_name in ("list", "dict", "set", "defaultdict", "OrderedDict"):
                return (func_name, "HIGH")
        return ("", "")

    def _attr_to_str(self, node: ast.expr) -> str:
        """Convert an AST attribute/subscript node to a dotted string."""
        if isinstance(node, ast.Attribute):
            parent = self._attr_to_str(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Subscript):
            parent = self._attr_to_str(node.value)
            return parent
        return ""

    def _call_to_str(self, call: ast.Call) -> str:
        """Convert a Call node's function to a dotted string."""
        return self._attr_to_str(call.func)

    def _is_global_mutation_target(self, attr_str: str) -> bool:
        return any(
            attr_str.startswith(prefix)
            for prefix in ("os.environ", "sys.path", "sys.modules")
        )

    def _is_global_mutation_call(self, call_str: str) -> bool:
        return any(
            call_str.startswith(prefix)
            for prefix in (
                "os.environ.update",
                "os.environ.pop",
                "os.environ.setdefault",
                "sys.path.append",
                "sys.path.insert",
                "sys.path.extend",
                "sys.path.remove",
            )
        )

    def _global_mutation_info(self, target: str) -> tuple[str, str]:
        if "environ" in target:
            return (
                "env_mutation",
                "Use monkeypatch.setenv() or unittest.mock.patch.dict(os.environ, ...) instead.",
            )
        if "sys.path" in target:
            return (
                "sys_path_mutation",
                "Use importlib or tmp_path fixtures rather than modifying sys.path directly.",
            )
        if "sys.modules" in target:
            return (
                "sys_modules_mutation",
                "Restore sys.modules in tearDown if you must modify it.",
            )
        return ("global_mutation", "Avoid mutating global state in tests.")

    def _has_fixture_decorator(self, node: ast.FunctionDef) -> bool:
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "fixture":
                return True
            if isinstance(dec, ast.Attribute) and dec.attr == "fixture":
                return True
            if isinstance(dec, ast.Call):
                func = dec.func
                if isinstance(func, ast.Name) and func.id == "fixture":
                    return True
                if isinstance(func, ast.Attribute) and func.attr == "fixture":
                    return True
        return False

    def _has_yield(self, node: ast.FunctionDef) -> bool:
        for child in ast.walk(node):
            if isinstance(child, (ast.Yield, ast.YieldFrom)):
                return True
        return False

    def _has_teardown_after_yield(self, node: ast.FunctionDef) -> bool:
        """Check if there is code after the yield statement in the function body."""
        body = node.body
        for i, stmt in enumerate(body):
            if self._stmt_contains_yield(stmt):
                # There must be at least one more statement after this
                return i < len(body) - 1
        return False

    def _stmt_contains_yield(self, stmt: ast.stmt) -> bool:
        for child in ast.walk(stmt):
            if isinstance(child, (ast.Yield, ast.YieldFrom)):
                return True
        return False

    def _opens_resource(self, node: ast.FunctionDef) -> bool:
        """Check if function calls open(), connect(), or similar resource openers."""
        resource_calls = {"open", "connect", "socket", "Session", "cursor"}
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func_name = ""
                if isinstance(child.func, ast.Name):
                    func_name = child.func.id
                elif isinstance(child.func, ast.Attribute):
                    func_name = child.func.attr
                if func_name in resource_calls:
                    return True
        return False

    def _has_context_manager_with(self, node: ast.FunctionDef) -> bool:
        for child in ast.walk(node):
            if isinstance(child, (ast.With, ast.AsyncWith)):
                return True
        return False
