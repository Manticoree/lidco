"""Tests for src/lidco/repository/unit_of_work.py — UnitOfWork."""
import pytest
from dataclasses import dataclass
from lidco.repository.unit_of_work import UnitOfWork


@dataclass
class User:
    id: str
    name: str


class TestUnitOfWorkBasic:
    def setup_method(self):
        self.uow = UnitOfWork()

    def test_register_new(self):
        u = User(id="1", name="Alice")
        self.uow.register_new(u)
        assert "1" in self.uow.pending_new()

    def test_register_dirty(self):
        u = User(id="2", name="Bob")
        self.uow.register_dirty(u)
        assert "2" in self.uow.pending_dirty()

    def test_register_removed(self):
        u = User(id="3", name="Charlie")
        self.uow.register_removed(u)
        assert "3" in self.uow.pending_removed()

    def test_commit_returns_summary(self):
        u = User(id="1", name="Alice")
        self.uow.register_new(u)
        summary = self.uow.commit()
        assert "1" in summary["new"]
        assert summary["dirty"] == []

    def test_commit_clears_pending(self):
        u = User(id="1", name="Alice")
        self.uow.register_new(u)
        self.uow.commit()
        assert self.uow.pending_new() == []

    def test_rollback_clears_pending(self):
        u = User(id="1", name="Alice")
        self.uow.register_new(u)
        self.uow.rollback()
        assert self.uow.pending_new() == []

    def test_begin_resets_state(self):
        u = User(id="1", name="Alice")
        self.uow.register_new(u)
        self.uow.begin()
        assert self.uow.pending_new() == []

    def test_is_active(self):
        assert not self.uow.is_active()
        self.uow.begin()
        assert self.uow.is_active()
        self.uow.commit()
        assert not self.uow.is_active()

    def test_commit_count(self):
        self.uow.commit()
        self.uow.commit()
        assert self.uow.commit_count() == 2

    def test_register_new_not_added_to_dirty(self):
        u = User(id="1", name="Alice")
        self.uow.register_new(u)
        self.uow.register_dirty(u)
        # new entity should not appear in dirty
        assert "1" not in self.uow.pending_dirty()

    def test_register_removed_removes_from_new(self):
        u = User(id="1", name="Alice")
        self.uow.register_new(u)
        self.uow.register_removed(u)
        assert "1" not in self.uow.pending_new()
        assert "1" in self.uow.pending_removed()

    def test_snapshot_taken_on_first_dirty(self):
        u = User(id="1", name="Alice")
        self.uow.register_dirty(u)
        snap = self.uow.get_snapshot("1")
        assert snap is not None
        assert snap.name == "Alice"

    def test_explicit_entity_id(self):
        u = User(id="1", name="Alice")
        self.uow.register_new(u, entity_id="custom_key")
        assert "custom_key" in self.uow.pending_new()


class TestUnitOfWorkContextManager:
    def test_context_manager_commits(self):
        uow = UnitOfWork()
        with uow:
            u = User(id="1", name="Alice")
            uow.register_new(u)
        assert uow.commit_count() == 1

    def test_context_manager_rollback_on_exception(self):
        uow = UnitOfWork()
        with pytest.raises(ValueError):
            with uow:
                u = User(id="1", name="Alice")
                uow.register_new(u)
                raise ValueError("test error")
        assert uow.pending_new() == []
