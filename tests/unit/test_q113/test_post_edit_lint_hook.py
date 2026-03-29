"""Tests for PostEditLintHook (Task 701)."""
import unittest
from unittest.mock import MagicMock

from lidco.editing.post_edit_lint import LintHookResult, PostEditLintHook


class TestLintHookResult(unittest.TestCase):
    def test_creation(self):
        r = LintHookResult(files_processed=3, auto_fixed=1, needs_manual=1, errors=["e"], blocked=True)
        self.assertEqual(r.files_processed, 3)
        self.assertTrue(r.blocked)

    def test_empty_result(self):
        r = LintHookResult(files_processed=0, auto_fixed=0, needs_manual=0, errors=[], blocked=False)
        self.assertFalse(r.blocked)


class TestEnableDisable(unittest.TestCase):
    def test_default_enabled(self):
        hook = PostEditLintHook()
        self.assertTrue(hook.enabled)

    def test_disable(self):
        hook = PostEditLintHook()
        hook.disable()
        self.assertFalse(hook.enabled)

    def test_enable_after_disable(self):
        hook = PostEditLintHook()
        hook.disable()
        hook.enable()
        self.assertTrue(hook.enabled)


class TestDisabledHook(unittest.TestCase):
    def test_disabled_returns_zero_result(self):
        hook = PostEditLintHook()
        hook.disable()
        result = hook.on_apply(["a.py", "b.py"])
        self.assertEqual(result.files_processed, 0)
        self.assertEqual(result.auto_fixed, 0)
        self.assertEqual(result.needs_manual, 0)
        self.assertFalse(result.blocked)


class TestOnApplyNoInjections(unittest.TestCase):
    def test_no_formatter_no_linter(self):
        hook = PostEditLintHook()
        result = hook.on_apply(["a.py"])
        self.assertEqual(result.files_processed, 1)
        self.assertEqual(result.auto_fixed, 0)
        self.assertFalse(result.blocked)

    def test_empty_files(self):
        hook = PostEditLintHook()
        result = hook.on_apply([])
        self.assertEqual(result.files_processed, 0)
        self.assertFalse(result.blocked)


class TestOnApplyWithFormatter(unittest.TestCase):
    def test_formatter_changed(self):
        fmt = MagicMock()
        fmt.format_file.return_value = MagicMock(changed=True, success=True, error="")
        hook = PostEditLintHook(formatter_registry=fmt)
        result = hook.on_apply(["a.py"])
        self.assertEqual(result.auto_fixed, 1)
        fmt.format_file.assert_called_once()

    def test_formatter_unchanged(self):
        fmt = MagicMock()
        fmt.format_file.return_value = MagicMock(changed=False, success=True, error="")
        hook = PostEditLintHook(formatter_registry=fmt)
        result = hook.on_apply(["a.py"])
        self.assertEqual(result.auto_fixed, 0)

    def test_formatter_error(self):
        fmt = MagicMock()
        fmt.format_file.return_value = MagicMock(changed=False, success=False, error="syntax error")
        hook = PostEditLintHook(formatter_registry=fmt)
        result = hook.on_apply(["a.py"])
        self.assertEqual(result.needs_manual, 1)
        self.assertTrue(len(result.errors) > 0)

    def test_formatter_exception(self):
        fmt = MagicMock()
        fmt.format_file.side_effect = RuntimeError("crash")
        hook = PostEditLintHook(formatter_registry=fmt)
        result = hook.on_apply(["a.py"])
        self.assertTrue(len(result.errors) > 0)

    def test_dry_run_check_only(self):
        fmt = MagicMock()
        fmt.format_file.return_value = MagicMock(changed=False, success=True, error="")
        hook = PostEditLintHook(formatter_registry=fmt)
        hook.on_apply(["a.py"], dry_run=True)
        fmt.format_file.assert_called_once_with("a.py", check_only=True)


class TestOnApplyWithLinter(unittest.TestCase):
    def test_linter_clean(self):
        linter = MagicMock()
        lint_result = MagicMock()
        lint_result.clean = True
        lint_result.errors = []
        linter.run_lint.return_value = [lint_result]
        hook = PostEditLintHook(lint_fix_loop=linter)
        result = hook.on_apply(["a.py"])
        self.assertEqual(result.needs_manual, 0)

    def test_linter_has_errors(self):
        linter = MagicMock()
        issue = MagicMock()
        issue.line = 5
        issue.message = "unused import"
        lint_result = MagicMock()
        lint_result.clean = False
        lint_result.errors = [issue]
        linter.run_lint.return_value = [lint_result]
        hook = PostEditLintHook(lint_fix_loop=linter)
        result = hook.on_apply(["a.py"])
        self.assertEqual(result.needs_manual, 1)

    def test_linter_exception(self):
        linter = MagicMock()
        linter.run_lint.side_effect = RuntimeError("lint crash")
        hook = PostEditLintHook(lint_fix_loop=linter)
        result = hook.on_apply(["a.py"])
        self.assertTrue(len(result.errors) > 0)


class TestBlocked(unittest.TestCase):
    def test_blocked_when_errors_and_threshold_error(self):
        linter = MagicMock()
        issue = MagicMock()
        issue.line = 1
        issue.message = "err"
        lint_result = MagicMock()
        lint_result.clean = False
        lint_result.errors = [issue]
        linter.run_lint.return_value = [lint_result]
        hook = PostEditLintHook(lint_fix_loop=linter, severity_threshold="error")
        result = hook.on_apply(["a.py"])
        self.assertTrue(result.blocked)

    def test_not_blocked_when_threshold_warning(self):
        linter = MagicMock()
        issue = MagicMock()
        issue.line = 1
        issue.message = "err"
        lint_result = MagicMock()
        lint_result.clean = False
        lint_result.errors = [issue]
        linter.run_lint.return_value = [lint_result]
        hook = PostEditLintHook(lint_fix_loop=linter, severity_threshold="warning")
        result = hook.on_apply(["a.py"])
        self.assertFalse(result.blocked)

    def test_not_blocked_when_no_errors(self):
        hook = PostEditLintHook(severity_threshold="error")
        result = hook.on_apply(["a.py"])
        self.assertFalse(result.blocked)


class TestRegisterWithSmartApply(unittest.TestCase):
    def test_registers_callback(self):
        hook = PostEditLintHook()
        sa = MagicMock()
        sa.after_apply_callback = None
        hook.register_with_smart_apply(sa)
        self.assertEqual(sa.after_apply_callback, hook.on_apply)

    def test_registers_via_register_callback(self):
        hook = PostEditLintHook()
        sa = MagicMock(spec=["register_callback"])
        hook.register_with_smart_apply(sa)
        sa.register_callback.assert_called_once_with("after_apply", hook.on_apply)


if __name__ == "__main__":
    unittest.main()
