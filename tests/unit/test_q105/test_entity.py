"""Tests for src/lidco/domain/entity.py — Entity, TimestampedEntity."""
import time
import pytest
from lidco.domain.entity import Entity, TimestampedEntity


class TestEntity:
    def test_auto_id(self):
        e = Entity()
        assert len(e.id) > 0

    def test_explicit_id(self):
        e = Entity("my-id")
        assert e.id == "my-id"

    def test_equality_same_id(self):
        e1 = Entity("x")
        e2 = Entity("x")
        assert e1 == e2

    def test_equality_different_id(self):
        e1 = Entity("x")
        e2 = Entity("y")
        assert e1 != e2

    def test_equality_different_type(self):
        e1 = Entity("x")
        assert e1 != "x"

    def test_hash_same_id(self):
        e1 = Entity("x")
        e2 = Entity("x")
        assert hash(e1) == hash(e2)

    def test_hash_different_id(self):
        e1 = Entity("x")
        e2 = Entity("y")
        assert hash(e1) != hash(e2)

    def test_usable_in_set(self):
        e1 = Entity("x")
        e2 = Entity("x")
        s = {e1, e2}
        assert len(s) == 1

    def test_version_starts_at_1(self):
        e = Entity()
        assert e.version == 1

    def test_touch_increments_version(self):
        e = Entity()
        e.touch()
        assert e.version == 2

    def test_touch_updates_timestamp(self):
        e = Entity()
        before = e.updated_at
        time.sleep(0.01)
        e.touch()
        assert e.updated_at > before

    def test_created_at_set(self):
        before = time.time()
        e = Entity()
        after = time.time()
        assert before <= e.created_at <= after

    def test_to_dict(self):
        e = Entity("my-id")
        d = e.to_dict()
        assert d["id"] == "my-id"
        assert "created_at" in d
        assert "version" in d

    def test_repr(self):
        e = Entity("x")
        assert "Entity" in repr(e)
        assert "x" in repr(e)

    def test_different_subclasses_not_equal(self):
        class A(Entity): pass
        class B(Entity): pass
        assert A("x") != B("x")


class TestTimestampedEntity:
    def test_not_deleted_initially(self):
        e = TimestampedEntity()
        assert e.is_deleted is False
        assert e.deleted_at is None

    def test_soft_delete(self):
        e = TimestampedEntity()
        e.soft_delete()
        assert e.is_deleted is True
        assert e.deleted_at is not None

    def test_restore(self):
        e = TimestampedEntity()
        e.soft_delete()
        e.restore()
        assert e.is_deleted is False
        assert e.deleted_at is None

    def test_soft_delete_increments_version(self):
        e = TimestampedEntity()
        v0 = e.version
        e.soft_delete()
        assert e.version == v0 + 1

    def test_to_dict_includes_deleted(self):
        e = TimestampedEntity()
        d = e.to_dict()
        assert "is_deleted" in d
        assert "deleted_at" in d
