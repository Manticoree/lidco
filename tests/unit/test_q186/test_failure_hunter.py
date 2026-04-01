"""Tests for SilentFailureHunter and TypeDesignAnalyzer — Task 1044."""

from __future__ import annotations

import unittest

from lidco.review.pipeline import ReviewSeverity
from lidco.review.agents.failure_hunter import SilentFailureHunter, TypeDesignAnalyzer


def _make_diff(file: str, lines: list[str]) -> str:
    added = "\n".join(f"+{line}" for line in lines)
    return f"+++ b/{file}\n@@ -0,0 +1,{len(lines)} @@\n{added}"


class TestSilentFailureHunter(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = SilentFailureHunter()

    def test_name(self) -> None:
        self.assertEqual(self.agent.name, "failure-hunter")

    def test_bare_except(self) -> None:
        diff = _make_diff("app.py", ["try:", "    x()", "except:", "    pass"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("Bare except" in i.message for i in issues))

    def test_bare_except_is_critical(self) -> None:
        diff = _make_diff("app.py", ["except:"])
        issues = self.agent.analyze(diff, [])
        bare = [i for i in issues if "Bare except" in i.message]
        for issue in bare:
            self.assertEqual(issue.severity, ReviewSeverity.CRITICAL)

    def test_swallowed_error(self) -> None:
        diff = _make_diff("app.py", ["except Exception:", "    pass"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("swallowed" in i.message.lower() for i in issues))

    def test_return_without_logging(self) -> None:
        diff = _make_diff("app.py", ["except ValueError:", "    return None"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("logging" in i.message.lower() for i in issues))

    def test_subprocess_without_check(self) -> None:
        diff = _make_diff("app.py", ['subprocess.run(["ls"])'])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("subprocess" in i.message for i in issues))

    def test_subprocess_with_check_no_issue(self) -> None:
        diff = _make_diff("app.py", ['subprocess.run(["ls"], check=True)'])
        issues = self.agent.analyze(diff, [])
        sub_issues = [i for i in issues if "subprocess" in i.message and "check" in i.message]
        self.assertEqual(len(sub_issues), 0)

    def test_os_system(self) -> None:
        diff = _make_diff("app.py", ['os.system("ls")'])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("os.system" in i.message for i in issues))

    def test_clean_code(self) -> None:
        diff = _make_diff("app.py", ["x = 1 + 2", "print(x)"])
        issues = self.agent.analyze(diff, [])
        self.assertEqual(len(issues), 0)

    def test_file_tracked(self) -> None:
        diff = _make_diff("server.py", ["except:"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any(i.file == "server.py" for i in issues))

    def test_line_number_tracked(self) -> None:
        diff = _make_diff("a.py", ["x = 1", "except:", "    pass"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(all(i.line > 0 for i in issues))


class TestTypeDesignAnalyzer(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = TypeDesignAnalyzer()

    def test_name(self) -> None:
        self.assertEqual(self.agent.name, "type-analyzer")

    def test_any_annotation(self) -> None:
        diff = _make_diff("app.py", ["def foo(x: Any) -> None:"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("Any" in i.message for i in issues))

    def test_any_return(self) -> None:
        diff = _make_diff("app.py", ["def foo() -> Any:"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("Any" in i.message for i in issues))

    def test_missing_return_type(self) -> None:
        diff = _make_diff("app.py", ["def process(data):"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("return type" in i.message.lower() for i in issues))

    def test_with_return_type_no_issue(self) -> None:
        diff = _make_diff("app.py", ["def process(data) -> int:"])
        issues = self.agent.analyze(diff, [])
        missing = [i for i in issues if "return type" in i.message.lower()]
        self.assertEqual(len(missing), 0)

    def test_broad_union(self) -> None:
        diff = _make_diff("app.py", ["x: Union[int, str, float, bool, list] = 0"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("Union" in i.message for i in issues))

    def test_bare_dict(self) -> None:
        diff = _make_diff("app.py", ["data: dict = {}"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("dict" in i.message.lower() for i in issues))

    def test_typed_dict_no_issue(self) -> None:
        diff = _make_diff("app.py", ['data: dict[str, int] = {"a": 1}'])
        issues = self.agent.analyze(diff, [])
        bare = [i for i in issues if "Bare" in i.message and "dict" in i.message]
        self.assertEqual(len(bare), 0)

    def test_severity_is_suggestion(self) -> None:
        diff = _make_diff("app.py", ["x: Any = 1"])
        issues = self.agent.analyze(diff, [])
        for issue in issues:
            self.assertEqual(issue.severity, ReviewSeverity.SUGGESTION)

    def test_clean_code(self) -> None:
        diff = _make_diff("app.py", ["x: int = 42"])
        issues = self.agent.analyze(diff, [])
        self.assertEqual(len(issues), 0)


if __name__ == "__main__":
    unittest.main()
