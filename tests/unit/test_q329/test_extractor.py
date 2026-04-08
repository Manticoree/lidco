"""Tests for Q329 — KnowledgeExtractor."""
from __future__ import annotations

import os
import tempfile
import unittest

from lidco.knowledge.extractor import (
    Concept,
    ConceptType,
    ExtractionResult,
    KnowledgeExtractor,
)


class TestConcept(unittest.TestCase):
    def test_matches_name(self) -> None:
        c = Concept(
            name="AuthService",
            concept_type=ConceptType.DATA_MODEL,
            description="Handles auth",
            source_file="a.py",
        )
        self.assertTrue(c.matches("auth"))
        self.assertTrue(c.matches("AuthService"))

    def test_matches_description(self) -> None:
        c = Concept(
            name="Foo",
            concept_type=ConceptType.ALGORITHM,
            description="Sorting algorithm",
            source_file="a.py",
        )
        self.assertTrue(c.matches("sorting"))
        self.assertFalse(c.matches("xyz"))

    def test_matches_tags(self) -> None:
        c = Concept(
            name="X",
            concept_type=ConceptType.DESIGN_PATTERN,
            description="",
            source_file="a.py",
            tags=("singleton", "pattern"),
        )
        self.assertTrue(c.matches("singleton"))
        self.assertFalse(c.matches("factory"))

    def test_frozen_dataclass(self) -> None:
        c = Concept(
            name="A", concept_type=ConceptType.INVARIANT,
            description="d", source_file="f.py",
        )
        with self.assertRaises(AttributeError):
            c.name = "B"  # type: ignore[misc]


class TestExtractionResult(unittest.TestCase):
    def test_counts(self) -> None:
        r = ExtractionResult(
            concepts=[
                Concept("A", ConceptType.ALGORITHM, "", "f.py"),
                Concept("B", ConceptType.DESIGN_PATTERN, "", "f.py"),
            ],
            errors=["err1"],
        )
        self.assertEqual(r.concept_count, 2)
        self.assertEqual(r.error_count, 1)

    def test_by_type(self) -> None:
        r = ExtractionResult(
            concepts=[
                Concept("A", ConceptType.ALGORITHM, "", "f.py"),
                Concept("B", ConceptType.DESIGN_PATTERN, "", "f.py"),
                Concept("C", ConceptType.ALGORITHM, "", "f.py"),
            ]
        )
        algos = r.by_type(ConceptType.ALGORITHM)
        self.assertEqual(len(algos), 2)


class TestKnowledgeExtractor(unittest.TestCase):
    def test_extract_class(self) -> None:
        source = '''
class UserService:
    """Manages users."""
    pass
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "svc.py")
        names = [c.name for c in result.concepts]
        self.assertIn("UserService", names)

    def test_extract_function(self) -> None:
        source = '''
def calculate_total(items):
    """Sum all item prices."""
    return sum(i.price for i in items)
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "calc.py")
        names = [c.name for c in result.concepts]
        self.assertIn("calculate_total", names)

    def test_skip_private_functions(self) -> None:
        source = '''
def _private():
    pass

def public():
    pass
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "m.py")
        names = [c.name for c in result.concepts]
        self.assertNotIn("_private", names)
        self.assertIn("public", names)

    def test_detect_singleton_pattern(self) -> None:
        source = '''
class Singleton:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "s.py")
        pattern_names = [c.name for c in result.by_type(ConceptType.DESIGN_PATTERN)]
        self.assertIn("Singleton", pattern_names)

    def test_detect_factory_pattern(self) -> None:
        source = '''
class WidgetFactory:
    def create_widget(self, kind):
        pass
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "f.py")
        pattern_names = [c.name for c in result.by_type(ConceptType.DESIGN_PATTERN)]
        self.assertIn("Factory", pattern_names)

    def test_detect_observer_pattern(self) -> None:
        source = '''
class EventBus:
    def subscribe(self, event, handler):
        pass
    def notify(self, event):
        pass
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "bus.py")
        pattern_names = [c.name for c in result.by_type(ConceptType.DESIGN_PATTERN)]
        self.assertIn("Observer", pattern_names)

    def test_detect_business_rules(self) -> None:
        source = '''
def validate(x):
    if not x:
        raise ValueError("x required")
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "v.py")
        rule_types = {c.concept_type for c in result.concepts}
        self.assertTrue(
            rule_types & {ConceptType.BUSINESS_RULE, ConceptType.INVARIANT}
        )

    def test_syntax_error_reported(self) -> None:
        ext = KnowledgeExtractor()
        result = ext.extract_from_source("def broken(:", "bad.py")
        self.assertTrue(result.error_count > 0)
        self.assertIn("SyntaxError", result.errors[0])

    def test_extract_from_file(self) -> None:
        source = 'def hello():\n    """Say hello."""\n    pass\n'
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            f.flush()
            path = f.name
        try:
            ext = KnowledgeExtractor()
            result = ext.extract_from_file(path)
            self.assertEqual(result.error_count, 0)
            names = [c.name for c in result.concepts]
            self.assertIn("hello", names)
        finally:
            os.unlink(path)

    def test_extract_from_missing_file(self) -> None:
        ext = KnowledgeExtractor()
        result = ext.extract_from_file("/nonexistent/file.py")
        self.assertTrue(result.error_count > 0)

    def test_custom_pattern(self) -> None:
        ext = KnowledgeExtractor()
        ext.add_pattern("EventSourcing", r"class\s+\w*EventStore")
        source = 'class MyEventStore:\n    pass\n'
        result = ext.extract_from_source(source, "es.py")
        pattern_names = [c.name for c in result.by_type(ConceptType.DESIGN_PATTERN)]
        self.assertIn("EventSourcing", pattern_names)

    def test_async_function_tagged(self) -> None:
        source = '''
async def fetch_data():
    """Fetch data from API."""
    pass
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "api.py")
        for c in result.concepts:
            if c.name == "fetch_data":
                self.assertIn("async", c.tags)
                break
        else:
            self.fail("fetch_data not found")

    def test_abc_class_is_architecture_decision(self) -> None:
        source = '''
from abc import ABC

class BaseProcessor(ABC):
    """Abstract base processor."""
    pass
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "base.py")
        for c in result.concepts:
            if c.name == "BaseProcessor":
                self.assertEqual(c.concept_type, ConceptType.ARCHITECTURE_DECISION)
                break
        else:
            self.fail("BaseProcessor not found")

    def test_skip_exception_classes(self) -> None:
        source = '''
class MyError(Exception):
    pass

class MyService:
    pass
'''
        ext = KnowledgeExtractor()
        result = ext.extract_from_source(source, "svc.py")
        names = [c.name for c in result.concepts if c.concept_type == ConceptType.DATA_MODEL]
        self.assertNotIn("MyError", names)
        self.assertIn("MyService", names)


if __name__ == "__main__":
    unittest.main()
