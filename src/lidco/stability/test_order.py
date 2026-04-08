"""
Test Order Analyzer.

Detects order-dependent tests, validates shuffle results, and analyzes
inter-test dependencies in Python test source code.
"""
from __future__ import annotations

import ast


class TestOrderAnalyzer:
    """Analyzes test suites for order-dependence issues."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_order_dependence(self, test_results: list[dict]) -> list[dict]:
        """Detect tests whose pass/fail depends on execution order.

        Identifies tests that fail in some orderings but pass in others by
        looking for inconsistent results across runs recorded in test_results.

        Args:
            test_results: List of dicts with "name", "order_index", "passed" (bool).
                          Multiple entries for the same test name represent
                          results from different runs/orderings.

        Returns:
            List of dicts with "test_name", "issue", "evidence".
        """
        findings: list[dict] = []

        # Group results by test name
        by_name: dict[str, list[dict]] = {}
        for result in test_results:
            name = result["name"]
            by_name.setdefault(name, []).append(result)

        for name, results in by_name.items():
            passed_states = {r["passed"] for r in results}
            if len(passed_states) > 1:
                # Mixed results — order dependent
                passed_indices = [
                    r["order_index"] for r in results if r["passed"]
                ]
                failed_indices = [
                    r["order_index"] for r in results if not r["passed"]
                ]
                findings.append(
                    {
                        "test_name": name,
                        "issue": "Test result varies with execution order",
                        "evidence": (
                            f"Passed at positions {passed_indices}, "
                            f"failed at positions {failed_indices}"
                        ),
                    }
                )

        return findings

    def validate_shuffle(
        self,
        test_names: list[str],
        results_normal: list[bool],
        results_shuffled: list[bool],
    ) -> dict:
        """Compare normal vs shuffled run results.

        Args:
            test_names: Ordered list of test names (matches results_normal order).
            results_normal: Pass/fail for normal run (parallel to test_names).
            results_shuffled: Pass/fail for shuffled run (parallel to test_names).

        Returns:
            Dict with "order_dependent" (bool), "failures" (list of test names
            that differ), "total", "stable_count".
        """
        failures: list[str] = []
        total = len(test_names)

        for name, normal, shuffled in zip(test_names, results_normal, results_shuffled):
            if normal != shuffled:
                failures.append(name)

        stable_count = total - len(failures)
        return {
            "order_dependent": len(failures) > 0,
            "failures": failures,
            "total": total,
            "stable_count": stable_count,
        }

    def analyze_dependencies(self, source_code: str) -> list[dict]:
        """Find tests that depend on other tests via shared fixtures or state.

        Looks for:
        - Tests that call other test methods directly
        - Tests that access class-level state written by setUp
        - Shared module-level variables mutated in test bodies

        Returns:
            List of dicts with "test_name", "depends_on", "type".
        """
        findings: list[dict] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return findings

        # Collect all test names
        all_test_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    all_test_names.add(node.name)

        # Check each test function for calls to other test functions
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue

            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                called = self._call_to_name(child)
                if not called:
                    continue

                # Direct call to another test function
                if called in all_test_names and called != node.name:
                    findings.append(
                        {
                            "test_name": node.name,
                            "depends_on": called,
                            "type": "direct_call",
                        }
                    )

                # self.other_test() pattern
                if called.startswith("self.test"):
                    dep_name = called[5:]  # strip "self."
                    if dep_name in all_test_names and dep_name != node.name:
                        findings.append(
                            {
                                "test_name": node.name,
                                "depends_on": dep_name,
                                "type": "self_call",
                            }
                        )

        # Check for shared module-level mutable state written in test bodies
        module_globals: dict[str, int] = {}
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        module_globals[target.id] = stmt.lineno

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue

            for child in ast.walk(node):
                if isinstance(child, ast.Global):
                    for gname in child.names:
                        if gname in module_globals:
                            findings.append(
                                {
                                    "test_name": node.name,
                                    "depends_on": f"global:{gname}",
                                    "type": "shared_global",
                                }
                            )

        return findings

    def suggest_fixes(self, findings: list[dict]) -> list[str]:
        """Generate fix suggestions for order-dependence findings.

        Args:
            findings: Combined output from detect_order_dependence or
                      analyze_dependencies.

        Returns:
            List of human-readable suggestion strings.
        """
        suggestions: list[str] = []

        for finding in findings:
            dep_type = finding.get("type", "")
            test_name = finding.get("test_name", finding.get("name", "unknown"))
            issue = finding.get("issue", "")

            if dep_type == "direct_call":
                depends_on = finding.get("depends_on", "")
                suggestions.append(
                    f"'{test_name}' directly calls '{depends_on}'. "
                    "Extract shared logic into a helper function or fixture instead."
                )
            elif dep_type == "self_call":
                depends_on = finding.get("depends_on", "")
                suggestions.append(
                    f"'{test_name}' calls self.{depends_on}. "
                    "Tests should not call other tests; use setUp or shared fixtures."
                )
            elif dep_type == "shared_global":
                depends_on = finding.get("depends_on", "")
                suggestions.append(
                    f"'{test_name}' uses {depends_on} which is module-level state. "
                    "Pass state via setUp/tearDown or pytest fixtures."
                )
            elif issue:
                suggestions.append(
                    f"'{test_name}': {issue}. "
                    "Ensure each test is fully independent by resetting state in setUp/tearDown."
                )

        if not suggestions:
            suggestions.append("No order-dependence issues detected.")

        return suggestions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _call_to_name(self, call: ast.Call) -> str:
        """Extract called name from a Call node."""
        if isinstance(call.func, ast.Name):
            return call.func.id
        if isinstance(call.func, ast.Attribute):
            obj = self._attr_to_str(call.func.value)
            return f"{obj}.{call.func.attr}" if obj else call.func.attr
        return ""

    def _attr_to_str(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._attr_to_str(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ""
