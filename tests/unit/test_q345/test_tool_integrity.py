"""Tests for ToolRegistryIntegrity (Q345)."""
from __future__ import annotations

import unittest


def _checker():
    from lidco.stability.tool_integrity import ToolRegistryIntegrity
    return ToolRegistryIntegrity()


def _tool(name, has_run=True, has_description=True, permissions=None):
    return {
        "name": name,
        "has_run": has_run,
        "has_description": has_description,
        "permissions": permissions or [],
    }


class TestCheckCompleteness(unittest.TestCase):
    def test_all_complete_tools(self):
        tools = [
            _tool("file_read", permissions=["read"]),
            _tool("shell_exec", permissions=["execute"]),
        ]
        result = _checker().check_completeness(tools)
        self.assertTrue(result["complete"])
        self.assertEqual(result["missing_run"], [])
        self.assertEqual(result["missing_description"], [])
        self.assertEqual(result["total"], 2)

    def test_missing_run_detected(self):
        tools = [_tool("broken_tool", has_run=False)]
        result = _checker().check_completeness(tools)
        self.assertFalse(result["complete"])
        self.assertIn("broken_tool", result["missing_run"])

    def test_missing_description_detected(self):
        tools = [_tool("no_desc", has_description=False)]
        result = _checker().check_completeness(tools)
        self.assertFalse(result["complete"])
        self.assertIn("no_desc", result["missing_description"])

    def test_empty_registry_is_complete(self):
        result = _checker().check_completeness([])
        self.assertTrue(result["complete"])
        self.assertEqual(result["total"], 0)


class TestFindDuplicateNames(unittest.TestCase):
    def test_no_duplicates_returns_empty(self):
        tools = [_tool("alpha"), _tool("beta"), _tool("gamma")]
        dupes = _checker().find_duplicate_names(tools)
        self.assertEqual(dupes, [])

    def test_single_duplicate_detected(self):
        tools = [_tool("exec"), _tool("read"), _tool("exec")]
        dupes = _checker().find_duplicate_names(tools)
        self.assertEqual(len(dupes), 1)
        self.assertEqual(dupes[0]["name"], "exec")
        self.assertEqual(dupes[0]["count"], 2)
        self.assertEqual(dupes[0]["indices"], [0, 2])

    def test_multiple_duplicates_all_reported(self):
        tools = [_tool("a"), _tool("b"), _tool("a"), _tool("b"), _tool("c")]
        dupes = _checker().find_duplicate_names(tools)
        names = {d["name"] for d in dupes}
        self.assertIn("a", names)
        self.assertIn("b", names)
        self.assertNotIn("c", names)


class TestVerifyPermissions(unittest.TestCase):
    def test_valid_permissions_no_issues(self):
        tools = [_tool("reader", permissions=["read", "filesystem"])]
        issues = _checker().verify_permissions(tools)
        self.assertEqual(issues, [])

    def test_empty_permissions_flagged(self):
        tools = [_tool("anon_tool", permissions=[])]
        issues = _checker().verify_permissions(tools)
        self.assertEqual(len(issues), 1)
        self.assertIn("no permissions", issues[0]["issues"][0])

    def test_unknown_permission_flagged(self):
        tools = [_tool("weird_tool", permissions=["fly"])]
        issues = _checker().verify_permissions(tools)
        self.assertEqual(len(issues), 1)
        self.assertTrue(any("fly" in i for i in issues[0]["issues"]))

    def test_admin_mixed_with_others_flagged(self):
        tools = [_tool("super_tool", permissions=["admin", "read"])]
        issues = _checker().verify_permissions(tools)
        self.assertEqual(len(issues), 1)
        self.assertTrue(any("admin" in i for i in issues[0]["issues"]))

    def test_admin_alone_is_valid(self):
        tools = [_tool("super_tool", permissions=["admin"])]
        issues = _checker().verify_permissions(tools)
        self.assertEqual(issues, [])


class TestGenerateMatrix(unittest.TestCase):
    def test_matrix_contains_all_tools(self):
        tools = [
            _tool("reader", permissions=["read"]),
            _tool("writer", permissions=["write"]),
        ]
        matrix = _checker().generate_matrix(tools)
        self.assertIn("reader", matrix["tools"])
        self.assertIn("writer", matrix["tools"])

    def test_matrix_collects_all_permissions(self):
        tools = [
            _tool("a", permissions=["read", "filesystem"]),
            _tool("b", permissions=["write", "network"]),
        ]
        matrix = _checker().generate_matrix(tools)
        perms = matrix["permissions"]
        self.assertIn("read", perms)
        self.assertIn("write", perms)
        self.assertIn("filesystem", perms)
        self.assertIn("network", perms)

    def test_matrix_maps_tool_to_its_perms(self):
        tools = [_tool("exec", permissions=["execute", "shell"])]
        matrix = _checker().generate_matrix(tools)
        self.assertEqual(sorted(matrix["matrix"]["exec"]), ["execute", "shell"])

    def test_empty_tools_gives_empty_matrix(self):
        matrix = _checker().generate_matrix([])
        self.assertEqual(matrix["tools"], [])
        self.assertEqual(matrix["matrix"], {})


if __name__ == "__main__":
    unittest.main()
