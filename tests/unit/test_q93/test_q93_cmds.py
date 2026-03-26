"""Tests for T601 Q93 CLI commands."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest


def _make_registry():
    """Create a minimal mock registry with async registration support."""
    registry = MagicMock()
    registered: dict[str, object] = {}

    def register_async(name, desc, handler):
        registered[name] = handler

    registry.register_async.side_effect = register_async
    registry._handlers = registered
    return registry


def _get_handler(registry, name):
    return registry._handlers[name]


class TestRegisterQ93Commands:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q93_cmds import register_q93_commands
        registry = _make_registry()
        register_q93_commands(registry)
        assert "playbook" in registry._handlers
        assert "test-impact" in registry._handlers
        assert "ai-blame" in registry._handlers
        assert "pr-desc" in registry._handlers


# ---------------------------------------------------------------------------
# /playbook
# ---------------------------------------------------------------------------

class TestPlaybookCommand:
    def _register(self):
        from lidco.cli.commands.q93_cmds import register_q93_commands
        registry = _make_registry()
        register_q93_commands(registry)
        return _get_handler(registry, "playbook")

    def test_list_no_playbooks(self):
        handler = self._register()
        with patch("lidco.playbooks.engine.PlaybookEngine.list", return_value=[]):
            result = asyncio.run(handler("list"))
        assert "No playbooks" in result

    def test_list_with_playbooks(self):
        handler = self._register()
        from lidco.playbooks.engine import Playbook
        fake = Playbook(name="deploy", description="Deploy app", steps=[])
        with patch("lidco.playbooks.engine.PlaybookEngine.list", return_value=[fake]):
            result = asyncio.run(handler("list"))
        assert "deploy" in result
        assert "Deploy app" in result

    def test_show_unknown_name(self):
        handler = self._register()
        with patch(
            "lidco.playbooks.engine.PlaybookEngine.load",
            side_effect=KeyError("Playbook 'nope' not found. Available: (none)"),
        ):
            result = asyncio.run(handler("show nope"))
        assert "not found" in result

    def test_show_playbook(self):
        handler = self._register()
        from lidco.playbooks.engine import Playbook, PlaybookStep
        fake = Playbook(
            name="deploy",
            description="Deploy",
            steps=[PlaybookStep(type="run", command="echo hi")],
        )
        with patch("lidco.playbooks.engine.PlaybookEngine.load", return_value=fake):
            result = asyncio.run(handler("show deploy"))
        assert "deploy" in result.lower()
        assert "echo hi" in result

    def test_run_unknown_name(self):
        handler = self._register()
        with patch(
            "lidco.playbooks.engine.PlaybookEngine.execute",
            side_effect=KeyError("Playbook 'x' not found. Available: (none)"),
        ):
            result = asyncio.run(handler("run x"))
        assert "not found" in result

    def test_run_success(self):
        handler = self._register()
        from lidco.playbooks.engine import PlaybookResult
        fake_result = PlaybookResult(
            name="deploy", steps_completed=2, steps_total=2, success=True
        )
        with patch("lidco.playbooks.engine.PlaybookEngine.execute", return_value=fake_result):
            result = asyncio.run(handler("run deploy"))
        assert "succeeded" in result

    def test_run_failure(self):
        handler = self._register()
        from lidco.playbooks.engine import PlaybookResult, StepResult
        fake_result = PlaybookResult(
            name="deploy",
            steps_completed=0,
            steps_total=2,
            success=False,
            step_results=[StepResult(0, "run", False, error="oops")],
        )
        with patch("lidco.playbooks.engine.PlaybookEngine.execute", return_value=fake_result):
            result = asyncio.run(handler("run deploy"))
        assert "failed" in result

    def test_run_parses_key_value_args(self):
        handler = self._register()
        from lidco.playbooks.engine import PlaybookResult
        fake_result = PlaybookResult(
            name="deploy", steps_completed=1, steps_total=1, success=True
        )
        captured = {}
        def fake_execute(name, variables=None):
            captured["variables"] = variables
            return fake_result

        with patch("lidco.playbooks.engine.PlaybookEngine.execute", side_effect=fake_execute):
            asyncio.run(handler("run deploy env=prod region=us"))

        assert captured["variables"].get("env") == "prod"
        assert captured["variables"].get("region") == "us"

    def test_no_subcommand_shows_list_or_usage(self):
        handler = self._register()
        with patch("lidco.playbooks.engine.PlaybookEngine.list", return_value=[]):
            result = asyncio.run(handler(""))
        # Empty args → list subcommand
        assert "playbook" in result.lower() or "Usage" in result


# ---------------------------------------------------------------------------
# /test-impact
# ---------------------------------------------------------------------------

class TestTestImpactCommand:
    def _register(self):
        from lidco.cli.commands.q93_cmds import register_q93_commands
        registry = _make_registry()
        register_q93_commands(registry)
        return _get_handler(registry, "test-impact")

    def _fake_result(self, affected=None, skipped=None):
        from lidco.testing.impact_analyzer import ImpactResult
        return ImpactResult(
            changed_files=["src/foo.py"],
            affected_tests=affected or ["tests/test_foo.py"],
            skipped_tests=skipped or [],
            coverage_estimate=0.5,
        )

    def test_shows_summary(self):
        handler = self._register()
        with patch(
            "lidco.testing.impact_analyzer.TestImpactAnalyzer.analyze_since",
            return_value=self._fake_result(),
        ):
            result = asyncio.run(handler(""))
        assert "Affected tests" in result
        assert "Skipped tests" in result

    def test_shows_minimal_command(self):
        handler = self._register()
        with patch(
            "lidco.testing.impact_analyzer.TestImpactAnalyzer.analyze_since",
            return_value=self._fake_result(),
        ):
            result = asyncio.run(handler(""))
        assert "python -m pytest" in result

    def test_since_flag_passed(self):
        handler = self._register()
        called_with = {}
        def fake_since(ref):
            called_with["ref"] = ref
            return self._fake_result()

        with patch(
            "lidco.testing.impact_analyzer.TestImpactAnalyzer.analyze_since",
            side_effect=fake_since,
        ):
            asyncio.run(handler("--since HEAD~3"))

        assert called_with["ref"] == "HEAD~3"

    def test_changed_files_args(self):
        handler = self._register()
        called_with = {}
        def fake_analyze(cs):
            called_with["cs"] = cs
            return self._fake_result()

        with patch(
            "lidco.testing.impact_analyzer.TestImpactAnalyzer.analyze",
            side_effect=fake_analyze,
        ):
            asyncio.run(handler("src/foo.py src/bar.py"))

        assert "src/foo.py" in called_with["cs"].files


# ---------------------------------------------------------------------------
# /ai-blame
# ---------------------------------------------------------------------------

class TestAiBlameCommand:
    def _register(self):
        from lidco.cli.commands.q93_cmds import register_q93_commands
        registry = _make_registry()
        register_q93_commands(registry)
        return _get_handler(registry, "ai-blame")

    def _fake_entries(self):
        from lidco.git.ai_blame import BlameEntry
        return [
            BlameEntry(
                file="foo.py",
                line_start=1,
                line_end=10,
                author="Alice",
                commit="abc12345",
                date="2026-01-01",
                message="Add feature",
                ai_explanation="This adds the core feature.",
            )
        ]

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_shows_blame_output(self):
        handler = self._register()
        with patch(
            "lidco.git.ai_blame.AIBlameAnalyzer.analyze_file",
            return_value=self._fake_entries(),
        ):
            result = asyncio.run(handler("foo.py"))
        assert "Alice" in result
        assert "Add feature" in result

    def test_shows_ai_explanation(self):
        handler = self._register()
        with patch(
            "lidco.git.ai_blame.AIBlameAnalyzer.analyze_file",
            return_value=self._fake_entries(),
        ):
            result = asyncio.run(handler("foo.py"))
        assert "core feature" in result

    def test_no_blame_data(self):
        handler = self._register()
        with patch("lidco.git.ai_blame.AIBlameAnalyzer.analyze_file", return_value=[]):
            result = asyncio.run(handler("foo.py"))
        assert "No blame data" in result

    def test_line_range_parsed(self):
        handler = self._register()
        called_with = {}
        def fake_analyze(path, line_range=None):
            called_with["range"] = line_range
            return self._fake_entries()

        with patch("lidco.git.ai_blame.AIBlameAnalyzer.analyze_file", side_effect=fake_analyze):
            asyncio.run(handler("foo.py 10-20"))

        assert called_with["range"] == (10, 20)


# ---------------------------------------------------------------------------
# /pr-desc
# ---------------------------------------------------------------------------

class TestPrDescCommand:
    def _register(self):
        from lidco.cli.commands.q93_cmds import register_q93_commands
        registry = _make_registry()
        register_q93_commands(registry)
        return _get_handler(registry, "pr-desc")

    def _fake_desc(self):
        from lidco.git.pr_description import PRDescription
        return PRDescription(
            title="Add feature",
            summary=["Adds X"],
            changes=["Modified foo.py"],
            test_plan=["Run tests"],
            breaking_changes=[],
        )

    def test_default_format_markdown(self):
        handler = self._register()
        with patch(
            "lidco.git.pr_description.PRDescriptionGenerator.generate",
            return_value=self._fake_desc(),
        ):
            result = asyncio.run(handler(""))
        assert "## Add feature" in result

    def test_github_format(self):
        handler = self._register()
        with patch(
            "lidco.git.pr_description.PRDescriptionGenerator.generate",
            return_value=self._fake_desc(),
        ):
            result = asyncio.run(handler("--format github"))
        assert "## Summary" in result
        assert "LIDCO" in result

    def test_custom_base_branch(self):
        handler = self._register()
        called_with = {}
        def fake_generate(base_branch="main"):
            called_with["base"] = base_branch
            return self._fake_desc()

        with patch(
            "lidco.git.pr_description.PRDescriptionGenerator.generate",
            side_effect=fake_generate,
        ):
            asyncio.run(handler("--base develop"))

        assert called_with["base"] == "develop"

    def test_exception_returns_error_message(self):
        handler = self._register()
        with patch(
            "lidco.git.pr_description.PRDescriptionGenerator.generate",
            side_effect=Exception("git not found"),
        ):
            result = asyncio.run(handler(""))
        assert "Error" in result
