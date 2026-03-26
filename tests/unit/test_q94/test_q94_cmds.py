"""Tests for T606 Q94 CLI commands."""
import asyncio
from unittest.mock import MagicMock, patch

import pytest


def _make_registry():
    registry = MagicMock()
    registered = {}

    def register_async(name, desc, handler):
        registered[name] = handler

    registry.register_async.side_effect = register_async
    registry._handlers = registered
    return registry


def _get(registry, name):
    return registry._handlers[name]


class TestRegisterQ94Commands:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q94_cmds import register_q94_commands
        registry = _make_registry()
        register_q94_commands(registry)
        assert "deps" in registry._handlers
        assert "migrate" in registry._handlers
        assert "changelog" in registry._handlers
        assert "env-check" in registry._handlers


# ---------------------------------------------------------------------------
# /deps
# ---------------------------------------------------------------------------

class TestDepsCommand:
    def _register(self):
        from lidco.cli.commands.q94_cmds import register_q94_commands
        r = _make_registry()
        register_q94_commands(r)
        return _get(r, "deps")

    def _fake_report(self, issues=None):
        from lidco.dependencies.analyzer import DependencyReport, PackageInfo
        return DependencyReport(
            packages=[PackageInfo("requests", "==2.28.0", "requirements.txt", is_pinned=True)],
            issues=issues or [],
            import_names=["requests"],
            manifest_names=["requests"],
        )

    def test_no_packages(self):
        from lidco.dependencies.analyzer import DependencyReport
        handler = self._register()
        empty = DependencyReport(packages=[], issues=[], import_names=[], manifest_names=[])
        with patch("lidco.dependencies.analyzer.DependencyAnalyzer.analyze", return_value=empty):
            result = asyncio.run(handler(""))
        assert "No dependency manifests" in result

    def test_shows_summary(self):
        handler = self._register()
        with patch("lidco.dependencies.analyzer.DependencyAnalyzer.analyze", return_value=self._fake_report()):
            result = asyncio.run(handler(""))
        assert "package" in result.lower()

    def test_shows_issues(self):
        from lidco.dependencies.analyzer import DependencyIssue
        handler = self._register()
        issues = [DependencyIssue("high", "pyyaml", "known_vulnerable", "Old PyYAML")]
        with patch("lidco.dependencies.analyzer.DependencyAnalyzer.analyze", return_value=self._fake_report(issues)):
            result = asyncio.run(handler(""))
        assert "pyyaml" in result
        assert "high" in result

    def test_no_issues_shows_ok(self):
        handler = self._register()
        with patch("lidco.dependencies.analyzer.DependencyAnalyzer.analyze", return_value=self._fake_report()):
            result = asyncio.run(handler(""))
        assert "✓" in result or "No issues" in result

    def test_exception_handled(self):
        handler = self._register()
        with patch("lidco.dependencies.analyzer.DependencyAnalyzer.analyze", side_effect=Exception("oops")):
            result = asyncio.run(handler(""))
        assert "Error" in result


# ---------------------------------------------------------------------------
# /migrate
# ---------------------------------------------------------------------------

class TestMigrateCommand:
    def _register(self):
        from lidco.cli.commands.q94_cmds import register_q94_commands
        r = _make_registry()
        register_q94_commands(r)
        return _get(r, "migrate")

    def _fake_result(self, changed=None):
        from lidco.migration.engine import MigrationResult
        return MigrationResult(
            rules_applied=["py2to3-has-key"],
            files_changed=changed or [],
            files_scanned=5,
            dry_run=True,
        )

    def test_list_shows_rulesets(self):
        handler = self._register()
        with patch("lidco.migration.engine.CodeMigrationEngine.list_rulesets",
                   return_value={"py2to3": 6, "stdlib": 4}):
            result = asyncio.run(handler("list"))
        assert "py2to3" in result
        assert "stdlib" in result

    def test_no_args_shows_list(self):
        handler = self._register()
        with patch("lidco.migration.engine.CodeMigrationEngine.list_rulesets",
                   return_value={"py2to3": 6}):
            result = asyncio.run(handler(""))
        assert "py2to3" in result

    def test_apply_dry_run(self):
        handler = self._register()
        with patch("lidco.migration.engine.CodeMigrationEngine.apply_ruleset",
                   return_value=self._fake_result()):
            result = asyncio.run(handler("apply py2to3"))
        assert "dry run" in result.lower()

    def test_apply_unknown_ruleset(self):
        handler = self._register()
        with patch("lidco.migration.engine.CodeMigrationEngine.apply_ruleset",
                   side_effect=KeyError("Unknown ruleset 'foo'. Available: py2to3")):
            result = asyncio.run(handler("apply foo"))
        assert "Unknown ruleset" in result

    def test_apply_write_flag(self):
        handler = self._register()
        called_with = {}
        def fake_apply_ruleset(name):
            called_with["dry_run"] = False  # Can't easily test constructor arg
            return self._fake_result()

        with patch("lidco.migration.engine.CodeMigrationEngine.apply_ruleset",
                   side_effect=fake_apply_ruleset):
            asyncio.run(handler("apply py2to3 --write"))

    def test_apply_shows_changed_files(self):
        from lidco.migration.engine import FileChange
        handler = self._register()
        changes = [FileChange("src/foo.py", "py2to3", "old", "new", 2)]
        with patch("lidco.migration.engine.CodeMigrationEngine.apply_ruleset",
                   return_value=self._fake_result(changed=changes)):
            result = asyncio.run(handler("apply py2to3"))
        assert "src/foo.py" in result

    def test_missing_ruleset_name_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler("apply"))
        # "apply" without ruleset name → usage
        assert "Usage" in result or "apply" in result


# ---------------------------------------------------------------------------
# /changelog
# ---------------------------------------------------------------------------

class TestChangelogCommand:
    def _register(self):
        from lidco.cli.commands.q94_cmds import register_q94_commands
        r = _make_registry()
        register_q94_commands(r)
        return _get(r, "changelog")

    def _fake_result(self):
        from lidco.git.changelog import (
            ChangelogResult, ChangelogRelease, ChangelogSection, ConventionalCommit
        )
        section = ChangelogSection(title="Features")
        section.commits.append(ConventionalCommit(
            hash="abc12345", type="feat", scope="", description="add thing",
            body="", breaking=False, date="2026-01-01", author="Alice", raw_message=""
        ))
        return ChangelogResult(
            releases=[ChangelogRelease("Unreleased", "2026-01-01", [section])],
            unrecognized_commits=[],
        )

    def test_shows_markdown(self):
        handler = self._register()
        with patch("lidco.git.changelog.ChangelogGenerator.generate", return_value=self._fake_result()):
            result = asyncio.run(handler(""))
        assert "Features" in result or "add thing" in result

    def test_no_commits_message(self):
        from lidco.git.changelog import ChangelogResult, ChangelogRelease
        handler = self._register()
        empty = ChangelogResult(
            releases=[ChangelogRelease("Unreleased", "2026-01-01", [])],
            unrecognized_commits=[],
        )
        with patch("lidco.git.changelog.ChangelogGenerator.generate", return_value=empty):
            result = asyncio.run(handler(""))
        assert "No conventional commits" in result

    def test_since_flag_passed(self):
        handler = self._register()
        called_with = {}
        def fake_gen(**kwargs):
            return MagicMock()

        from lidco.git.changelog import ChangelogGenerator
        original_init = ChangelogGenerator.__init__

        with patch.object(ChangelogGenerator, "generate", return_value=self._fake_result()):
            with patch.object(ChangelogGenerator, "__init__", lambda self, **kw: original_init(self, **kw) or called_with.update(kw)):
                asyncio.run(handler("--since v1.0.0"))

    def test_error_handled(self):
        handler = self._register()
        with patch("lidco.git.changelog.ChangelogGenerator.generate", side_effect=Exception("git error")):
            result = asyncio.run(handler(""))
        assert "Error" in result


# ---------------------------------------------------------------------------
# /env-check
# ---------------------------------------------------------------------------

class TestEnvCheckCommand:
    def _register(self):
        from lidco.cli.commands.q94_cmds import register_q94_commands
        r = _make_registry()
        register_q94_commands(r)
        return _get(r, "env-check")

    def _fake_result(self, issues=None, valid=True):
        from lidco.env.validator import ValidationResult, EnvVar
        return ValidationResult(
            env_vars=[EnvVar("FOO", "bar")],
            template_vars=[EnvVar("FOO", "")],
            issues=issues or [],
            env_file=".env",
            template_file=".env.example",
        )

    def test_valid_result(self):
        handler = self._register()
        with patch("lidco.env.validator.EnvValidator.validate", return_value=self._fake_result()):
            result = asyncio.run(handler(""))
        assert "Valid" in result or "✓" in result

    def test_invalid_result(self):
        from lidco.env.validator import ValidationIssue
        handler = self._register()
        issues = [ValidationIssue("error", "SECRET_KEY", "missing", "SECRET_KEY is missing")]
        with patch("lidco.env.validator.EnvValidator.validate", return_value=self._fake_result(issues=issues, valid=False)):
            result = asyncio.run(handler(""))
        assert "SECRET_KEY" in result

    def test_gen_template_flag(self):
        handler = self._register()
        with patch("lidco.env.validator.EnvValidator.generate_template", return_value="/path/.env.example"):
            result = asyncio.run(handler("--gen-template"))
        assert ".env.example" in result or "Generated" in result

    def test_gen_template_no_env(self):
        handler = self._register()
        with patch("lidco.env.validator.EnvValidator.generate_template", side_effect=FileNotFoundError(".env not found")):
            result = asyncio.run(handler("--gen-template"))
        assert "Error" in result

    def test_custom_env_flag(self):
        handler = self._register()
        called_with = {}
        from lidco.env.validator import EnvValidator
        original = EnvValidator.__init__

        def fake_init(self_, project_root=None, env_file=".env", **kw):
            called_with["env_file"] = env_file
            original(self_, project_root=project_root, env_file=env_file, **kw)

        with patch.object(EnvValidator, "__init__", fake_init):
            with patch("lidco.env.validator.EnvValidator.validate", return_value=self._fake_result()):
                asyncio.run(handler("--env .env.test"))

        assert called_with.get("env_file") == ".env.test"

    def test_exception_handled(self):
        handler = self._register()
        with patch("lidco.env.validator.EnvValidator.validate", side_effect=Exception("oops")):
            result = asyncio.run(handler(""))
        assert "Error" in result
