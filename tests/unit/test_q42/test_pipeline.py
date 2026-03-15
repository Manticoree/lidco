"""Tests for Q42 — TDDPipeline (Task 286)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.tdd.pipeline import TDDPipeline, TDDResult, TDDStage, _extract_file_path, _strip_fences


# ── Helpers ──────────────────────────────────────────────────────────────────

class TestStripFences:
    def test_removes_python_fence(self):
        code = "```python\nprint('hi')\n```"
        assert _strip_fences(code) == "print('hi')"

    def test_removes_bare_fence(self):
        code = "```\ncode here\n```"
        assert _strip_fences(code) == "code here"

    def test_no_fence_unchanged(self):
        code = "def foo(): pass"
        assert _strip_fences(code) == "def foo(): pass"


class TestExtractFilePath:
    def test_extracts_test_file(self):
        text = "## Test File Location\ntests/unit/test_foo.py\n## Next"
        assert _extract_file_path(text, "Test File Location") == "tests/unit/test_foo.py"

    def test_extracts_impl_file(self):
        text = "## Implementation File Location\nsrc/pkg/foo.py\n"
        assert _extract_file_path(text, "Implementation File Location") == "src/pkg/foo.py"

    def test_returns_none_if_missing(self):
        assert _extract_file_path("no sections", "Test File Location") is None

    def test_strips_backticks(self):
        text = "## Test File Location\n`tests/test_x.py`\n"
        assert _extract_file_path(text, "Test File Location") == "tests/test_x.py"


# ── TDDResult ────────────────────────────────────────────────────────────────

class TestTDDResult:
    def test_success_when_done(self):
        r = TDDResult(task="x", stage_reached=TDDStage.DONE)
        assert r.success is True

    def test_not_success_when_failed(self):
        r = TDDResult(task="x", stage_reached=TDDStage.FAILED)
        assert r.success is False

    def test_summary_contains_task(self):
        r = TDDResult(task="my task")
        assert "my task" in r.summary()

    def test_summary_shows_stage(self):
        r = TDDResult(task="x", stage_reached=TDDStage.CODE, cycles=2)
        s = r.summary()
        assert "code" in s
        assert "2" in s


# ── TDDPipeline ───────────────────────────────────────────────────────────────

def _make_session(tmp_path):
    session = MagicMock()
    session.project_dir = tmp_path
    call_count = [0]
    responses = [
        # spec
        "## Goal\nAdd feature.\n## Test File Location\ntest_gen.py\n## Implementation File Location\nimpl_gen.py",
        # test code
        "def test_foo(): assert False",
        # implementation
        "def foo(): return True",
        # verify
        "Looks good.",
    ]
    async def handle(prompt, agent_name=None, **kw):
        resp = MagicMock()
        idx = min(call_count[0], len(responses) - 1)
        resp.content = responses[idx]
        call_count[0] += 1
        return resp
    session.orchestrator.handle = handle
    return session


class TestTDDPipeline:
    def test_pipeline_writes_test_file(self, tmp_path):
        session = _make_session(tmp_path)

        from lidco.tdd.runner import TestRunResult
        mock_runner_results = [
            TestRunResult(passed=False, total=1, n_failed=1),  # RED
            TestRunResult(passed=True, total=1, n_passed=1),   # GREEN
        ]
        run_call = [0]
        def mock_run(target=""):
            r = mock_runner_results[min(run_call[0], len(mock_runner_results)-1)]
            run_call[0] += 1
            return r

        async def run():
            pipeline = TDDPipeline(
                session,
                test_file=str(tmp_path / "test_gen.py"),
                impl_file=str(tmp_path / "impl_gen.py"),
            )
            pipeline._runner.run = mock_run
            return await pipeline.run("add feature")

        result = asyncio.run(run())
        assert result.stage_reached in (TDDStage.DONE, TDDStage.FAILED, TDDStage.RUN_GREEN, TDDStage.VERIFY)

    def test_pipeline_failed_after_max_cycles(self, tmp_path):
        session = _make_session(tmp_path)

        from lidco.tdd.runner import TestRunResult
        always_failing = TestRunResult(passed=False, total=1, n_failed=1)

        async def run():
            pipeline = TDDPipeline(
                session,
                test_file=str(tmp_path / "test_gen.py"),
                impl_file=str(tmp_path / "impl_gen.py"),
                max_cycles=2,
            )
            pipeline._runner.run = lambda *a, **kw: always_failing
            return await pipeline.run("impossible task")

        result = asyncio.run(run())
        assert result.stage_reached == TDDStage.FAILED
        assert result.cycles == 2

    def test_status_callback_fired(self, tmp_path):
        session = _make_session(tmp_path)
        events: list = []

        from lidco.tdd.runner import TestRunResult
        mock_results = [
            TestRunResult(passed=False, n_failed=1),
            TestRunResult(passed=True, n_passed=1),
        ]
        call_idx = [0]
        def mock_run(target=""):
            r = mock_results[min(call_idx[0], 1)]
            call_idx[0] += 1
            return r

        async def run():
            pipeline = TDDPipeline(
                session,
                test_file=str(tmp_path / "t.py"),
                impl_file=str(tmp_path / "i.py"),
                status_callback=lambda stage, msg: events.append(stage),
            )
            pipeline._runner.run = mock_run
            return await pipeline.run("task")

        asyncio.run(run())
        assert "spec" in events
