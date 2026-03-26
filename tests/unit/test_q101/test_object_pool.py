"""Tests for src/lidco/core/object_pool.py — ObjectPool."""
import threading
import time
import pytest
from lidco.core.object_pool import ObjectPool, PoolExhausted, PoolStats


class TestObjectPoolBasic:
    def test_acquire_creates_object(self):
        pool = ObjectPool(factory=dict, max_size=5)
        obj = pool.acquire()
        assert isinstance(obj, dict)

    def test_release_returns_to_pool(self):
        pool = ObjectPool(factory=dict, max_size=5)
        obj = pool.acquire()
        pool.release(obj)
        assert pool.pool_size == 1

    def test_acquire_reuses_pooled_object(self):
        pool = ObjectPool(factory=dict, max_size=5)
        obj1 = pool.acquire()
        pool.release(obj1)
        obj2 = pool.acquire()
        assert obj2 is obj1

    def test_release_untracked_is_ignored(self):
        pool = ObjectPool(factory=dict, max_size=5)
        pool.release({"not_tracked": True})  # should not raise

    def test_size_property(self):
        pool = ObjectPool(factory=dict, max_size=5)
        assert pool.size == 0
        obj = pool.acquire()
        assert pool.size == 1
        pool.release(obj)
        assert pool.size == 1  # still 1 (in available pool)

    def test_pool_size_property(self):
        pool = ObjectPool(factory=dict, max_size=5)
        assert pool.pool_size == 0
        obj = pool.acquire()
        pool.release(obj)
        assert pool.pool_size == 1


class TestObjectPoolExhausted:
    def test_exhausted_raises_immediately(self):
        pool = ObjectPool(factory=dict, max_size=2)
        pool.acquire()
        pool.acquire()
        with pytest.raises(PoolExhausted):
            pool.acquire(timeout=0)

    def test_exhausted_after_timeout(self):
        pool = ObjectPool(factory=dict, max_size=1)
        pool.acquire()
        with pytest.raises(PoolExhausted):
            pool.acquire(timeout=0.05)

    def test_not_exhausted_after_release(self):
        pool = ObjectPool(factory=dict, max_size=1)
        obj = pool.acquire()

        def _release():
            time.sleep(0.05)
            pool.release(obj)

        t = threading.Thread(target=_release)
        t.start()
        obj2 = pool.acquire(timeout=1.0)
        t.join()
        assert obj2 is not None


class TestObjectPoolValidation:
    def test_invalid_object_discarded(self):
        counter = {"n": 0}

        def factory():
            counter["n"] += 1
            return {"id": counter["n"]}

        def validate(obj):
            return obj.get("valid", False)

        pool = ObjectPool(factory=factory, max_size=5, validate=validate)
        obj = pool.acquire()
        pool.release(obj)  # obj has no "valid" key → discarded
        assert pool.pool_size == 0

    def test_valid_object_retained(self):
        pool = ObjectPool(factory=lambda: {"valid": True}, max_size=5,
                          validate=lambda o: o.get("valid", False))
        obj = pool.acquire()
        pool.release(obj)
        assert pool.pool_size == 1


class TestObjectPoolContextManager:
    def test_context_manager_releases(self):
        pool = ObjectPool(factory=dict, max_size=5)
        with pool.acquire_context() as obj:
            assert isinstance(obj, dict)
        assert pool.pool_size == 1

    def test_context_manager_releases_on_exception(self):
        pool = ObjectPool(factory=dict, max_size=5)
        with pytest.raises(ValueError):
            with pool.acquire_context() as _:
                raise ValueError("test")
        assert pool.pool_size == 1


class TestObjectPoolStats:
    def test_stats(self):
        pool = ObjectPool(factory=dict, max_size=5)
        obj = pool.acquire()
        pool.release(obj)
        s = pool.stats()
        assert isinstance(s, PoolStats)
        assert s.total_created == 1
        assert s.total_acquired == 1
        assert s.total_released == 1

    def test_drain(self):
        pool = ObjectPool(factory=dict, max_size=5)
        obj = pool.acquire()
        pool.release(obj)
        n = pool.drain()
        assert n == 1
        assert pool.pool_size == 0
