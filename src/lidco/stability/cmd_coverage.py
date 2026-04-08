"""
Command Coverage Tracker.

Maps slash commands to their test files, identifies untested commands,
generates test stubs, and computes coverage percentage.
"""
from __future__ import annotations

import re


class CommandCoverageTracker:
    """Tracks which slash commands have test coverage."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map_commands_to_tests(
        self,
        commands: list[str],
        test_files: dict[str, str],
    ) -> dict:
        """Map command names to test files that test them.

        A test file is considered to test a command when it contains a
        reference to the command name (typically as a string or in a handler
        invocation).  Hyphens are also matched as underscores.

        Args:
            commands: List of command name strings (e.g. ["cmd-dedup", ...]).
            test_files: Dict mapping filename -> file content.

        Returns:
            Dict mapping command_name -> list of test file names that test it.
        """
        mapping: dict[str, list[str]] = {cmd: [] for cmd in commands}

        for cmd in commands:
            # Build patterns: exact name and hyphen/underscore variant
            variants = {cmd, cmd.replace("-", "_"), cmd.replace("_", "-")}
            patterns = [re.compile(re.escape(v)) for v in variants]

            for filename, content in test_files.items():
                for pat in patterns:
                    if pat.search(content):
                        mapping[cmd].append(filename)
                        break  # count file once per command

        return mapping

    def find_untested(
        self,
        commands: list[str],
        test_files: dict[str, str],
    ) -> list[str]:
        """Return list of command names that have no tests.

        Args:
            commands: List of command name strings.
            test_files: Dict mapping filename -> file content.

        Returns:
            List of command names with no matching test files.
        """
        mapping = self.map_commands_to_tests(commands, test_files)
        return [cmd for cmd, files in mapping.items() if not files]

    def generate_test_stubs(self, untested: list[str]) -> str:
        """Generate test stub code for untested commands.

        Args:
            untested: List of command names that need tests.

        Returns:
            Python source code string with test stubs.
        """
        if not untested:
            return "# All commands have test coverage — no stubs needed.\n"

        lines: list[str] = [
            '"""Auto-generated test stubs for untested slash commands."""',
            "from __future__ import annotations",
            "",
            "import asyncio",
            "import unittest",
            "",
            "",
            "def _run(coro):",
            "    return asyncio.run(coro)",
            "",
            "",
        ]

        for cmd in untested:
            class_name = "Test" + "".join(
                part.capitalize() for part in re.split(r"[-_]", cmd)
            ) + "Cmd"
            handler_var = cmd.replace("-", "_")
            lines += [
                f"class {class_name}(unittest.TestCase):",
                f'    """Stub tests for /{cmd} command."""',
                "",
                "    def setUp(self):",
                "        # TODO: import and register the relevant commands module",
                "        # from lidco.cli.commands.qXXX_cmds import register_qXXX_commands",
                "        # reg = _FakeRegistry()",
                "        # register_qXXX_commands(reg)",
                f"        # self.handler = reg.commands['{cmd}'][1]",
                "        self.handler = None",
                "",
                "    def test_no_args(self):",
                f'        """/{cmd} with no args should return usage text."""',
                "        if self.handler is None:",
                "            self.skipTest('handler not wired')",
                "        result = _run(self.handler(''))",
                "        self.assertIsInstance(result, str)",
                "",
                "    def test_basic_invocation(self):",
                f'        """/{cmd} should handle a basic invocation."""',
                "        if self.handler is None:",
                "            self.skipTest('handler not wired')",
                "        result = _run(self.handler('--help'))",
                "        self.assertIsInstance(result, str)",
                "",
                "",
            ]

        lines.append("if __name__ == '__main__':")
        lines.append("    unittest.main()")
        lines.append("")

        return "\n".join(lines)

    def coverage_percentage(
        self,
        commands: list[str],
        test_files: dict[str, str],
    ) -> float:
        """Return percentage of commands that have tests (0.0 – 100.0).

        Args:
            commands: List of command name strings.
            test_files: Dict mapping filename -> file content.

        Returns:
            Float between 0.0 and 100.0.
        """
        if not commands:
            return 100.0

        mapping = self.map_commands_to_tests(commands, test_files)
        tested = sum(1 for files in mapping.values() if files)
        return (tested / len(commands)) * 100.0
