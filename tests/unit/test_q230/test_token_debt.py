"""Tests for lidco.budget.token_debt."""
from __future__ import annotations

import pytest

from lidco.budget.token_debt import DebtEntry, DebtSummary, TokenDebtTracker


class TestDebtEntry:
    def test_frozen(self) -> None:
        e = DebtEntry(amount=100)
        with pytest.raises(AttributeError):
            e.amount = 200  # type: ignore[misc]

    def test_defaults(self) -> None:
        e = DebtEntry(amount=100)
        assert e.reason == ""
        assert e.repaid == 0
        assert e.timestamp > 0


class TestDebtSummary:
    def test_frozen(self) -> None:
        s = DebtSummary()
        with pytest.raises(AttributeError):
            s.total_debt = 1  # type: ignore[misc]

    def test_defaults(self) -> None:
        s = DebtSummary()
        assert s.total_debt == 0
        assert s.ceiling == 50000


class TestTokenDebtTracker:
    def test_incur_adds_entry(self) -> None:
        t = TokenDebtTracker()
        entry = t.incur(1000, "overflow")
        assert entry.amount == 1000
        assert entry.reason == "overflow"
        assert t.outstanding() == 1000

    def test_repay_fifo(self) -> None:
        t = TokenDebtTracker()
        t.incur(500, "first")
        t.incur(300, "second")
        repaid = t.repay(600)
        assert repaid == 600
        assert t.outstanding() == 200
        # First entry fully repaid, second partially
        debts = t.get_debts()
        assert debts[0].repaid == 500
        assert debts[1].repaid == 100

    def test_repay_more_than_owed(self) -> None:
        t = TokenDebtTracker()
        t.incur(100)
        repaid = t.repay(500)
        assert repaid == 100
        assert t.outstanding() == 0

    def test_outstanding_empty(self) -> None:
        t = TokenDebtTracker()
        assert t.outstanding() == 0

    def test_is_over_ceiling(self) -> None:
        t = TokenDebtTracker(ceiling=100)
        t.incur(50)
        assert t.is_over_ceiling() is False
        t.incur(60)
        assert t.is_over_ceiling() is True

    def test_get_debts(self) -> None:
        t = TokenDebtTracker()
        t.incur(100, "a")
        t.incur(200, "b")
        debts = t.get_debts()
        assert len(debts) == 2
        assert debts[0].reason == "a"
        assert debts[1].reason == "b"

    def test_get_summary(self) -> None:
        t = TokenDebtTracker(ceiling=1000)
        t.incur(500, "a")
        t.repay(200)
        s = t.get_summary()
        assert s.total_debt == 500
        assert s.total_repaid == 200
        assert s.outstanding == 300
        assert s.entries == 1
        assert s.ceiling == 1000

    def test_clear(self) -> None:
        t = TokenDebtTracker()
        t.incur(100)
        t.incur(200)
        t.clear()
        assert t.outstanding() == 0
        assert t.get_debts() == []

    def test_summary_text(self) -> None:
        t = TokenDebtTracker(ceiling=1000)
        t.incur(500)
        s = t.summary()
        assert "500" in s
        assert "OK" in s

    def test_summary_over_ceiling(self) -> None:
        t = TokenDebtTracker(ceiling=100)
        t.incur(200)
        s = t.summary()
        assert "OVER CEILING" in s
