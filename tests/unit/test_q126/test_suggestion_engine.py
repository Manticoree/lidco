"""Tests for suggestion_engine — Q126."""
from __future__ import annotations
import unittest
from lidco.proactive.suggestion_engine import (
    Suggestion,
    SuggestionEngine,
    rule_long_function,
    rule_no_docstring,
    rule_hardcoded_string,
    rule_todo_comment,
    rule_bare_except,
)


class TestSuggestion(unittest.TestCase):
    def test_creation(self):
        s = Suggestion(id="x", category="refactor", message="Fix this")
        self.assertEqual(s.id, "x")
        self.assertEqual(s.category, "refactor")
        self.assertEqual(s.confidence, 0.0)
        self.assertEqual(s.priority, 1)

    def test_all_fields(self):
        s = Suggestion(id="a", category="security", message="m", file="f.py", line=5,
                       confidence=0.9, priority=3)
        self.assertEqual(s.file, "f.py")
        self.assertEqual(s.line, 5)
        self.assertEqual(s.priority, 3)


class TestRuleLongFunction(unittest.TestCase):
    def test_short_function_no_suggestion(self):
        src = "def f(): pass"
        self.assertEqual(rule_long_function(src), [])

    def test_long_function_suggestion(self):
        body = "\n".join(["    x = 1"] * 55)
        src = f"def foo():\n{body}"
        result = rule_long_function(src)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0].category, "refactor")

    def test_syntax_error_returns_empty(self):
        self.assertEqual(rule_long_function("def f("), [])


class TestRuleNoDocstring(unittest.TestCase):
    def test_function_without_docstring(self):
        src = "def foo():\n    pass"
        result = rule_no_docstring(src)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0].category, "doc")

    def test_function_with_docstring(self):
        src = 'def foo():\n    """Docs."""\n    pass'
        result = rule_no_docstring(src)
        self.assertEqual(result, [])

    def test_class_without_docstring(self):
        src = "class Bar:\n    pass"
        result = rule_no_docstring(src)
        self.assertTrue(any(s.category == "doc" for s in result))


class TestRuleHardcodedString(unittest.TestCase):
    def test_ip_address(self):
        src = 'host = "192.168.1.1"'
        result = rule_hardcoded_string(src)
        self.assertTrue(len(result) > 0)

    def test_url(self):
        src = 'url = "https://example.com/api"'
        result = rule_hardcoded_string(src)
        self.assertTrue(len(result) > 0)

    def test_password(self):
        src = 'password = "supersecret"'
        result = rule_hardcoded_string(src)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0].category, "security")

    def test_clean_code(self):
        src = "x = 42"
        self.assertEqual(rule_hardcoded_string(src), [])


class TestRuleTodoComment(unittest.TestCase):
    def test_todo(self):
        src = "# TODO fix this"
        result = rule_todo_comment(src)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0].category, "refactor")

    def test_fixme(self):
        src = "# FIXME broken"
        result = rule_todo_comment(src)
        self.assertTrue(len(result) > 0)

    def test_no_todo(self):
        src = "x = 1  # regular comment"
        self.assertEqual(rule_todo_comment(src), [])


class TestRuleBareExcept(unittest.TestCase):
    def test_bare_except(self):
        src = "try:\n    pass\nexcept:\n    pass"
        result = rule_bare_except(src)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0].category, "refactor")

    def test_typed_except(self):
        src = "try:\n    pass\nexcept ValueError:\n    pass"
        self.assertEqual(rule_bare_except(src), [])

    def test_syntax_error(self):
        self.assertEqual(rule_bare_except("def f("), [])


class TestSuggestionEngine(unittest.TestCase):
    def test_empty_rules(self):
        engine = SuggestionEngine()
        self.assertEqual(engine.analyze("x = 1"), [])

    def test_add_rule(self):
        engine = SuggestionEngine()
        engine.add_rule(rule_todo_comment)
        results = engine.analyze("# TODO fix")
        self.assertTrue(len(results) > 0)

    def test_with_defaults(self):
        engine = SuggestionEngine.with_defaults()
        results = engine.analyze("# TODO refactor this\ndef foo():\n    pass")
        self.assertTrue(len(results) > 0)

    def test_filter_by_confidence(self):
        engine = SuggestionEngine.with_defaults()
        sug = [Suggestion("a", "refactor", "m", confidence=0.5),
               Suggestion("b", "security", "m", confidence=0.9)]
        filtered = engine.filter(sug, min_confidence=0.8)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "b")

    def test_filter_by_category(self):
        engine = SuggestionEngine.with_defaults()
        sug = [Suggestion("a", "refactor", "m"),
               Suggestion("b", "security", "m")]
        filtered = engine.filter(sug, category="security")
        self.assertEqual(len(filtered), 1)

    def test_top_n(self):
        engine = SuggestionEngine()
        sug = [
            Suggestion("a", "refactor", "m", priority=1, confidence=0.5),
            Suggestion("b", "security", "m", priority=3, confidence=0.9),
            Suggestion("c", "doc", "m", priority=2, confidence=0.7),
        ]
        top = engine.top_n(sug, 2)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].id, "b")  # highest priority

    def test_rule_exception_handled(self):
        def bad_rule(code, fname):
            raise RuntimeError("broken")
        engine = SuggestionEngine(rules=[bad_rule])
        result = engine.analyze("x = 1")
        self.assertEqual(result, [])

    def test_analyze_returns_list(self):
        engine = SuggestionEngine.with_defaults()
        result = engine.analyze("")
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
