"""Tests for EnsembleRunner — T487."""
from __future__ import annotations
import pytest
from lidco.agents.ensemble import CandidateResult, EnsembleResult, EnsembleRunner


class TestEnsembleRunner:
    def test_run_returns_ensemble_result(self):
        runner = EnsembleRunner()
        result = runner.run("fix bug", n=3)
        assert isinstance(result, EnsembleResult)
        assert len(result.candidates) == 3

    def test_best_is_from_candidates(self):
        runner = EnsembleRunner()
        result = runner.run("task", n=2)
        assert result.best in result.candidates

    def test_agent_fn_called(self):
        calls = []
        def agent_fn(agent_id, task):
            calls.append(agent_id)
            return f"output_{agent_id}"
        runner = EnsembleRunner(agent_fn=agent_fn)
        runner.run("task", n=3)
        assert len(calls) == 3

    def test_test_fn_used_for_selection(self):
        def agent_fn(agent_id, task):
            return "good" if agent_id == "agent_1" else "bad"
        def test_fn(output):
            return output == "good"
        runner = EnsembleRunner(agent_fn=agent_fn, test_fn=test_fn)
        result = runner.run("task", n=3)
        assert result.best.test_passed
        assert result.best.agent_id == "agent_1"

    def test_selection_reason_included(self):
        runner = EnsembleRunner()
        result = runner.run("task", n=2)
        assert result.selection_reason

    def test_custom_score_fn(self):
        def score_fn(c):
            return 1.0 if "win" in c.output else 0.0
        def agent_fn(agent_id, task):
            return "win" if agent_id == "agent_2" else "lose"
        runner = EnsembleRunner(agent_fn=agent_fn, score_fn=score_fn)
        result = runner.run("task", n=3)
        assert result.best.agent_id == "agent_2"

    def test_n_equals_1(self):
        runner = EnsembleRunner()
        result = runner.run("task", n=1)
        assert len(result.candidates) == 1
        assert result.best is result.candidates[0]

    def test_agent_fn_exception_handled(self):
        def bad_agent(agent_id, task):
            raise RuntimeError("agent failed")
        runner = EnsembleRunner(agent_fn=bad_agent)
        result = runner.run("task", n=2)
        assert all("error" in c.output for c in result.candidates)

    def test_score_no_test_fn(self):
        runner = EnsembleRunner()
        c = CandidateResult(agent_id="a", output="short")
        score = runner.score(c)
        assert 0.0 <= score <= 1.0

    def test_score_test_passed_higher(self):
        runner = EnsembleRunner()
        passed = CandidateResult(agent_id="a", output="x", test_passed=True)
        failed = CandidateResult(agent_id="b", output="x", test_passed=False)
        assert runner.score(passed) > runner.score(failed)

    def test_candidate_result_dataclass(self):
        c = CandidateResult(agent_id="a", output="out", score=0.9, test_passed=True)
        assert c.agent_id == "a"
        assert c.test_passed
