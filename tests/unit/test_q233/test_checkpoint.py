"""Tests for lidco.budget.checkpoint."""
from __future__ import annotations

import json
import time
import unittest

from lidco.budget.checkpoint import BudgetCheckpoint, BudgetCheckpointManager


class TestBudgetCheckpoint(unittest.TestCase):
    def test_defaults(self) -> None:
        cp = BudgetCheckpoint()
        assert cp.session_id == ""
        assert cp.tokens_used == 0
        assert cp.context_limit == 128000

    def test_frozen(self) -> None:
        cp = BudgetCheckpoint()
        with self.assertRaises(AttributeError):
            cp.session_id = "x"  # type: ignore[misc]


class TestBudgetCheckpointManager(unittest.TestCase):
    def test_save_and_load(self) -> None:
        mgr = BudgetCheckpointManager()
        mgr.save("sess1", tokens_used=5000, turns=3)
        cp = mgr.load("sess1")
        assert cp is not None
        assert cp.session_id == "sess1"
        assert cp.tokens_used == 5000
        assert cp.turns == 3

    def test_load_returns_latest(self) -> None:
        mgr = BudgetCheckpointManager()
        mgr.save("s", tokens_used=100)
        mgr.save("s", tokens_used=200)
        cp = mgr.load("s")
        assert cp is not None
        assert cp.tokens_used == 200

    def test_load_missing(self) -> None:
        mgr = BudgetCheckpointManager()
        assert mgr.load("nonexistent") is None

    def test_serialize_deserialize(self) -> None:
        mgr = BudgetCheckpointManager()
        original = mgr.save("sess2", tokens_used=8000, model="gpt-4")
        data = mgr.serialize(original)
        parsed = json.loads(data)
        assert parsed["session_id"] == "sess2"
        restored = mgr.deserialize(data)
        assert restored.session_id == original.session_id
        assert restored.tokens_used == original.tokens_used
        assert restored.model == "gpt-4"

    def test_is_stale(self) -> None:
        mgr = BudgetCheckpointManager()
        old = BudgetCheckpoint(timestamp=time.time() - 100000)
        assert mgr.is_stale(old) is True
        fresh = BudgetCheckpoint(timestamp=time.time())
        assert mgr.is_stale(fresh) is False

    def test_is_stale_custom_age(self) -> None:
        mgr = BudgetCheckpointManager()
        cp = BudgetCheckpoint(timestamp=time.time() - 10)
        assert mgr.is_stale(cp, max_age=5.0) is True
        assert mgr.is_stale(cp, max_age=100.0) is False

    def test_get_all_and_clear(self) -> None:
        mgr = BudgetCheckpointManager()
        mgr.save("a", tokens_used=1)
        mgr.save("b", tokens_used=2)
        assert len(mgr.get_all()) == 2
        mgr.clear()
        assert len(mgr.get_all()) == 0

    def test_summary(self) -> None:
        mgr = BudgetCheckpointManager()
        mgr.save("demo", tokens_used=42)
        text = mgr.summary()
        assert "demo" in text
        assert "1" in text


if __name__ == "__main__":
    unittest.main()
