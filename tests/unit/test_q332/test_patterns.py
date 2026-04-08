"""Tests for review_learn.patterns (Q332, task 1772)."""
from __future__ import annotations

import unittest

from lidco.review_learn.patterns import (
    PatternCategory,
    PatternMatch,
    PatternRegistry,
    ReviewPattern,
    Severity,
    create_default_registry,
)


class TestReviewPattern(unittest.TestCase):
    def test_basic_fields(self) -> None:
        p = ReviewPattern(
            name="test-pat",
            description="A test pattern",
            category=PatternCategory.BEST_PRACTICE,
            severity=Severity.WARNING,
        )
        self.assertEqual(p.name, "test-pat")
        self.assertEqual(p.category, PatternCategory.BEST_PRACTICE)
        self.assertEqual(p.severity, Severity.WARNING)

    def test_matches_language_empty(self) -> None:
        p = ReviewPattern(name="x", description="d", category=PatternCategory.STYLE, severity=Severity.INFO)
        self.assertTrue(p.matches_language("python"))
        self.assertTrue(p.matches_language("rust"))

    def test_matches_language_specific(self) -> None:
        p = ReviewPattern(
            name="x", description="d",
            category=PatternCategory.STYLE, severity=Severity.INFO,
            languages=("python", "javascript"),
        )
        self.assertTrue(p.matches_language("Python"))
        self.assertTrue(p.matches_language("javascript"))
        self.assertFalse(p.matches_language("rust"))

    def test_to_dict(self) -> None:
        p = ReviewPattern(
            name="x", description="d",
            category=PatternCategory.SECURITY, severity=Severity.CRITICAL,
            languages=("python",), tags=("sec",),
        )
        d = p.to_dict()
        self.assertEqual(d["name"], "x")
        self.assertEqual(d["category"], "security")
        self.assertEqual(d["severity"], "critical")
        self.assertEqual(d["languages"], ["python"])
        self.assertEqual(d["tags"], ["sec"])

    def test_frozen(self) -> None:
        p = ReviewPattern(name="x", description="d", category=PatternCategory.STYLE, severity=Severity.INFO)
        with self.assertRaises(AttributeError):
            p.name = "y"  # type: ignore[misc]


class TestPatternMatch(unittest.TestCase):
    def test_fields(self) -> None:
        p = ReviewPattern(name="x", description="d", category=PatternCategory.STYLE, severity=Severity.INFO)
        m = PatternMatch(pattern=p, file_path="foo.py", line=10, context="ctx")
        self.assertEqual(m.file_path, "foo.py")
        self.assertEqual(m.line, 10)
        self.assertGreater(m.matched_at, 0)


class TestPatternRegistry(unittest.TestCase):
    def _make_pattern(self, name: str, **kwargs) -> ReviewPattern:
        defaults = {
            "description": f"desc-{name}",
            "category": PatternCategory.BEST_PRACTICE,
            "severity": Severity.WARNING,
        }
        defaults.update(kwargs)
        return ReviewPattern(name=name, **defaults)  # type: ignore[arg-type]

    def test_add_and_get(self) -> None:
        reg = PatternRegistry()
        p = self._make_pattern("a")
        reg.add(p)
        self.assertEqual(reg.count, 1)
        self.assertIs(reg.get("a"), p)

    def test_overwrite(self) -> None:
        reg = PatternRegistry()
        reg.add(self._make_pattern("a"))
        p2 = self._make_pattern("a", description="new")
        reg.add(p2)
        self.assertEqual(reg.count, 1)
        self.assertEqual(reg.get("a").description, "new")  # type: ignore[union-attr]

    def test_remove(self) -> None:
        reg = PatternRegistry()
        reg.add(self._make_pattern("a"))
        self.assertTrue(reg.remove("a"))
        self.assertFalse(reg.remove("a"))
        self.assertEqual(reg.count, 0)

    def test_list_all_sorted(self) -> None:
        reg = PatternRegistry()
        reg.add(self._make_pattern("b"))
        reg.add(self._make_pattern("a"))
        names = [p.name for p in reg.list_all()]
        self.assertEqual(names, ["a", "b"])

    def test_find_by_category(self) -> None:
        reg = PatternRegistry()
        reg.add(self._make_pattern("a", category=PatternCategory.SECURITY))
        reg.add(self._make_pattern("b", category=PatternCategory.STYLE))
        found = reg.find_by_category(PatternCategory.SECURITY)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "a")

    def test_find_by_severity(self) -> None:
        reg = PatternRegistry()
        reg.add(self._make_pattern("a", severity=Severity.CRITICAL))
        reg.add(self._make_pattern("b", severity=Severity.INFO))
        found = reg.find_by_severity(Severity.CRITICAL)
        self.assertEqual(len(found), 1)

    def test_find_by_language(self) -> None:
        reg = PatternRegistry()
        reg.add(self._make_pattern("a", languages=("python",)))
        reg.add(self._make_pattern("b", languages=("rust",)))
        reg.add(self._make_pattern("c"))  # no language = matches all
        found = reg.find_by_language("python")
        names = {p.name for p in found}
        self.assertIn("a", names)
        self.assertIn("c", names)
        self.assertNotIn("b", names)

    def test_find_by_tag(self) -> None:
        reg = PatternRegistry()
        reg.add(self._make_pattern("a", tags=("security", "auth")))
        reg.add(self._make_pattern("b", tags=("perf",)))
        found = reg.find_by_tag("security")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "a")

    def test_search(self) -> None:
        reg = PatternRegistry()
        reg.add(self._make_pattern("magic-number", description="Avoid magic numbers"))
        reg.add(self._make_pattern("other"))
        found = reg.search("magic")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, "magic-number")

    def test_search_description(self) -> None:
        reg = PatternRegistry()
        reg.add(self._make_pattern("a", description="hardcoded secrets are bad"))
        found = reg.search("secret")
        self.assertEqual(len(found), 1)


class TestCreateDefaultRegistry(unittest.TestCase):
    def test_has_patterns(self) -> None:
        reg = create_default_registry()
        self.assertGreaterEqual(reg.count, 5)

    def test_known_patterns_present(self) -> None:
        reg = create_default_registry()
        self.assertIsNotNone(reg.get("magic-number"))
        self.assertIsNotNone(reg.get("broad-except"))
        self.assertIsNotNone(reg.get("hardcoded-secret"))

    def test_security_category(self) -> None:
        reg = create_default_registry()
        sec = reg.find_by_category(PatternCategory.SECURITY)
        self.assertGreaterEqual(len(sec), 1)


if __name__ == "__main__":
    unittest.main()
