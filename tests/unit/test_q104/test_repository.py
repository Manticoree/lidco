"""Tests for src/lidco/repository/base.py — Repository."""
import pytest
from dataclasses import dataclass
from lidco.repository.base import Repository, EntityNotFoundError


@dataclass
class Item:
    id: str
    name: str
    value: int = 0


class TestRepositoryBasic:
    def setup_method(self):
        self.repo = Repository(entity_type="Item")

    def test_save_and_find_by_id(self):
        item = Item(id="1", name="widget")
        self.repo.save(item)
        found = self.repo.find_by_id("1")
        assert found is item

    def test_find_by_id_missing(self):
        assert self.repo.find_by_id("missing") is None

    def test_get_by_id(self):
        item = Item(id="1", name="widget")
        self.repo.save(item)
        assert self.repo.get_by_id("1") is item

    def test_get_by_id_raises(self):
        with pytest.raises(EntityNotFoundError) as exc:
            self.repo.get_by_id("missing")
        assert exc.value.entity_id == "missing"
        assert exc.value.entity_type == "Item"

    def test_delete_existing(self):
        self.repo.save(Item(id="1", name="x"))
        assert self.repo.delete("1") is True
        assert self.repo.find_by_id("1") is None

    def test_delete_missing(self):
        assert self.repo.delete("nonexistent") is False

    def test_exists(self):
        self.repo.save(Item(id="1", name="x"))
        assert self.repo.exists("1") is True
        assert self.repo.exists("2") is False

    def test_contains(self):
        self.repo.save(Item(id="1", name="x"))
        assert "1" in self.repo
        assert "2" not in self.repo

    def test_len(self):
        assert len(self.repo) == 0
        self.repo.save(Item(id="1", name="x"))
        assert len(self.repo) == 1

    def test_clear(self):
        self.repo.save(Item(id="1", name="x"))
        self.repo.clear()
        assert len(self.repo) == 0

    def test_overwrite_entity(self):
        self.repo.save(Item(id="1", name="old"))
        self.repo.save(Item(id="1", name="new"))
        found = self.repo.get_by_id("1")
        assert found.name == "new"

    def test_all_ids(self):
        self.repo.save(Item(id="b", name="b"))
        self.repo.save(Item(id="a", name="a"))
        assert self.repo.all_ids() == ["a", "b"]


class TestRepositoryQuery:
    def setup_method(self):
        self.repo = Repository(entity_type="Item")
        self.repo.save(Item(id="1", name="apple", value=10))
        self.repo.save(Item(id="2", name="banana", value=20))
        self.repo.save(Item(id="3", name="cherry", value=30))

    def test_find_all(self):
        items = self.repo.find_all()
        assert len(items) == 3

    def test_find_all_with_predicate(self):
        items = self.repo.find_all(lambda e: e.value > 15)
        assert len(items) == 2

    def test_find_one(self):
        item = self.repo.find_one(lambda e: e.name == "banana")
        assert item is not None
        assert item.name == "banana"

    def test_find_one_missing(self):
        item = self.repo.find_one(lambda e: e.name == "missing")
        assert item is None

    def test_count(self):
        assert self.repo.count() == 3

    def test_count_with_predicate(self):
        assert self.repo.count(lambda e: e.value >= 20) == 2
