"""Tests for ArenaMode (T511)."""
import pytest

from lidco.agents.arena import ArenaEntry, ArenaMode, ArenaResult


@pytest.fixture
def arena():
    return ArenaMode(models=["model-a", "model-b"])


def test_run_returns_arena_result(arena):
    result = arena.run("write hello world")
    assert isinstance(result, ArenaResult)
    assert result.task == "write hello world"


def test_run_creates_entry_per_model(arena):
    result = arena.run("task")
    assert len(result.entries) == 2
    assert {e.model for e in result.entries} == {"model-a", "model-b"}


def test_run_winner_is_none_initially(arena):
    result = arena.run("task")
    assert result.winner is None


def test_run_uses_model_fn(arena):
    def fn(model, task):
        return (f"output-{model}", 10)

    result = arena.run("t", model_fn=fn)
    outputs = {e.model: e.output for e in result.entries}
    assert outputs["model-a"] == "output-model-a"
    assert outputs["model-b"] == "output-model-b"


def test_run_handles_model_fn_exception(arena):
    def fn(model, task):
        if model == "model-a":
            raise RuntimeError("fail")
        return ("ok", 5)

    result = arena.run("t", model_fn=fn)
    entry_a = next(e for e in result.entries if e.model == "model-a")
    assert "[error:" in entry_a.output
    assert entry_a.token_count == 0


def test_run_appends_to_history(arena):
    arena.run("t1")
    arena.run("t2")
    assert len(arena.history()) == 2


def test_select_winner_returns_new_result(arena):
    result = arena.run("t")
    new_result = arena.select_winner(result, 0)
    assert new_result is not result
    assert new_result.winner is not None
    assert new_result.winner.model == result.entries[0].model


def test_select_winner_method_is_human(arena):
    result = arena.run("t")
    new_result = arena.select_winner(result, 1)
    assert new_result.selection_method == "human"


def test_auto_select_picks_highest_score(arena):
    result = arena.run("t")
    # Manually set scores
    result.entries[0].score = 0.9
    result.entries[1].score = 0.5
    new_result = arena.auto_select(result)
    assert new_result.winner.model == "model-a"
    assert new_result.selection_method == "auto_score"


def test_auto_select_with_test_fn_prefers_passing(arena):
    result = arena.run("t")
    # entry[0] stub output contains "model-a"; entry[1] contains "model-b"
    def test_fn(output):
        return "model-b" in output

    result.entries[0].score = 0.9
    result.entries[1].score = 0.1
    new_result = arena.auto_select(result, test_fn=test_fn)
    # model-b passes test even with lower score, so it wins
    assert new_result.winner.model == "model-b"
    assert new_result.selection_method == "auto_test"


def test_auto_select_empty_entries():
    arena = ArenaMode(models=[])
    result = arena.run("t")
    new_result = arena.auto_select(result)
    assert new_result.winner is None


def test_win_rates_empty_history(arena):
    rates = arena.win_rates()
    assert rates == {}


def test_win_rates_computed_correctly(arena):
    r1 = arena.run("t1")
    r2 = arena.run("t2")
    arena.select_winner(r1, 0)  # model-a wins
    arena.select_winner(r2, 0)  # model-a wins again
    rates = arena.win_rates()
    assert rates["model-a"] == pytest.approx(1.0)
    assert rates["model-b"] == pytest.approx(0.0)


def test_format_comparison_returns_table(arena):
    result = arena.run("t")
    table = arena.format_comparison(result)
    assert "| Model |" in table
    assert "model-a" in table
    assert "model-b" in table


def test_history_returns_copy(arena):
    arena.run("t")
    h = arena.history()
    h.clear()
    assert len(arena.history()) == 1  # original unaffected
