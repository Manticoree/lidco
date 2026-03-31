"""Tests for OutputPaginator."""
from __future__ import annotations

import unittest

from lidco.streaming.paginator import OutputPaginator, Page


class TestPage(unittest.TestCase):
    def test_fields(self):
        p = Page(content=["a"], page_number=1, total_pages=1, has_next=False, has_prev=False)
        self.assertEqual(p.content, ["a"])
        self.assertEqual(p.page_number, 1)
        self.assertFalse(p.has_next)
        self.assertFalse(p.has_prev)


class TestOutputPaginator(unittest.TestCase):
    def _lines(self, n: int) -> list[str]:
        return [f"line {i}" for i in range(1, n + 1)]

    # --- total_pages ---
    def test_total_pages_empty(self):
        pag = OutputPaginator([], page_size=10)
        self.assertEqual(pag.total_pages, 1)

    def test_total_pages_exact(self):
        pag = OutputPaginator(self._lines(20), page_size=10)
        self.assertEqual(pag.total_pages, 2)

    def test_total_pages_partial(self):
        pag = OutputPaginator(self._lines(25), page_size=10)
        self.assertEqual(pag.total_pages, 3)

    # --- page ---
    def test_page_first(self):
        pag = OutputPaginator(self._lines(30), page_size=10)
        pg = pag.page(1)
        self.assertEqual(pg.page_number, 1)
        self.assertEqual(len(pg.content), 10)
        self.assertTrue(pg.has_next)
        self.assertFalse(pg.has_prev)

    def test_page_last(self):
        pag = OutputPaginator(self._lines(25), page_size=10)
        pg = pag.page(3)
        self.assertEqual(pg.page_number, 3)
        self.assertEqual(len(pg.content), 5)
        self.assertFalse(pg.has_next)
        self.assertTrue(pg.has_prev)

    def test_page_clamps_high(self):
        pag = OutputPaginator(self._lines(10), page_size=10)
        pg = pag.page(99)
        self.assertEqual(pg.page_number, 1)

    def test_page_clamps_low(self):
        pag = OutputPaginator(self._lines(10), page_size=10)
        pg = pag.page(0)
        self.assertEqual(pg.page_number, 1)

    def test_page_sets_current(self):
        pag = OutputPaginator(self._lines(30), page_size=10)
        pag.page(2)
        self.assertEqual(pag.current_page_number, 2)

    # --- next_page / prev_page ---
    def test_next_page(self):
        pag = OutputPaginator(self._lines(30), page_size=10)
        pag.page(1)
        pg = pag.next_page()
        self.assertEqual(pg.page_number, 2)

    def test_next_page_at_end_clamps(self):
        pag = OutputPaginator(self._lines(10), page_size=10)
        pag.page(1)
        pg = pag.next_page()
        self.assertEqual(pg.page_number, 1)  # clamped

    def test_prev_page(self):
        pag = OutputPaginator(self._lines(30), page_size=10)
        pag.page(3)
        pg = pag.prev_page()
        self.assertEqual(pg.page_number, 2)

    def test_prev_page_at_start_clamps(self):
        pag = OutputPaginator(self._lines(10), page_size=10)
        pag.page(1)
        pg = pag.prev_page()
        self.assertEqual(pg.page_number, 1)  # clamped

    # --- first_page / last_page ---
    def test_first_page(self):
        pag = OutputPaginator(self._lines(30), page_size=10)
        pag.page(3)
        pg = pag.first_page()
        self.assertEqual(pg.page_number, 1)

    def test_last_page(self):
        pag = OutputPaginator(self._lines(30), page_size=10)
        pg = pag.last_page()
        self.assertEqual(pg.page_number, 3)

    # --- current_page_number ---
    def test_current_page_number_default(self):
        pag = OutputPaginator(self._lines(10), page_size=10)
        self.assertEqual(pag.current_page_number, 1)

    # --- search_pages ---
    def test_search_pages_finds(self):
        lines = ["apple", "banana", "cherry", "date", "elderberry"]
        pag = OutputPaginator(lines, page_size=2)
        # pages: [apple, banana], [cherry, date], [elderberry]
        result = pag.search_pages("cherry")
        self.assertEqual(result, [2])

    def test_search_pages_multiple(self):
        lines = ["a1", "b1", "a2", "b2", "a3"]
        pag = OutputPaginator(lines, page_size=2)
        result = pag.search_pages("a")
        self.assertEqual(result, [1, 2, 3])

    def test_search_pages_no_match(self):
        pag = OutputPaginator(["hello"], page_size=10)
        result = pag.search_pages("xyz")
        self.assertEqual(result, [])

    def test_search_pages_regex(self):
        lines = ["code 200", "code 404", "code 500"]
        pag = OutputPaginator(lines, page_size=2)
        result = pag.search_pages(r"code [45]\d{2}")
        self.assertEqual(result, [1, 2])

    # --- page_size=1 ---
    def test_page_size_one(self):
        pag = OutputPaginator(["a", "b", "c"], page_size=1)
        self.assertEqual(pag.total_pages, 3)
        pg = pag.page(2)
        self.assertEqual(pg.content, ["b"])


if __name__ == "__main__":
    unittest.main()
