"""Tests for CommandCoverageTracker (Q340 Task 4)."""
from __future__ import annotations

import unittest


class TestMapCommandsToTests(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_coverage import CommandCoverageTracker
        self.t = CommandCoverageTracker()

    def test_empty_commands_returns_empty_mapping(self):
        result = self.t.map_commands_to_tests([], {})
        self.assertEqual(result, {})

    def test_command_found_in_test_file(self):
        commands = ["cmd-dedup"]
        test_files = {"test_dedup.py": 'handler = reg.commands["cmd-dedup"]'}
        result = self.t.map_commands_to_tests(commands, test_files)
        self.assertIn("test_dedup.py", result["cmd-dedup"])

    def test_command_not_found_gives_empty_list(self):
        commands = ["missing-cmd"]
        test_files = {"test_other.py": "nothing relevant here"}
        result = self.t.map_commands_to_tests(commands, test_files)
        self.assertEqual(result["missing-cmd"], [])

    def test_hyphen_underscore_variant_matched(self):
        commands = ["cmd-dedup"]
        # File uses underscore variant
        test_files = {"test_x.py": "cmd_dedup handler test"}
        result = self.t.map_commands_to_tests(commands, test_files)
        self.assertIn("test_x.py", result["cmd-dedup"])

    def test_multiple_files_matched(self):
        commands = ["foo"]
        test_files = {
            "test_a.py": "foo handler",
            "test_b.py": "testing foo command",
        }
        result = self.t.map_commands_to_tests(commands, test_files)
        self.assertIn("test_a.py", result["foo"])
        self.assertIn("test_b.py", result["foo"])

    def test_file_counted_once_per_command(self):
        commands = ["foo"]
        test_files = {"test_a.py": "foo foo foo"}
        result = self.t.map_commands_to_tests(commands, test_files)
        self.assertEqual(result["foo"].count("test_a.py"), 1)


class TestFindUntested(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_coverage import CommandCoverageTracker
        self.t = CommandCoverageTracker()

    def test_all_tested(self):
        commands = ["foo", "bar"]
        test_files = {"t.py": "foo bar"}
        result = self.t.find_untested(commands, test_files)
        self.assertEqual(result, [])

    def test_some_untested(self):
        commands = ["foo", "baz"]
        test_files = {"t.py": "foo handler"}
        result = self.t.find_untested(commands, test_files)
        self.assertIn("baz", result)
        self.assertNotIn("foo", result)

    def test_all_untested(self):
        commands = ["x", "y"]
        test_files = {"t.py": "nothing here"}
        result = self.t.find_untested(commands, test_files)
        self.assertIn("x", result)
        self.assertIn("y", result)


class TestGenerateTestStubs(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_coverage import CommandCoverageTracker
        self.t = CommandCoverageTracker()

    def test_empty_untested_returns_no_stubs_needed(self):
        result = self.t.generate_test_stubs([])
        self.assertIn("no stubs needed", result.lower())

    def test_stub_generated_for_each_command(self):
        result = self.t.generate_test_stubs(["foo-bar", "baz"])
        self.assertIn("FooBarCmd", result)
        self.assertIn("BazCmd", result)

    def test_stub_contains_class_definition(self):
        result = self.t.generate_test_stubs(["my-cmd"])
        self.assertIn("class Test", result)
        self.assertIn("unittest.TestCase", result)

    def test_stub_contains_test_method(self):
        result = self.t.generate_test_stubs(["my-cmd"])
        self.assertIn("def test_", result)

    def test_stub_is_valid_python_syntax(self):
        import ast
        code = self.t.generate_test_stubs(["alpha", "beta-gamma"])
        try:
            ast.parse(code)
        except SyntaxError as e:
            self.fail(f"Generated stub has syntax error: {e}")


class TestCoveragePercentage(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_coverage import CommandCoverageTracker
        self.t = CommandCoverageTracker()

    def test_empty_commands_returns_100(self):
        result = self.t.coverage_percentage([], {})
        self.assertEqual(result, 100.0)

    def test_all_covered_returns_100(self):
        commands = ["foo", "bar"]
        test_files = {"t.py": "foo bar"}
        result = self.t.coverage_percentage(commands, test_files)
        self.assertEqual(result, 100.0)

    def test_none_covered_returns_0(self):
        commands = ["foo", "bar"]
        test_files = {"t.py": "nothing"}
        result = self.t.coverage_percentage(commands, test_files)
        self.assertEqual(result, 0.0)

    def test_half_covered_returns_50(self):
        commands = ["foo", "bar"]
        test_files = {"t.py": "foo"}
        result = self.t.coverage_percentage(commands, test_files)
        self.assertAlmostEqual(result, 50.0)

    def test_return_type_is_float(self):
        result = self.t.coverage_percentage(["x"], {"t.py": "x"})
        self.assertIsInstance(result, float)


if __name__ == "__main__":
    unittest.main()
