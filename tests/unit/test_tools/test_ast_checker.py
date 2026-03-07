"""Tests for ASTBugCheckerTool and check_file."""
from __future__ import annotations

import dataclasses
import textwrap
from pathlib import Path

import pytest

from lidco.tools.ast_checker import ASTBugCheckerTool, ASTIssue, check_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_py(tmp_path: Path, content: str, name: str = "sample.py") -> str:
    """Write *content* to *tmp_path/name* and return the file path as str."""
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return str(p)


def _rules(issues: list[ASTIssue]) -> list[str]:
    return [i.rule for i in issues]


# ---------------------------------------------------------------------------
# Individual rule checks
# ---------------------------------------------------------------------------


class TestMutableDefault:
    def test_list_default_detected(self, tmp_path: Path) -> None:
        src = """\
            def foo(x=[]):
                return x
        """
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert any(i.rule == "mutable-default" for i in issues)


class TestBareExcept:
    def test_bare_except_detected(self, tmp_path: Path) -> None:
        src = """\
            try:
                pass
            except:
                pass
        """
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert any(i.rule == "bare-except" for i in issues)


class TestSilencedException:
    def test_silenced_exception_detected(self, tmp_path: Path) -> None:
        src = """\
            try:
                pass
            except Exception:
                pass
        """
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert any(i.rule == "silenced-exception" for i in issues)


class TestNoneComparison:
    def test_eq_none_detected(self, tmp_path: Path) -> None:
        src = """\
            x = None
            if x == None:
                pass
        """
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert any(i.rule == "none-comparison" for i in issues)

    def test_neq_none_detected(self, tmp_path: Path) -> None:
        src = """\
            x = None
            if x != None:
                pass
        """
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert any(i.rule == "none-comparison" for i in issues)


class TestBoolComparison:
    def test_eq_true_detected(self, tmp_path: Path) -> None:
        src = """\
            x = True
            if x == True:
                pass
        """
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert any(i.rule == "bool-comparison" for i in issues)

    def test_eq_false_detected(self, tmp_path: Path) -> None:
        src = """\
            x = False
            if x == False:
                pass
        """
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert any(i.rule == "bool-comparison" for i in issues)


class TestAssertInProd:
    def test_assert_detected_in_non_test_file(self, tmp_path: Path) -> None:
        src = """\
            def validate(x):
                assert x > 0, "must be positive"
        """
        # Use a non-test filename
        path = _write_py(tmp_path, src, name="validator.py")
        issues = check_file(path, [])
        assert any(i.rule == "assert-in-prod" for i in issues)


class TestUnreachableCode:
    def test_code_after_return_detected(self, tmp_path: Path) -> None:
        src = """\
            def foo():
                return 1
                x = 2
        """
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert any(i.rule == "unreachable-code" for i in issues)


class TestBroadRaise:
    def test_raise_exception_detected(self, tmp_path: Path) -> None:
        src = """\
            def foo():
                raise Exception("something went wrong")
        """
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert any(i.rule == "broad-raise" for i in issues)


class TestSyntaxError:
    def test_syntax_error_returns_issue(self, tmp_path: Path) -> None:
        src = "def foo(:\n    pass\n"
        path = _write_py(tmp_path, src)
        issues = check_file(path, [])
        assert len(issues) == 1
        assert issues[0].rule == "syntax-error"


class TestEmptyFile:
    def test_empty_file_no_issues(self, tmp_path: Path) -> None:
        path = _write_py(tmp_path, "")
        issues = check_file(path, [])
        assert issues == []


class TestRulesFilter:
    def test_rules_filter_limits_output(self, tmp_path: Path) -> None:
        # File with both mutable-default and bare-except
        src = """\
            def foo(x=[]):
                try:
                    pass
                except:
                    pass
        """
        path = _write_py(tmp_path, src)
        all_issues = check_file(path, [])
        filtered = check_file(path, ["mutable-default"])
        # filtered should only contain mutable-default
        assert all(i.rule == "mutable-default" for i in filtered)
        assert len(filtered) < len(all_issues)


class TestASTIssueFrozen:
    def test_astissue_is_frozen_dataclass(self) -> None:
        issue = ASTIssue(
            file="foo.py",
            line=1,
            rule="test",
            message="test message",
            fix_hint="fix it",
        )
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            issue.line = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ASTBugCheckerTool integration
# ---------------------------------------------------------------------------


class TestASTBugCheckerTool:
    def setup_method(self) -> None:
        self.tool = ASTBugCheckerTool()

    async def test_success_true_when_no_issues(self, tmp_path: Path) -> None:
        src = """\
            def greet(name: str) -> str:
                return f"Hello, {name}"
        """
        path = _write_py(tmp_path, src)
        result = await self.tool._run(path=str(path))
        assert result.success is True

    async def test_success_false_when_issues_found(self, tmp_path: Path) -> None:
        src = """\
            def foo(x=[]):
                return x
        """
        path = _write_py(tmp_path, src)
        result = await self.tool._run(path=str(path))
        assert result.success is False
