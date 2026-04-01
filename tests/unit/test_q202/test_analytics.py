"""Tests for lidco.teams.analytics."""

from __future__ import annotations

from lidco.teams.analytics import TeamAnalytics, UsageRecord


class TestUsageRecord:
    def test_defaults(self) -> None:
        r = UsageRecord(user_id="u1", action="query")
        assert r.cost == 0.0
        assert r.tokens == 0
        assert r.timestamp == 0.0


class TestTeamAnalytics:
    def _populated(self) -> TeamAnalytics:
        a = TeamAnalytics("t1")
        a.record("alice", "query", cost=0.01, tokens=100)
        a.record("alice", "edit", cost=0.02, tokens=200)
        a.record("bob", "query", cost=0.03, tokens=150)
        return a

    def test_record_and_total_cost(self) -> None:
        a = self._populated()
        assert abs(a.total_cost() - 0.06) < 1e-9

    def test_total_tokens(self) -> None:
        a = self._populated()
        assert a.total_tokens() == 450

    def test_per_member_cost(self) -> None:
        a = self._populated()
        costs = a.per_member_cost()
        assert abs(costs["alice"] - 0.03) < 1e-9
        assert abs(costs["bob"] - 0.03) < 1e-9

    def test_per_member_tokens(self) -> None:
        a = self._populated()
        tokens = a.per_member_tokens()
        assert tokens["alice"] == 300
        assert tokens["bob"] == 150

    def test_activity_timeline(self) -> None:
        a = self._populated()
        timeline = a.activity_timeline(last_n=2)
        assert len(timeline) == 2
        assert timeline[-1].user_id == "bob"

    def test_top_contributors(self) -> None:
        a = self._populated()
        top = a.top_contributors(1)
        assert len(top) == 1
        assert top[0][0] == "alice"
        assert top[0][1] == 2

    def test_summary_contains_team_id(self) -> None:
        a = self._populated()
        s = a.summary()
        assert "t1" in s
        assert "Total records: 3" in s

    def test_empty_analytics(self) -> None:
        a = TeamAnalytics("empty")
        assert a.total_cost() == 0.0
        assert a.total_tokens() == 0
        assert a.top_contributors() == []
