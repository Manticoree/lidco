"""Tests for PublicApiFreezeChecker (Q345)."""
from __future__ import annotations

import unittest


def _checker():
    from lidco.stability.api_freeze import PublicApiFreezeChecker
    return PublicApiFreezeChecker()


def _api(*funcs):
    """Build an API dict from (name, params, return_type) tuples."""
    return {
        "functions": [
            {"name": n, "params": list(p), "return_type": r}
            for n, p, r in funcs
        ]
    }


class TestDetectBreakingChanges(unittest.TestCase):
    def test_identical_apis_have_no_changes(self):
        api = _api(("process", ["data"], "str"))
        result = _checker().detect_breaking_changes(api, api)
        self.assertEqual(result, [])

    def test_removed_function_is_breaking(self):
        old = _api(("process", ["data"], "str"), ("validate", ["v"], "bool"))
        new = _api(("process", ["data"], "str"))
        changes = _checker().detect_breaking_changes(old, new)
        self.assertTrue(any(c["change_type"] == "removed" for c in changes))
        self.assertTrue(any(c["severity"] == "BREAKING" for c in changes))
        self.assertTrue(any(c["function"] == "validate" for c in changes))

    def test_removed_param_is_breaking(self):
        old = _api(("fn", ["a", "b"], "None"))
        new = _api(("fn", ["a"], "None"))
        changes = _checker().detect_breaking_changes(old, new)
        param_removed = [c for c in changes if c["change_type"] == "param_removed"]
        self.assertEqual(len(param_removed), 1)
        self.assertIn("b", param_removed[0]["description"])

    def test_added_required_param_is_breaking(self):
        old = _api(("fn", ["a"], "None"))
        new = _api(("fn", ["a", "b"], "None"))
        changes = _checker().detect_breaking_changes(old, new)
        added = [c for c in changes if c["change_type"] == "param_added_required"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["severity"], "BREAKING")

    def test_return_type_change_is_warning(self):
        old = _api(("fn", ["a"], "str"))
        new = _api(("fn", ["a"], "int"))
        changes = _checker().detect_breaking_changes(old, new)
        ret_changes = [c for c in changes if c["change_type"] == "return_type_changed"]
        self.assertEqual(len(ret_changes), 1)
        self.assertEqual(ret_changes[0]["severity"], "WARNING")

    def test_added_function_produces_no_change(self):
        old = _api(("process", ["data"], "str"))
        new = _api(("process", ["data"], "str"), ("new_fn", [], "None"))
        changes = _checker().detect_breaking_changes(old, new)
        self.assertEqual(changes, [])

    def test_multiple_functions_multiple_changes(self):
        old = _api(("a", ["x"], "str"), ("b", ["y"], "int"))
        new = _api(("a", ["x", "z"], "str"))  # b removed, a gets new param
        changes = _checker().detect_breaking_changes(old, new)
        types = {c["change_type"] for c in changes}
        self.assertIn("removed", types)
        self.assertIn("param_added_required", types)


class TestTrackSignatures(unittest.TestCase):
    def test_extracts_public_function(self):
        code = "def process(data: str, timeout: int = 5) -> str:\n    return data\n"
        sigs = _checker().track_signatures(code)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0]["name"], "process")
        self.assertIn("data", sigs[0]["params"])
        self.assertEqual(sigs[0]["return_type"], "str")
        self.assertIsInstance(sigs[0]["line"], int)

    def test_skips_private_functions(self):
        code = "def _internal(): pass\ndef __dunder__(): pass\ndef public(): pass\n"
        sigs = _checker().track_signatures(code)
        names = [s["name"] for s in sigs]
        self.assertNotIn("_internal", names)
        self.assertNotIn("__dunder__", names)
        self.assertIn("public", names)

    def test_invalid_syntax_returns_empty(self):
        sigs = _checker().track_signatures("def broken(:")
        self.assertEqual(sigs, [])

    def test_no_return_annotation_gives_empty_string(self):
        code = "def greet(name):\n    pass\n"
        sigs = _checker().track_signatures(code)
        self.assertEqual(sigs[0]["return_type"], "")


class TestCheckDeprecations(unittest.TestCase):
    def test_deprecated_function_without_warning(self):
        code = (
            "def old_func():\n"
            '    """Deprecated: use new_func instead."""\n'
            "    return 1\n"
        )
        results = _checker().check_deprecations(code)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["has_warning"])
        self.assertIn("warnings.warn", results[0]["suggestion"])

    def test_deprecated_function_with_warning(self):
        code = (
            "import warnings\n"
            "def old_func():\n"
            '    """Deprecated: use new_func."""\n'
            '    warnings.warn("old_func is deprecated", DeprecationWarning)\n'
            "    return 1\n"
        )
        results = _checker().check_deprecations(code)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["has_warning"])

    def test_non_deprecated_function_not_reported(self):
        code = "def current_func():\n    return 42\n"
        results = _checker().check_deprecations(code)
        self.assertEqual(results, [])


class TestValidateSemver(unittest.TestCase):
    def test_breaking_change_requires_major_bump(self):
        result = _checker().validate_semver("1.2.0", "2.0.0", has_breaking=True)
        self.assertTrue(result["valid"])
        self.assertEqual(result["actual_bump"], "major")

    def test_minor_bump_with_breaking_is_invalid(self):
        result = _checker().validate_semver("1.2.0", "1.3.0", has_breaking=True)
        self.assertFalse(result["valid"])
        self.assertIn("major", result["suggestion"].lower())

    def test_patch_bump_without_breaking_is_valid(self):
        result = _checker().validate_semver("1.2.0", "1.2.1", has_breaking=False)
        self.assertTrue(result["valid"])

    def test_result_contains_old_and_new_versions(self):
        result = _checker().validate_semver("1.0.0", "1.1.0", has_breaking=False)
        self.assertEqual(result["old"], "1.0.0")
        self.assertEqual(result["new"], "1.1.0")


if __name__ == "__main__":
    unittest.main()
