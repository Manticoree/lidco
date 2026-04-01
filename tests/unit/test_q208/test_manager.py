"""Tests for lidco.bootstrap.manager — BootstrapManager."""

from __future__ import annotations

import unittest

from lidco.bootstrap.manager import (
    BootstrapError,
    BootstrapManager,
    BootstrapPhase,
    BootstrapResult,
    BootstrapStep,
)


class TestBootstrapPhase(unittest.TestCase):
    def test_enum_values(self) -> None:
        assert BootstrapPhase.CONFIG == "config"
        assert BootstrapPhase.READY == "ready"


class TestBootstrapManager(unittest.TestCase):
    def test_add_step_and_run_empty(self) -> None:
        bm = BootstrapManager()
        results = bm.run()
        assert results == []
        assert not bm.is_ready()

    def test_run_simple_steps(self) -> None:
        bm = BootstrapManager()
        bm.add_step(BootstrapStep(name="load_config", phase=BootstrapPhase.CONFIG))
        bm.add_step(BootstrapStep(name="init_db", phase=BootstrapPhase.DATABASE))
        results = bm.run()
        assert len(results) == 2
        assert all(r.success for r in results)
        assert bm.is_ready()

    def test_handler_called(self) -> None:
        called: list[str] = []
        bm = BootstrapManager()
        bm.add_step(BootstrapStep(
            name="setup",
            phase=BootstrapPhase.CONFIG,
            handler=lambda: called.append("setup"),
        ))
        bm.run()
        assert called == ["setup"]

    def test_handler_failure(self) -> None:
        def bad_handler() -> None:
            raise RuntimeError("boom")

        bm = BootstrapManager()
        bm.add_step(BootstrapStep(
            name="fail_step",
            phase=BootstrapPhase.CONFIG,
            handler=bad_handler,
        ))
        results = bm.run()
        assert len(results) == 1
        assert not results[0].success
        assert "boom" in results[0].error
        assert not bm.is_ready()

    def test_dependency_order(self) -> None:
        order: list[str] = []
        bm = BootstrapManager()
        bm.add_step(BootstrapStep(
            name="b",
            phase=BootstrapPhase.DATABASE,
            handler=lambda: order.append("b"),
            depends_on=("a",),
        ))
        bm.add_step(BootstrapStep(
            name="a",
            phase=BootstrapPhase.CONFIG,
            handler=lambda: order.append("a"),
        ))
        bm.run()
        assert order == ["a", "b"]

    def test_run_phase(self) -> None:
        bm = BootstrapManager()
        bm.add_step(BootstrapStep(name="cfg1", phase=BootstrapPhase.CONFIG))
        bm.add_step(BootstrapStep(name="db1", phase=BootstrapPhase.DATABASE))
        results = bm.run_phase(BootstrapPhase.CONFIG)
        assert len(results) == 1
        assert results[0].step_name == "cfg1"

    def test_health_check(self) -> None:
        bm = BootstrapManager()
        bm.add_step(BootstrapStep(name="s1", phase=BootstrapPhase.CONFIG))
        bm.run()
        health = bm.health_check()
        assert health == {"s1": True}

    def test_summary(self) -> None:
        bm = BootstrapManager()
        assert "No bootstrap" in bm.summary()
        bm.add_step(BootstrapStep(name="s1", phase=BootstrapPhase.CONFIG))
        bm.run()
        s = bm.summary()
        assert "1/1" in s
        assert "succeeded" in s

    def test_results_returns_copy(self) -> None:
        bm = BootstrapManager()
        bm.add_step(BootstrapStep(name="s1", phase=BootstrapPhase.CONFIG))
        bm.run()
        r1 = bm.results()
        r2 = bm.results()
        assert r1 == r2
        assert r1 is not r2


if __name__ == "__main__":
    unittest.main()
