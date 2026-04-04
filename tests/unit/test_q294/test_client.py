"""Tests for NotionClient."""
import pytest

from lidco.notion.client import Block, Database, NotionClient, Page


class TestNotionClientPages:
    def test_create_page_returns_page(self):
        c = NotionClient()
        p = c.create_page(None, "My Page", "hello")
        assert isinstance(p, Page)
        assert p.title == "My Page"
        assert p.content == "hello"
        assert p.id

    def test_create_page_empty_title_raises(self):
        c = NotionClient()
        with pytest.raises(ValueError, match="Title"):
            c.create_page(None, "  ", "content")

    def test_get_page_success(self):
        c = NotionClient()
        p = c.create_page(None, "Test")
        fetched = c.get_page(p.id)
        assert fetched.title == "Test"

    def test_get_page_not_found_raises(self):
        c = NotionClient()
        with pytest.raises(KeyError, match="not found"):
            c.get_page("nonexistent")

    def test_update_page_title(self):
        c = NotionClient()
        p = c.create_page(None, "Old Title")
        updated = c.update_page(p.id, title="New Title")
        assert updated.title == "New Title"
        assert updated.content == p.content

    def test_update_page_content(self):
        c = NotionClient()
        p = c.create_page(None, "Title", "old")
        updated = c.update_page(p.id, content="new")
        assert updated.content == "new"
        assert updated.title == "Title"

    def test_delete_page_existing(self):
        c = NotionClient()
        p = c.create_page(None, "Delete Me")
        assert c.delete_page(p.id) is True
        with pytest.raises(KeyError):
            c.get_page(p.id)

    def test_delete_page_nonexistent(self):
        c = NotionClient()
        assert c.delete_page("nope") is False


class TestNotionClientSearch:
    def test_search_by_title(self):
        c = NotionClient()
        c.create_page(None, "Python Guide", "intro")
        c.create_page(None, "Java Guide", "intro")
        results = c.search("Python")
        assert len(results) == 1
        assert results[0].title == "Python Guide"

    def test_search_by_content(self):
        c = NotionClient()
        c.create_page(None, "Notes", "important meeting notes")
        results = c.search("meeting")
        assert len(results) == 1

    def test_search_case_insensitive(self):
        c = NotionClient()
        c.create_page(None, "ABC", "")
        results = c.search("abc")
        assert len(results) == 1

    def test_search_no_results(self):
        c = NotionClient()
        c.create_page(None, "Hello", "world")
        assert c.search("zzz") == []


class TestNotionClientBlocks:
    def test_add_block_to_page(self):
        c = NotionClient()
        p = c.create_page(None, "Page")
        b = c.add_block(p.id, "paragraph", "Hello world")
        assert isinstance(b, Block)
        assert b.content == "Hello world"
        assert b.parent_id == p.id

    def test_get_block(self):
        c = NotionClient()
        p = c.create_page(None, "Page")
        b = c.add_block(p.id, "heading_1", "Title")
        fetched = c.get_block(b.id)
        assert fetched.type == "heading_1"

    def test_get_block_not_found(self):
        c = NotionClient()
        with pytest.raises(KeyError, match="not found"):
            c.get_block("bad_id")

    def test_add_block_updates_page_blocks(self):
        c = NotionClient()
        p = c.create_page(None, "Page")
        c.add_block(p.id, "paragraph", "first")
        c.add_block(p.id, "paragraph", "second")
        page = c.get_page(p.id)
        assert len(page.blocks) == 2


class TestNotionClientDatabases:
    def test_create_database(self):
        c = NotionClient()
        db = c.create_database("Tasks")
        assert isinstance(db, Database)
        assert db.title == "Tasks"

    def test_create_database_empty_title_raises(self):
        c = NotionClient()
        with pytest.raises(ValueError):
            c.create_database("")

    def test_list_databases_empty(self):
        c = NotionClient()
        assert c.list_databases() == []

    def test_list_databases_returns_all(self):
        c = NotionClient()
        c.create_database("DB1")
        c.create_database("DB2")
        assert len(c.list_databases()) == 2

    def test_create_page_in_database(self):
        c = NotionClient()
        db = c.create_database("Tasks")
        p = c.create_page(db.id, "Task 1")
        # Refresh db
        dbs = c.list_databases()
        assert p.id in dbs[0].page_ids
