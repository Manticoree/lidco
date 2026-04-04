"""Tests for GitLabWiki (Q290)."""

import unittest

from lidco.gitlab.wiki import GitLabWiki, WikiPage


class TestCreatePage(unittest.TestCase):
    def test_create_basic(self):
        wiki = GitLabWiki()
        page = wiki.create_page("Getting Started", "Welcome to the wiki.")
        self.assertIsInstance(page, WikiPage)
        self.assertEqual(page.slug, "getting-started")
        self.assertEqual(page.title, "Getting Started")
        self.assertEqual(page.content, "Welcome to the wiki.")

    def test_empty_title_raises(self):
        wiki = GitLabWiki()
        with self.assertRaises(ValueError):
            wiki.create_page("", "content")

    def test_duplicate_slug_raises(self):
        wiki = GitLabWiki()
        wiki.create_page("Hello", "world")
        with self.assertRaises(ValueError):
            wiki.create_page("Hello", "again")

    def test_slug_normalization(self):
        wiki = GitLabWiki()
        page = wiki.create_page("My Cool Page", "stuff")
        self.assertEqual(page.slug, "my-cool-page")


class TestGetPage(unittest.TestCase):
    def test_get_existing(self):
        wiki = GitLabWiki()
        wiki.create_page("Setup", "instructions")
        page = wiki.get_page("setup")
        self.assertEqual(page.title, "Setup")

    def test_get_missing_raises(self):
        wiki = GitLabWiki()
        with self.assertRaises(KeyError):
            wiki.get_page("nonexistent")


class TestUpdatePage(unittest.TestCase):
    def test_update_content(self):
        wiki = GitLabWiki()
        wiki.create_page("FAQ", "old content")
        updated = wiki.update_page("faq", "new content")
        self.assertEqual(updated.content, "new content")
        self.assertEqual(updated.title, "FAQ")

    def test_update_missing_raises(self):
        wiki = GitLabWiki()
        with self.assertRaises(KeyError):
            wiki.update_page("nope", "content")

    def test_update_preserves_format(self):
        wiki = GitLabWiki()
        wiki.create_page("Test", "v1")
        updated = wiki.update_page("test", "v2")
        self.assertEqual(updated.format, "markdown")


class TestSearch(unittest.TestCase):
    def test_search_by_title(self):
        wiki = GitLabWiki()
        wiki.create_page("Python Guide", "content here")
        wiki.create_page("Rust Guide", "other content")
        results = wiki.search("python")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].slug, "python-guide")

    def test_search_by_content(self):
        wiki = GitLabWiki()
        wiki.create_page("Page", "secret keyword inside")
        results = wiki.search("keyword")
        self.assertEqual(len(results), 1)

    def test_search_empty_query(self):
        wiki = GitLabWiki()
        wiki.create_page("X", "Y")
        self.assertEqual(wiki.search(""), [])
        self.assertEqual(wiki.search("   "), [])

    def test_search_no_match(self):
        wiki = GitLabWiki()
        wiki.create_page("A", "B")
        self.assertEqual(wiki.search("zzz"), [])


class TestListPages(unittest.TestCase):
    def test_empty(self):
        wiki = GitLabWiki()
        self.assertEqual(wiki.list_pages(), [])

    def test_sorted_by_slug(self):
        wiki = GitLabWiki()
        wiki.create_page("Zebra", "z")
        wiki.create_page("Alpha", "a")
        pages = wiki.list_pages()
        self.assertEqual(pages[0].slug, "alpha")
        self.assertEqual(pages[1].slug, "zebra")


if __name__ == "__main__":
    unittest.main()
