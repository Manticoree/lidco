"""Tests for T611 Q95 CLI commands."""
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock

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


class TestRegisterQ95:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q95_cmds import register_q95_commands
        r = _make_registry()
        register_q95_commands(r)
        assert "stats" in r._handlers
        assert "todo" in r._handlers
        assert "licenses" in r._handlers
        assert "hooks" in r._handlers


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------

class TestStatsCommand:
    def _register(self):
        from lidco.cli.commands.q95_cmds import register_q95_commands
        r = _make_registry()
        register_q95_commands(r)
        return _get(r, "stats")

    def _fake_report(self):
        from lidco.stats.code_stats import CodeStatsReport, LanguageStat
        return CodeStatsReport(
            by_language={
                "Python": LanguageStat("Python", files=10, total_lines=1000, code_lines=800, comment_lines=100, blank_lines=100),
            },
            file_stats=[],
            total_files=10,
            total_lines=1000,
            total_code=800,
            total_comments=100,
            total_blank=100,
        )

    def test_shows_summary(self):
        handler = self._register()
        with patch("lidco.stats.code_stats.CodeStats.analyze", return_value=self._fake_report()):
            result = asyncio.run(handler(""))
        assert "Python" in result
        assert "800" in result

    def test_json_flag(self):
        handler = self._register()
        with patch("lidco.stats.code_stats.CodeStats.analyze", return_value=self._fake_report()):
            result = asyncio.run(handler("--json"))
        import json
        data = json.loads(result)
        assert "Python" in data

    def test_error_handled(self):
        handler = self._register()
        with patch("lidco.stats.code_stats.CodeStats.analyze", side_effect=Exception("disk error")):
            result = asyncio.run(handler(""))
        assert "Error" in result


# ---------------------------------------------------------------------------
# /todo
# ---------------------------------------------------------------------------

class TestTodoCommand:
    def _register(self):
        from lidco.cli.commands.q95_cmds import register_q95_commands
        r = _make_registry()
        register_q95_commands(r)
        return _get(r, "todo")

    def _fake_report(self, items=None):
        from lidco.analysis.todo_scanner import TodoReport, TodoItem
        items = items or [
            TodoItem(file="src/foo.py", line=10, tag="TODO", severity="medium", text="fix this"),
            TodoItem(file="src/bar.py", line=5, tag="FIXME", severity="high", text="broken"),
        ]
        return TodoReport(items=items, files_scanned=5)

    def test_shows_items(self):
        handler = self._register()
        with patch("lidco.analysis.todo_scanner.TodoScanner.scan", return_value=self._fake_report()):
            result = asyncio.run(handler(""))
        assert "TODO" in result
        assert "FIXME" in result

    def test_no_items_message(self):
        handler = self._register()
        from lidco.analysis.todo_scanner import TodoReport
        empty = TodoReport(items=[], files_scanned=3)
        with patch("lidco.analysis.todo_scanner.TodoScanner.scan", return_value=empty):
            result = asyncio.run(handler(""))
        assert "No TODO" in result

    def test_tag_filter(self):
        handler = self._register()
        with patch("lidco.analysis.todo_scanner.TodoScanner.scan", return_value=self._fake_report()):
            result = asyncio.run(handler("--tag FIXME"))
        assert "FIXME" in result

    def test_severity_filter(self):
        handler = self._register()
        with patch("lidco.analysis.todo_scanner.TodoScanner.scan", return_value=self._fake_report()):
            result = asyncio.run(handler("--severity high"))
        # Only FIXME (high) should appear
        assert "FIXME" in result

    def test_shows_summary_line(self):
        handler = self._register()
        with patch("lidco.analysis.todo_scanner.TodoScanner.scan", return_value=self._fake_report()):
            result = asyncio.run(handler(""))
        assert "files scanned" in result.lower() or "items" in result.lower()


# ---------------------------------------------------------------------------
# /licenses
# ---------------------------------------------------------------------------

class TestLicensesCommand:
    def _register(self):
        from lidco.cli.commands.q95_cmds import register_q95_commands
        r = _make_registry()
        register_q95_commands(r)
        return _get(r, "licenses")

    def _fake_report(self, packages=None, issues=None):
        from lidco.compliance.license_checker import LicenseReport, PackageLicense
        pkgs = packages or [
            PackageLicense("requests", "2.28.0", "Apache-2.0", "permissive"),
        ]
        return LicenseReport(packages=pkgs, issues=issues or [], project_license="MIT")

    def test_no_packages(self):
        from lidco.compliance.license_checker import LicenseReport
        handler = self._register()
        empty = LicenseReport(packages=[], issues=[], project_license="MIT")
        with patch("lidco.compliance.license_checker.LicenseChecker.check", return_value=empty):
            result = asyncio.run(handler(""))
        assert "No packages" in result

    def test_shows_packages(self):
        handler = self._register()
        with patch("lidco.compliance.license_checker.LicenseChecker.check", return_value=self._fake_report()):
            result = asyncio.run(handler(""))
        assert "requests" in result

    def test_shows_issues(self):
        from lidco.compliance.license_checker import LicenseIssue, PackageLicense, LicenseReport
        handler = self._register()
        pkgs = [PackageLicense("badlib", "1.0", "GPL-3.0", "copyleft")]
        issues = [LicenseIssue("error", "badlib", "GPL-3.0", "copyleft", "incompatible")]
        report = LicenseReport(packages=pkgs, issues=issues, project_license="MIT")
        with patch("lidco.compliance.license_checker.LicenseChecker.check", return_value=report):
            result = asyncio.run(handler(""))
        assert "badlib" in result or "incompatible" in result

    def test_error_handled(self):
        handler = self._register()
        with patch("lidco.compliance.license_checker.LicenseChecker.check", side_effect=Exception("oops")):
            result = asyncio.run(handler(""))
        assert "Error" in result


# ---------------------------------------------------------------------------
# /hooks
# ---------------------------------------------------------------------------

class TestHooksCommand:
    def _register(self):
        from lidco.cli.commands.q95_cmds import register_q95_commands
        r = _make_registry()
        register_q95_commands(r)
        return _get(r, "hooks")

    def _make_hook(self, name="pre-commit", enabled=True):
        from lidco.git.hooks_manager import GitHook
        return GitHook(name=name, path=f".git/hooks/{name}", enabled=enabled, is_standard=True)

    def test_list_no_hooks(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.list", return_value=[]):
            result = asyncio.run(handler("list"))
        assert "No hooks" in result

    def test_list_shows_hooks(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.list", return_value=[self._make_hook()]):
            result = asyncio.run(handler("list"))
        assert "pre-commit" in result

    def test_list_disabled_shows_status(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.list", return_value=[self._make_hook(enabled=False)]):
            result = asyncio.run(handler("list"))
        assert "disabled" in result.lower() or "✗" in result

    def test_install_hook(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.install", return_value=self._make_hook()):
            result = asyncio.run(handler("install pre-commit exit 0"))
        assert "Installed" in result or "pre-commit" in result

    def test_install_conflict(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.install", side_effect=FileExistsError("exists")):
            result = asyncio.run(handler("install pre-commit exit 0"))
        assert "Error" in result or "exists" in result.lower()

    def test_remove_hook(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.remove", return_value=True):
            result = asyncio.run(handler("remove pre-commit"))
        assert "Removed" in result

    def test_remove_not_found(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.remove", return_value=False):
            result = asyncio.run(handler("remove nonexistent"))
        assert "not found" in result.lower() or "not" in result

    def test_enable_hook(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.enable", return_value=self._make_hook()):
            result = asyncio.run(handler("enable pre-commit"))
        assert "Enabled" in result

    def test_disable_hook(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.disable", return_value=self._make_hook(enabled=False)):
            result = asyncio.run(handler("disable pre-commit"))
        assert "Disabled" in result

    def test_enable_error(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.enable", side_effect=FileNotFoundError("not found")):
            result = asyncio.run(handler("enable missing"))
        assert "Error" in result

    def test_run_success(self):
        from lidco.git.hooks_manager import HookResult
        handler = self._register()
        fake_result = HookResult("pre-commit", True, 0, stdout="all good", stderr="")
        with patch("lidco.git.hooks_manager.HooksManager.run", return_value=fake_result):
            result = asyncio.run(handler("run pre-commit"))
        assert "passed" in result or "pre-commit" in result

    def test_run_failure(self):
        from lidco.git.hooks_manager import HookResult
        handler = self._register()
        fake_result = HookResult("pre-commit", False, 1, stdout="", stderr="lint failed")
        with patch("lidco.git.hooks_manager.HooksManager.run", return_value=fake_result):
            result = asyncio.run(handler("run pre-commit"))
        assert "failed" in result or "lint failed" in result

    def test_no_subcommand_shows_list(self):
        handler = self._register()
        with patch("lidco.git.hooks_manager.HooksManager.list", return_value=[]):
            result = asyncio.run(handler(""))
        assert "hooks" in result.lower()

    def test_unknown_subcommand_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler("badcmd"))
        assert "Usage" in result
