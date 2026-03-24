"""Tests for ArenaLeaderboard (T524)."""
import time
import pytest

from lidco.agents.arena_leaderboard import ArenaLeaderboard, ModelStats, VoteRecord


@pytest.fixture
def lb(tmp_path):
    return ArenaLeaderboard(db_path=tmp_path / "lb.db")


def _vote(model_a, model_b, winner, task_type="coding", prompt_hash="abc"):
    return VoteRecord(
        model_a=model_a,
        model_b=model_b,
        winner=winner,
        task_type=task_type,
        prompt_hash=prompt_hash,
        timestamp=time.time(),
    )


# ---- record_vote ----

def test_record_vote_no_error(lb):
    lb.record_vote(_vote("m-a", "m-b", "m-a"))


def test_record_vote_multiple(lb):
    lb.record_vote(_vote("m-a", "m-b", "m-a"))
    lb.record_vote(_vote("m-a", "m-b", "m-b"))
    stats = lb.stats("coding")
    assert len(stats) == 2


# ---- stats ----

def test_stats_empty(lb):
    assert lb.stats("coding") == []


def test_stats_win_rate(lb):
    lb.record_vote(_vote("m-a", "m-b", "m-a"))
    lb.record_vote(_vote("m-a", "m-b", "m-a"))
    lb.record_vote(_vote("m-a", "m-b", "m-b"))
    stats = {s.model: s for s in lb.stats("coding")}
    assert stats["m-a"].wins == 2
    assert stats["m-a"].appearances == 3
    assert stats["m-a"].win_rate == pytest.approx(2 / 3)


def test_stats_sorted_by_win_rate(lb):
    lb.record_vote(_vote("m-a", "m-b", "m-b"))
    lb.record_vote(_vote("m-a", "m-b", "m-b"))
    stats = lb.stats("coding")
    assert stats[0].model == "m-b"


def test_stats_different_task_types(lb):
    lb.record_vote(_vote("m-a", "m-b", "m-a", task_type="coding"))
    lb.record_vote(_vote("m-a", "m-b", "m-b", task_type="review"))
    coding = lb.stats("coding")
    review = lb.stats("review")
    assert len(coding) == 2
    assert len(review) == 2


# ---- best_model ----

def test_best_model_none_when_insufficient_data(lb):
    lb.record_vote(_vote("m-a", "m-b", "m-a"))
    lb.record_vote(_vote("m-a", "m-b", "m-a"))
    # Only 2 appearances — below threshold of 3
    assert lb.best_model("coding") is None


def test_best_model_returns_top_model(lb):
    for _ in range(3):
        lb.record_vote(_vote("m-a", "m-b", "m-a"))
    assert lb.best_model("coding") == "m-a"


# ---- leaderboard ----

def test_leaderboard_empty(lb):
    assert lb.leaderboard() == []


def test_leaderboard_aggregates_all_types(lb):
    lb.record_vote(_vote("m-a", "m-b", "m-a", task_type="coding"))
    lb.record_vote(_vote("m-a", "m-b", "m-b", task_type="review"))
    board = lb.leaderboard()
    assert len(board) == 2


def test_leaderboard_sorted_by_win_rate(lb):
    lb.record_vote(_vote("m-a", "m-b", "m-b"))
    lb.record_vote(_vote("m-a", "m-b", "m-b"))
    board = lb.leaderboard()
    assert board[0].model == "m-b"


# ---- suggest_models ----

def test_suggest_models_defaults_when_no_data(lb):
    a, b = lb.suggest_models("coding")
    assert isinstance(a, str)
    assert isinstance(b, str)


def test_suggest_models_returns_top_two(lb):
    for _ in range(3):
        lb.record_vote(_vote("m-a", "m-b", "m-a"))
    for _ in range(3):
        lb.record_vote(_vote("m-b", "m-c", "m-b"))
    a, b = lb.suggest_models("coding")
    assert a == "m-a"
    assert b in ("m-b", "m-c")
