"""Tests for Bugbot — Task 410."""

from __future__ import annotations

import pytest

from lidco.proactive.bugbot import BugbotAnalyzer, BugbotWatcher, BugReport


# ---------------------------------------------------------------------------
# BugbotAnalyzer tests
# ---------------------------------------------------------------------------

BARE_EXCEPT_CODE = """\
try:
    pass
except:
    pass
"""

SWALLOWED_EXCEPTION_CODE = """\
try:
    pass
except Exception as e:
    pass
"""

MUTABLE_DEFAULT_LIST_CODE = """\
def foo(x=[]):
    return x
"""

MUTABLE_DEFAULT_DICT_CODE = """\
def bar(opts={}):
    return opts
"""

MUTABLE_DEFAULT_SET_CODE = """\
def baz(s=set()):
    return s
"""

EQ_NONE_CODE = """\
x = None
if x == None:
    pass
"""

NOT_EQ_NONE_CODE = """\
x = None
if x != None:
    pass
"""

UNREACHABLE_CODE = """\
def f():
    return 1
    x = 2
"""

CLEAN_CODE = """\
def clean(x: int = 0) -> int:
    try:
        return x + 1
    except ValueError:
        raise RuntimeError("bad") from None
"""

SYNTAX_ERROR_CODE = "def bad(:"

MULTIPLE_BUGS_CODE = """\
def problematic(items=[]):
    try:
        x = None
        if x == None:
            return items
        y = 1
    except:
        pass
"""


class TestBugbotAnalyzer:

    def setup_method(self) -> None:
        self.analyzer = BugbotAnalyzer()

    def test_bare_except_detected(self) -> None:
        reports = self.analyzer.analyze(BARE_EXCEPT_CODE, "test.py")
        kinds = [r.kind for r in reports]
        assert "bare_except" in kinds

    def test_swallowed_exception_detected(self) -> None:
        reports = self.analyzer.analyze(SWALLOWED_EXCEPTION_CODE, "test.py")
        kinds = [r.kind for r in reports]
        assert "swallowed_exception" in kinds

    def test_mutable_default_list(self) -> None:
        reports = self.analyzer.analyze(MUTABLE_DEFAULT_LIST_CODE, "test.py")
        kinds = [r.kind for r in reports]
        assert "mutable_default_arg" in kinds

    def test_mutable_default_dict(self) -> None:
        reports = self.analyzer.analyze(MUTABLE_DEFAULT_DICT_CODE, "test.py")
        kinds = [r.kind for r in reports]
        assert "mutable_default_arg" in kinds

    def test_eq_none(self) -> None:
        reports = self.analyzer.analyze(EQ_NONE_CODE, "test.py")
        kinds = [r.kind for r in reports]
        assert "eq_none" in kinds

    def test_not_eq_none(self) -> None:
        reports = self.analyzer.analyze(NOT_EQ_NONE_CODE, "test.py")
        kinds = [r.kind for r in reports]
        assert "eq_none" in kinds

    def test_unreachable_code(self) -> None:
        reports = self.analyzer.analyze(UNREACHABLE_CODE, "test.py")
        kinds = [r.kind for r in reports]
        assert "unreachable_code" in kinds

    def test_clean_code_no_reports(self) -> None:
        reports = self.analyzer.analyze(CLEAN_CODE, "test.py")
        assert reports == []

    def test_syntax_error_returns_empty(self) -> None:
        reports = self.analyzer.analyze(SYNTAX_ERROR_CODE, "test.py")
        assert reports == []

    def test_multiple_bugs_in_one_file(self) -> None:
        reports = self.analyzer.analyze(MULTIPLE_BUGS_CODE, "test.py")
        kinds = {r.kind for r in reports}
        assert len(kinds) >= 2

    def test_bug_report_fields(self) -> None:
        reports = self.analyzer.analyze(BARE_EXCEPT_CODE, "myfile.py")
        assert len(reports) >= 1
        r = reports[0]
        assert r.file == "myfile.py"
        assert r.line > 0
        assert r.kind
        assert r.message
        assert r.severity in ("error", "warning", "info")

    def test_bug_report_is_frozen(self) -> None:
        r = BugReport(file="f.py", line=1, kind="bare_except", message="msg", severity="warning")
        with pytest.raises((AttributeError, TypeError)):
            r.file = "other.py"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BugbotWatcher tests
# ---------------------------------------------------------------------------

class TestBugbotWatcher:

    def test_enabled_by_default(self) -> None:
        watcher = BugbotWatcher()
        assert watcher.enabled is True

    def test_set_enabled(self) -> None:
        watcher = BugbotWatcher()
        watcher.set_enabled(False)
        assert watcher.enabled is False

    def test_add_remove_file(self) -> None:
        watcher = BugbotWatcher()
        watcher.add_file("foo.py")
        assert "foo.py" in watcher._files
        watcher.remove_file("foo.py")
        assert "foo.py" not in watcher._files

    def test_analyze_missing_file(self) -> None:
        watcher = BugbotWatcher()
        reports = watcher.analyze_file("/nonexistent/file.py")
        assert reports == []
