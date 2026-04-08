"""Tests for Q308 CLI commands."""

import asyncio
import unittest
from unittest.mock import patch, MagicMock


class _FakeRegistry:
    """Minimal registry to capture registrations."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = handler


def _build_registry() -> _FakeRegistry:
    from lidco.cli.commands.q308_cmds import register_q308_commands
    reg = _FakeRegistry()
    register_q308_commands(reg)
    return reg


class TestQ308Registration(unittest.TestCase):
    def test_registers_contributions(self):
        reg = _build_registry()
        self.assertIn("contributions", reg.commands)

    def test_registers_velocity(self):
        reg = _build_registry()
        self.assertIn("velocity", reg.commands)

    def test_registers_predict_churn(self):
        reg = _build_registry()
        self.assertIn("predict-churn", reg.commands)

    def test_registers_repo_health(self):
        reg = _build_registry()
        self.assertIn("repo-health", reg.commands)


class TestContributionsCommand(unittest.TestCase):
    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_contributions_default(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            stdout="abc|Alice|a@b.com|2026-03-01|feat\n5\t3\tsrc/x.py\n"
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["contributions"](""))
        self.assertIn("Contributions:", result)
        self.assertIn("Alice", result)

    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_contributions_with_since(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="")
        reg = _build_registry()
        result = asyncio.run(reg.commands["contributions"]("--since 2026-01-01"))
        self.assertIn("0 commits", result)

    @patch("lidco.gitanalytics.contributions.subprocess.run")
    def test_contributions_with_top(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="")
        reg = _build_registry()
        result = asyncio.run(reg.commands["contributions"]("--top 5"))
        self.assertIn("Contributions:", result)


class TestVelocityCommand(unittest.TestCase):
    @patch("lidco.gitanalytics.velocity.subprocess.run")
    def test_velocity_default(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            stdout="a1|A|a@b.com|2026-03-01T10:00:00+00:00\n"
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["velocity"](""))
        self.assertIn("Velocity", result)
        self.assertIn("Commits/day", result)

    @patch("lidco.gitanalytics.velocity.subprocess.run")
    def test_velocity_with_days(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="")
        reg = _build_registry()
        result = asyncio.run(reg.commands["velocity"]("--days 7"))
        self.assertIn("Velocity (7d)", result)


class TestPredictChurnCommand(unittest.TestCase):
    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_churn_default(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(
            stdout="abc|2026-03-01T10:00:00+00:00\nsrc/foo.py\n"
        )
        reg = _build_registry()
        result = asyncio.run(reg.commands["predict-churn"](""))
        self.assertIn("Churn prediction", result)

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_churn_empty(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="")
        reg = _build_registry()
        result = asyncio.run(reg.commands["predict-churn"](""))
        self.assertIn("No churn data", result)

    @patch("lidco.gitanalytics.churn_predictor.subprocess.run")
    def test_churn_with_flags(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="")
        reg = _build_registry()
        result = asyncio.run(reg.commands["predict-churn"]("--days 30 --top 5"))
        self.assertIn("No churn data", result)


class TestRepoHealthCommand(unittest.TestCase):
    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_health_default(self, mock_run: MagicMock):
        def side_effect(cmd, **kwargs):
            r = MagicMock()
            if "shortlog" in cmd:
                r.stdout = "  5\tDev1\n  3\tDev2\n"
            elif "--oneline" in cmd:
                r.stdout = "\n".join(f"a{i} m" for i in range(20))
            elif "--name-only" in cmd:
                r.stdout = "\n".join(f"f{i}.py" for i in range(5))
            else:
                r.stdout = ""
            return r
        mock_run.side_effect = side_effect

        reg = _build_registry()
        result = asyncio.run(reg.commands["repo-health"](""))
        self.assertIn("Repository Health:", result)

    @patch("lidco.gitanalytics.health.subprocess.run")
    def test_health_with_days(self, mock_run: MagicMock):
        mock_run.return_value = MagicMock(stdout="")
        reg = _build_registry()
        result = asyncio.run(reg.commands["repo-health"]("--days 7"))
        self.assertIn("Repository Health:", result)


if __name__ == "__main__":
    unittest.main()
