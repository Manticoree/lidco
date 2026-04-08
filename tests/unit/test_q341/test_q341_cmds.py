"""Tests for Q341 CLI commands (Tasks 1-4)."""
from __future__ import annotations

import asyncio
import json
import unittest


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = (description, handler)


def _run(coro):
    return asyncio.run(coro)


class TestQ341Registration(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q341_cmds import register_q341_commands
        self.reg = _FakeRegistry()
        register_q341_commands(self.reg)

    def test_all_commands_registered(self):
        expected = {"test-isolation", "mock-check", "test-order", "perf-guard"}
        self.assertEqual(set(self.reg.commands.keys()), expected)

    def test_all_descriptions_non_empty(self):
        for name, (desc, _) in self.reg.commands.items():
            self.assertTrue(len(desc) > 0, f"'{name}' has empty description")


class TestTestIsolationCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q341_cmds import register_q341_commands
        self.reg = _FakeRegistry()
        register_q341_commands(self.reg)
        self.handler = self.reg.commands["test-isolation"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_clean_source_no_issues(self):
        source = (
            "class MyTest:\n"
            "    def setUp(self): pass\n"
            "    def tearDown(self): pass\n"
        )
        result = _run(self.handler(source))
        self.assertIn("Test Isolation Report", result)

    def test_shared_state_detected_in_output(self):
        source = "SHARED = []\n"
        result = _run(self.handler(source))
        self.assertIn("SHARED", result)

    def test_global_mutation_detected(self):
        source = "os.environ['KEY'] = 'value'\n"
        result = _run(self.handler(source))
        self.assertIn("Global mutations", result)


class TestMockCheckCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q341_cmds import register_q341_commands
        self.reg = _FakeRegistry()
        register_q341_commands(self.reg)
        self.handler = self.reg.commands["mock-check"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_clean_code_no_issues(self):
        source = "def test_simple():\n    assert True\n"
        result = _run(self.handler(source))
        self.assertIn("Mock Integrity Report", result)

    def test_return_value_drift_detected(self):
        source = "mock_obj.return_value = 42\n"
        result = _run(self.handler(source))
        self.assertIn("Signature drift", result)

    def test_over_mocked_test_detected(self):
        mocks = "\n".join(f"    m{i} = MagicMock()" for i in range(6))
        source = f"def test_heavy():\n{mocks}\n"
        result = _run(self.handler(source))
        self.assertIn("Over-mocked", result)


class TestTestOrderCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q341_cmds import register_q341_commands
        self.reg = _FakeRegistry()
        register_q341_commands(self.reg)
        self.handler = self.reg.commands["test-order"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_invalid_json_returns_error(self):
        result = _run(self.handler("not-json"))
        self.assertIn("Error", result)

    def test_non_dict_json_returns_error(self):
        result = _run(self.handler("[1, 2, 3]"))
        self.assertIn("Error", result)

    def test_stable_results_no_dependence(self):
        data = json.dumps({
            "test_results": [
                {"name": "test_a", "order_index": 0, "passed": True},
                {"name": "test_a", "order_index": 1, "passed": True},
            ]
        })
        result = _run(self.handler(data))
        self.assertIn("No order-dependent", result)

    def test_flaky_test_detected(self):
        data = json.dumps({
            "test_results": [
                {"name": "test_flaky", "order_index": 0, "passed": True},
                {"name": "test_flaky", "order_index": 1, "passed": False},
            ]
        })
        result = _run(self.handler(data))
        self.assertIn("test_flaky", result)


class TestPerfGuardCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q341_cmds import register_q341_commands
        self.reg = _FakeRegistry()
        register_q341_commands(self.reg)
        self.handler = self.reg.commands["perf-guard"][1]

    def test_no_args_returns_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_help_flag_returns_usage(self):
        result = _run(self.handler("--help"))
        self.assertIn("Usage", result)

    def test_invalid_json_returns_error(self):
        result = _run(self.handler("not-json"))
        self.assertIn("Error", result)

    def test_slow_test_detected(self):
        data = json.dumps({
            "current_times": {"test_slow": 10.0},
            "slow_threshold": 5.0,
        })
        result = _run(self.handler(data))
        self.assertIn("test_slow", result)
        self.assertIn("Slow tests", result)

    def test_regression_detected(self):
        data = json.dumps({
            "current_times": {"test_a": 5.0},
            "previous_times": {"test_a": 1.0},
        })
        result = _run(self.handler(data))
        self.assertIn("test_a", result)
        self.assertIn("regressions", result)

    def test_parallelization_suggestion_shown(self):
        data = json.dumps({
            "current_times": {"a": 2.0, "b": 3.0},
            "num_workers": 2,
        })
        result = _run(self.handler(data))
        self.assertIn("Parallelization", result)


if __name__ == "__main__":
    unittest.main()
