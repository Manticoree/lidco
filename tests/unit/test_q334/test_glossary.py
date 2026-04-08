"""Tests for lidco.writing.glossary — GlossaryManager."""

from __future__ import annotations

import json
import unittest

from lidco.writing.glossary import (
    ConsistencyViolation,
    GlossaryEntry,
    GlossaryManager,
    GlossaryReport,
    UndefinedTerm,
)


class TestGlossaryEntry(unittest.TestCase):
    def test_matches_term(self):
        entry = GlossaryEntry(term="API", definition="Application Programming Interface")
        self.assertTrue(entry.matches("The API is ready."))
        self.assertTrue(entry.matches("Use the api endpoint."))

    def test_matches_alias(self):
        entry = GlossaryEntry(term="API", definition="...", aliases=["REST endpoint"])
        self.assertTrue(entry.matches("Call the REST endpoint."))

    def test_no_match(self):
        entry = GlossaryEntry(term="API", definition="...")
        self.assertFalse(entry.matches("The database is running."))


class TestGlossaryManagerCRUD(unittest.TestCase):
    def setUp(self):
        self.mgr = GlossaryManager()

    def test_add_and_get(self):
        entry = GlossaryEntry(term="API", definition="Application Programming Interface")
        self.mgr.add(entry)
        result = self.mgr.get("API")
        self.assertIsNotNone(result)
        self.assertEqual(result.term, "API")

    def test_get_case_insensitive(self):
        self.mgr.add(GlossaryEntry(term="API", definition="..."))
        self.assertIsNotNone(self.mgr.get("api"))

    def test_get_not_found(self):
        self.assertIsNone(self.mgr.get("nonexistent"))

    def test_remove(self):
        self.mgr.add(GlossaryEntry(term="API", definition="..."))
        self.assertTrue(self.mgr.remove("API"))
        self.assertIsNone(self.mgr.get("API"))

    def test_remove_not_found(self):
        self.assertFalse(self.mgr.remove("nonexistent"))

    def test_list_entries(self):
        self.mgr.add(GlossaryEntry(term="Zebra", definition="z"))
        self.mgr.add(GlossaryEntry(term="Apple", definition="a"))
        entries = self.mgr.list_entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].term, "Apple")

    def test_count(self):
        self.assertEqual(self.mgr.count, 0)
        self.mgr.add(GlossaryEntry(term="API", definition="..."))
        self.assertEqual(self.mgr.count, 1)

    def test_search_by_term(self):
        self.mgr.add(GlossaryEntry(term="API", definition="Application Programming Interface"))
        results = self.mgr.search("API")
        self.assertEqual(len(results), 1)

    def test_search_by_definition(self):
        self.mgr.add(GlossaryEntry(term="API", definition="Application Programming Interface"))
        results = self.mgr.search("Programming")
        self.assertEqual(len(results), 1)

    def test_search_by_alias(self):
        self.mgr.add(GlossaryEntry(term="API", definition="...", aliases=["web service"]))
        results = self.mgr.search("web service")
        self.assertEqual(len(results), 1)

    def test_search_no_results(self):
        self.mgr.add(GlossaryEntry(term="API", definition="..."))
        results = self.mgr.search("nonexistent")
        self.assertEqual(len(results), 0)

    def test_update_entry(self):
        self.mgr.add(GlossaryEntry(term="API", definition="old"))
        self.mgr.add(GlossaryEntry(term="API", definition="new"))
        entry = self.mgr.get("API")
        self.assertEqual(entry.definition, "new")


class TestGlossaryManagerScan(unittest.TestCase):
    def setUp(self):
        self.mgr = GlossaryManager()

    def test_scan_finds_defined_terms(self):
        self.mgr.add(GlossaryEntry(term="API", definition="..."))
        report = self.mgr.scan("The API is ready.")
        self.assertIn("API", report.defined_terms_found)

    def test_scan_finds_undefined_tech_terms(self):
        # "redis" is in _COMMON_TECH_TERMS but not in glossary
        report = self.mgr.scan("We use redis for caching.")
        terms = [u.term.lower() for u in report.undefined_terms]
        self.assertIn("redis", terms)

    def test_scan_consistency_violations(self):
        self.mgr.add(GlossaryEntry(term="API", definition="...", aliases=["web service"]))
        report = self.mgr.scan("The web service returns data.")
        self.assertTrue(len(report.consistency_violations) > 0)
        self.assertEqual(report.consistency_violations[0].canonical, "API")

    def test_scan_no_issues(self):
        self.mgr.add(GlossaryEntry(term="API", definition="..."))
        report = self.mgr.scan("The API is running.")
        self.assertEqual(len(report.consistency_violations), 0)


class TestGlossaryManagerCrossRef(unittest.TestCase):
    def setUp(self):
        self.mgr = GlossaryManager()

    def test_cross_references(self):
        self.mgr.add(GlossaryEntry(term="API", definition="...", related=["REST"]))
        self.mgr.add(GlossaryEntry(term="REST", definition="Representational State Transfer"))
        refs = self.mgr.cross_references("API")
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].term, "REST")

    def test_cross_references_not_found(self):
        refs = self.mgr.cross_references("nonexistent")
        self.assertEqual(len(refs), 0)

    def test_cross_references_missing_target(self):
        self.mgr.add(GlossaryEntry(term="API", definition="...", related=["nonexistent"]))
        refs = self.mgr.cross_references("API")
        self.assertEqual(len(refs), 0)


class TestGlossaryManagerPersistence(unittest.TestCase):
    def setUp(self):
        self.mgr = GlossaryManager()

    def test_export_json(self):
        self.mgr.add(GlossaryEntry(term="API", definition="...", aliases=["endpoint"], category="tech"))
        raw = self.mgr.export_json()
        data = json.loads(raw)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["term"], "API")
        self.assertIn("endpoint", data[0]["aliases"])

    def test_import_json(self):
        data = json.dumps([
            {"term": "API", "definition": "Application Programming Interface", "aliases": [], "related": []},
            {"term": "SDK", "definition": "Software Development Kit", "aliases": [], "related": []},
        ])
        count = self.mgr.import_json(data)
        self.assertEqual(count, 2)
        self.assertEqual(self.mgr.count, 2)
        self.assertIsNotNone(self.mgr.get("API"))

    def test_import_invalid_json(self):
        with self.assertRaises(json.JSONDecodeError):
            self.mgr.import_json("not json")

    def test_roundtrip(self):
        self.mgr.add(GlossaryEntry(term="API", definition="...", aliases=["endpoint"], related=["REST"], category="tech"))
        raw = self.mgr.export_json()
        mgr2 = GlossaryManager()
        mgr2.import_json(raw)
        entry = mgr2.get("API")
        self.assertIsNotNone(entry)
        self.assertIn("endpoint", entry.aliases)
        self.assertIn("REST", entry.related)
        self.assertEqual(entry.category, "tech")


if __name__ == "__main__":
    unittest.main()
