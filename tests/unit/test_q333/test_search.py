"""Tests for lidco.adr.search — ADRSearch."""

from __future__ import annotations

import unittest

from lidco.adr.manager import ADR, ADRManager, ADRStatus
from lidco.adr.search import (
    ADRSearch,
    CodeReference,
    SearchResult,
    TraceabilityReport,
    _text_match_score,
)


class TestTextMatchScore(unittest.TestCase):
    """Tests for _text_match_score helper."""

    def test_exact_substring(self) -> None:
        self.assertEqual(_text_match_score("redis", "Use Redis for caching"), 1.0)

    def test_word_overlap(self) -> None:
        score = _text_match_score("redis caching", "We use redis and memcached for caching")
        self.assertGreater(score, 0)

    def test_no_match(self) -> None:
        self.assertEqual(_text_match_score("kafka", "Use Redis"), 0.0)

    def test_empty(self) -> None:
        self.assertEqual(_text_match_score("", "text"), 0.0)
        self.assertEqual(_text_match_score("q", ""), 0.0)


class TestSearchResult(unittest.TestCase):
    def test_to_dict(self) -> None:
        adr = ADR(number=1, title="T")
        r = SearchResult(adr=adr, score=0.9, matched_fields=["title"], snippet="snip")
        d = r.to_dict()
        self.assertEqual(d["score"], 0.9)
        self.assertEqual(d["snippet"], "snip")


class TestCodeReference(unittest.TestCase):
    def test_to_dict(self) -> None:
        r = CodeReference(file_path="a.py", line_number=10, adr_number=1, text="# ADR-1")
        d = r.to_dict()
        self.assertEqual(d["file_path"], "a.py")


class TestTraceabilityReport(unittest.TestCase):
    def test_to_dict(self) -> None:
        t = TraceabilityReport(adr_number=1, title="T", status="accepted", referenced_in_code=True)
        d = t.to_dict()
        self.assertTrue(d["referenced_in_code"])


class TestADRSearch(unittest.TestCase):
    """Tests for ADRSearch."""

    def setUp(self) -> None:
        self.mgr = ADRManager()
        self.mgr.create("Use PostgreSQL", context="Need a relational database", decision="PostgreSQL", tags=["database"])
        self.mgr.create("Use Redis", context="Need caching layer", decision="Redis", tags=["cache"])
        self.mgr.create("REST API", context="API design", decision="Use REST", tags=["api"])
        self.search = ADRSearch(self.mgr)

    def test_full_text_search_title(self) -> None:
        results = self.search.full_text_search("PostgreSQL")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].adr.title, "Use PostgreSQL")

    def test_full_text_search_context(self) -> None:
        results = self.search.full_text_search("relational database")
        self.assertGreater(len(results), 0)

    def test_full_text_search_tag(self) -> None:
        results = self.search.full_text_search("cache")
        self.assertTrue(any(r.adr.title == "Use Redis" for r in results))

    def test_full_text_search_no_match(self) -> None:
        results = self.search.full_text_search("blockchain")
        self.assertEqual(len(results), 0)

    def test_full_text_search_empty(self) -> None:
        results = self.search.full_text_search("")
        self.assertEqual(len(results), 0)

    def test_full_text_search_limit(self) -> None:
        results = self.search.full_text_search("Use", limit=1)
        self.assertLessEqual(len(results), 1)

    def test_search_by_status(self) -> None:
        self.mgr.update_status(1, ADRStatus.ACCEPTED)
        results = self.search.search_by_status(ADRStatus.ACCEPTED)
        self.assertEqual(len(results), 1)

    def test_search_by_date_range(self) -> None:
        results = self.search.search_by_date_range("2020-01-01", "2099-12-31")
        self.assertEqual(len(results), 3)

    def test_search_by_date_range_none(self) -> None:
        results = self.search.search_by_date_range("2000-01-01", "2000-01-02")
        self.assertEqual(len(results), 0)

    def test_search_by_tag(self) -> None:
        results = self.search.search_by_tag("database")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].adr.title, "Use PostgreSQL")

    def test_search_by_tag_case_insensitive(self) -> None:
        results = self.search.search_by_tag("DATABASE")
        self.assertEqual(len(results), 1)

    def test_find_code_references(self) -> None:
        files = {
            "app.py": "# See ADR-0001 for rationale\nimport foo\n",
            "db.py": "# ADR-2 decision\nconn = connect()\n",
        }
        refs = self.search.find_code_references(files)
        self.assertEqual(len(refs), 2)
        numbers = {r.adr_number for r in refs}
        self.assertIn(1, numbers)
        self.assertIn(2, numbers)

    def test_find_code_references_empty(self) -> None:
        refs = self.search.find_code_references({"a.py": "no refs here"})
        self.assertEqual(len(refs), 0)

    def test_traceability_report(self) -> None:
        files = {"app.py": "# ADR-0001\n"}
        reports = self.search.traceability_report(file_contents=files)
        self.assertEqual(len(reports), 3)
        adr1_report = next(r for r in reports if r.adr_number == 1)
        self.assertTrue(adr1_report.referenced_in_code)
        adr2_report = next(r for r in reports if r.adr_number == 2)
        self.assertFalse(adr2_report.referenced_in_code)

    def test_traceability_report_no_files(self) -> None:
        reports = self.search.traceability_report()
        self.assertEqual(len(reports), 3)
        self.assertFalse(reports[0].referenced_in_code)

    def test_cross_reference(self) -> None:
        adr4 = self.mgr.create("Supersedes PG")
        adr4.references.append("ADR-0001")
        self.mgr.supersede(1, 4)
        xrefs = self.search.cross_reference()
        self.assertIn(4, xrefs)
        self.assertIn(1, xrefs[4])
        # ADR-1 should ref ADR-4 via superseded_by
        self.assertIn(1, xrefs)
        self.assertIn(4, xrefs[1])

    def test_cross_reference_empty(self) -> None:
        xrefs = self.search.cross_reference()
        self.assertEqual(len(xrefs), 0)

    def test_manager_property(self) -> None:
        self.assertIs(self.search.manager, self.mgr)


if __name__ == "__main__":
    unittest.main()
