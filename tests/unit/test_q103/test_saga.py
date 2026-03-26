"""Tests for src/lidco/saga/coordinator.py — SagaCoordinator."""
import pytest
from lidco.saga.coordinator import SagaCoordinator, SagaStatus, SagaStep, SagaResult


class TestSagaCoordinatorBasic:
    def test_empty_saga_completes(self):
        coord = SagaCoordinator()
        result = coord.execute()
        assert result.status == SagaStatus.COMPLETED
        assert result.steps_completed == []

    def test_single_step_success(self):
        coord = SagaCoordinator()
        coord.add_step(
            "reserve",
            action=lambda ctx: "reserved",
            compensation=lambda ctx: None,
        )
        result = coord.execute()
        assert result.status == SagaStatus.COMPLETED
        assert "reserve" in result.steps_completed

    def test_multiple_steps(self):
        coord = SagaCoordinator()
        log = []
        coord.add_step("s1", action=lambda ctx: log.append("s1"), compensation=lambda ctx: None)
        coord.add_step("s2", action=lambda ctx: log.append("s2"), compensation=lambda ctx: None)
        coord.add_step("s3", action=lambda ctx: log.append("s3"), compensation=lambda ctx: None)
        result = coord.execute()
        assert result.status == SagaStatus.COMPLETED
        assert log == ["s1", "s2", "s3"]

    def test_step_result_stored(self):
        coord = SagaCoordinator()
        coord.add_step("charge", action=lambda ctx: "charged_ok", compensation=lambda ctx: None)
        result = coord.execute()
        assert result.data.get("charge") == "charged_ok"

    def test_context_passed_to_steps(self):
        coord = SagaCoordinator()
        received = {}

        def action(ctx):
            received.update(ctx)

        coord.add_step("s1", action=action, compensation=lambda ctx: None)
        coord.execute(context={"order_id": "123"})
        assert received.get("order_id") == "123"


class TestSagaCompensation:
    def test_failed_step_compensates_completed(self):
        coord = SagaCoordinator()
        compensated = []

        def ok_action(ctx): pass
        def fail_action(ctx): raise ValueError("payment failed")
        def compensation(ctx): compensated.append("compensated")

        coord.add_step("reserve", action=ok_action, compensation=compensation)
        coord.add_step("charge", action=fail_action, compensation=lambda ctx: None)
        result = coord.execute()
        assert result.status == SagaStatus.FAILED
        assert "reserve" in result.steps_compensated
        assert "charge" not in result.steps_completed
        assert "reserve" in result.steps_completed

    def test_error_message_in_result(self):
        coord = SagaCoordinator()
        coord.add_step(
            "fail_step",
            action=lambda ctx: (_ for _ in ()).throw(RuntimeError("bad")),
            compensation=lambda ctx: None,
        )
        result = coord.execute()
        assert result.status == SagaStatus.FAILED
        assert "bad" in result.error

    def test_compensation_best_effort(self):
        """Even if compensation fails, saga continues compensating."""
        coord = SagaCoordinator()

        def ok1(ctx): pass
        def ok2(ctx): pass
        def fail_main(ctx): raise ValueError("fail")
        def fail_comp(ctx): raise RuntimeError("comp_fail")
        def ok_comp(ctx): pass

        coord.add_step("s1", action=ok1, compensation=ok_comp)
        coord.add_step("s2", action=ok2, compensation=fail_comp)
        coord.add_step("s3", action=fail_main, compensation=lambda ctx: None)
        result = coord.execute()
        # Should not raise — compensation errors are swallowed
        assert result.status == SagaStatus.FAILED

    def test_reverse_compensation_order(self):
        coord = SagaCoordinator()
        comp_order = []

        def ok(ctx): pass
        def fail(ctx): raise ValueError("x")

        coord.add_step("s1", action=ok, compensation=lambda ctx: comp_order.append("s1"))
        coord.add_step("s2", action=ok, compensation=lambda ctx: comp_order.append("s2"))
        coord.add_step("s3", action=fail, compensation=lambda ctx: None)
        coord.execute()
        assert comp_order == ["s2", "s1"]


class TestSagaCoordinatorHelpers:
    def test_step_count(self):
        coord = SagaCoordinator()
        assert coord.step_count() == 0
        coord.add_step("a", lambda ctx: None, lambda ctx: None)
        assert coord.step_count() == 1

    def test_step_names(self):
        coord = SagaCoordinator()
        coord.add_step("alpha", lambda ctx: None, lambda ctx: None)
        coord.add_step("beta", lambda ctx: None, lambda ctx: None)
        assert coord.step_names() == ["alpha", "beta"]

    def test_chaining(self):
        coord = SagaCoordinator()
        result = coord.add_step("a", lambda ctx: None, lambda ctx: None)
        assert result is coord

    def test_clear(self):
        coord = SagaCoordinator()
        coord.add_step("a", lambda ctx: None, lambda ctx: None)
        coord.clear()
        assert coord.step_count() == 0

    def test_result_has_saga_id(self):
        coord = SagaCoordinator()
        result = coord.execute()
        assert len(result.saga_id) > 0
