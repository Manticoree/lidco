"""Tests for Q156 fixes — __all__ exports, EventBus errors, SagaStatus, StructuredLogger levels."""
from __future__ import annotations

import unittest

# ---------------------------------------------------------------------------
# Task 892: __all__ exports for resilience, network, streaming, perf
# ---------------------------------------------------------------------------


class TestResilienceExports(unittest.TestCase):
    """Verify lidco.resilience __all__ and direct imports."""

    def test_all_is_defined(self):
        import lidco.resilience
        self.assertTrue(hasattr(lidco.resilience, "__all__"))
        self.assertIsInstance(lidco.resilience.__all__, list)

    def test_all_is_non_empty(self):
        import lidco.resilience
        self.assertGreater(len(lidco.resilience.__all__), 0)

    def test_retry_executor_importable(self):
        from lidco.resilience import RetryExecutor
        self.assertTrue(callable(RetryExecutor))

    def test_error_boundary_importable(self):
        from lidco.resilience import ErrorBoundary
        self.assertTrue(callable(ErrorBoundary))

    def test_fallback_chain_importable(self):
        from lidco.resilience import FallbackChain
        self.assertTrue(callable(FallbackChain))

    def test_all_entries_importable(self):
        import lidco.resilience
        for name in lidco.resilience.__all__:
            self.assertTrue(
                hasattr(lidco.resilience, name),
                f"{name!r} listed in __all__ but not accessible on the module",
            )


class TestNetworkExports(unittest.TestCase):
    """Verify lidco.network __all__ and direct imports."""

    def test_all_is_defined(self):
        import lidco.network
        self.assertTrue(hasattr(lidco.network, "__all__"))
        self.assertIsInstance(lidco.network.__all__, list)

    def test_connection_pool_importable(self):
        from lidco.network import ConnectionPool
        self.assertTrue(callable(ConnectionPool))

    def test_header_manager_importable(self):
        from lidco.network import HeaderManager
        self.assertTrue(callable(HeaderManager))

    def test_url_parser_importable(self):
        from lidco.network import UrlParser
        self.assertTrue(callable(UrlParser))

    def test_all_entries_importable(self):
        import lidco.network
        for name in lidco.network.__all__:
            self.assertTrue(
                hasattr(lidco.network, name),
                f"{name!r} listed in __all__ but not accessible on the module",
            )


class TestStreamingExports(unittest.TestCase):
    """Verify lidco.streaming __all__ and direct imports."""

    def test_all_is_defined(self):
        import lidco.streaming
        self.assertTrue(hasattr(lidco.streaming, "__all__"))
        self.assertIsInstance(lidco.streaming.__all__, list)

    def test_line_buffer_importable(self):
        from lidco.streaming import LineBuffer
        self.assertTrue(callable(LineBuffer))

    def test_stream_multiplexer_importable(self):
        from lidco.streaming import StreamMultiplexer
        self.assertTrue(callable(StreamMultiplexer))

    def test_all_entries_importable(self):
        import lidco.streaming
        for name in lidco.streaming.__all__:
            self.assertTrue(
                hasattr(lidco.streaming, name),
                f"{name!r} listed in __all__ but not accessible on the module",
            )


class TestPerfExports(unittest.TestCase):
    """Verify lidco.perf __all__ and direct imports."""

    def test_all_is_defined(self):
        import lidco.perf
        self.assertTrue(hasattr(lidco.perf, "__all__"))
        self.assertIsInstance(lidco.perf.__all__, list)

    def test_timing_profiler_importable(self):
        from lidco.perf import TimingProfiler
        self.assertTrue(callable(TimingProfiler))

    def test_bottleneck_detector_importable(self):
        from lidco.perf import BottleneckDetector
        self.assertTrue(callable(BottleneckDetector))

    def test_perf_report_importable(self):
        from lidco.perf import PerfReport
        self.assertTrue(callable(PerfReport))

    def test_all_entries_importable(self):
        import lidco.perf
        for name in lidco.perf.__all__:
            self.assertTrue(
                hasattr(lidco.perf, name),
                f"{name!r} listed in __all__ but not accessible on the module",
            )


# ---------------------------------------------------------------------------
# Task 894: EventBus error capture
# ---------------------------------------------------------------------------

from lidco.events.bus import EventBus, Event  # noqa: E402


class TestEventBusErrorCapture(unittest.TestCase):
    """EventBus.publish should capture handler errors in last_errors."""

    def setUp(self):
        self.bus = EventBus()

    def test_no_errors_initially(self):
        self.assertEqual(self.bus.last_errors, [])

    def test_successful_publish_has_no_errors(self):
        called = []
        self.bus.subscribe("evt", lambda e: called.append(e.type))
        self.bus.publish("evt", {"key": "val"})
        self.assertEqual(self.bus.last_errors, [])
        self.assertEqual(called, ["evt"])

    def test_failing_handler_captured_in_last_errors(self):
        def boom(event: Event) -> None:
            raise RuntimeError("kaboom")

        self.bus.subscribe("evt", boom)
        self.bus.publish("evt")
        errors = self.bus.last_errors
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertIn("kaboom", str(errors[0]))

    def test_successful_publish_clears_previous_errors(self):
        self.bus.subscribe("fail", lambda e: (_ for _ in ()).throw(ValueError("bad")))
        self.bus.publish("fail")
        self.assertEqual(len(self.bus.last_errors), 1)

        # A successful publish to another event type should clear errors
        self.bus.subscribe("ok", lambda e: None)
        self.bus.publish("ok")
        self.assertEqual(self.bus.last_errors, [])

    def test_multiple_handlers_one_failing(self):
        results = []
        self.bus.subscribe("mixed", lambda e: results.append("a"))
        self.bus.subscribe("mixed", lambda e: (_ for _ in ()).throw(TypeError("oops")))
        self.bus.subscribe("mixed", lambda e: results.append("c"))

        self.bus.publish("mixed")
        # The non-failing handlers still run
        self.assertEqual(results, ["a", "c"])
        # Exactly one error captured
        self.assertEqual(len(self.bus.last_errors), 1)
        self.assertIsInstance(self.bus.last_errors[0], TypeError)

    def test_multiple_handlers_all_failing(self):
        self.bus.subscribe("bad", lambda e: (_ for _ in ()).throw(ValueError("v")))
        self.bus.subscribe("bad", lambda e: (_ for _ in ()).throw(KeyError("k")))

        self.bus.publish("bad")
        self.assertEqual(len(self.bus.last_errors), 2)

    def test_publish_returns_event(self):
        event = self.bus.publish("test.event", {"x": 1})
        self.assertIsInstance(event, Event)
        self.assertEqual(event.type, "test.event")
        self.assertEqual(event.data, {"x": 1})

    def test_last_errors_is_copy(self):
        """Mutating the returned list should not affect internal state."""
        self.bus.subscribe("err", lambda e: (_ for _ in ()).throw(RuntimeError("r")))
        self.bus.publish("err")
        errs = self.bus.last_errors
        errs.clear()
        # Internal list unaffected
        self.assertEqual(len(self.bus.last_errors), 1)


# ---------------------------------------------------------------------------
# Task 895: SagaStatus states
# ---------------------------------------------------------------------------

from lidco.saga.coordinator import SagaCoordinator, SagaStatus, SagaResult  # noqa: E402


class TestSagaStatusStates(unittest.TestCase):
    """SagaCoordinator sets correct SagaStatus through its lifecycle."""

    def test_saga_status_enum_values(self):
        self.assertEqual(SagaStatus.PENDING.value, "pending")
        self.assertEqual(SagaStatus.RUNNING.value, "running")
        self.assertEqual(SagaStatus.COMPLETED.value, "completed")
        self.assertEqual(SagaStatus.COMPENSATING.value, "compensating")
        self.assertEqual(SagaStatus.FAILED.value, "failed")

    def test_successful_execution_returns_completed(self):
        coord = SagaCoordinator()
        coord.add_step("s1", action=lambda ctx: "ok", compensation=lambda ctx: None)
        result = coord.execute()
        self.assertEqual(result.status, SagaStatus.COMPLETED)
        self.assertIn("s1", result.steps_completed)

    def test_failed_step_returns_failed_status(self):
        coord = SagaCoordinator()
        coord.add_step("s1", action=lambda ctx: "ok", compensation=lambda ctx: None)
        coord.add_step(
            "s2",
            action=lambda ctx: (_ for _ in ()).throw(RuntimeError("fail")),
            compensation=lambda ctx: None,
        )
        result = coord.execute()
        self.assertEqual(result.status, SagaStatus.FAILED)
        self.assertIn("Step 's2' failed", result.error)

    def test_compensation_runs_on_failure(self):
        compensated = []
        coord = SagaCoordinator()
        coord.add_step("s1", action=lambda ctx: "ok", compensation=lambda ctx: compensated.append("s1"))
        coord.add_step(
            "s2",
            action=lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")),
            compensation=lambda ctx: compensated.append("s2"),
        )
        result = coord.execute()
        # s2 was never completed so only s1 is compensated
        self.assertEqual(compensated, ["s1"])
        self.assertIn("s1", result.steps_compensated)

    def test_completed_steps_tracked(self):
        coord = SagaCoordinator()
        coord.add_step("a", action=lambda ctx: 1, compensation=lambda ctx: None)
        coord.add_step("b", action=lambda ctx: 2, compensation=lambda ctx: None)
        result = coord.execute()
        self.assertEqual(result.steps_completed, ["a", "b"])

    def test_result_contains_step_data(self):
        coord = SagaCoordinator()
        coord.add_step("calc", action=lambda ctx: 42, compensation=lambda ctx: None)
        result = coord.execute()
        self.assertEqual(result.data["calc"], 42)

    def test_saga_result_has_saga_id(self):
        coord = SagaCoordinator()
        coord.add_step("x", action=lambda ctx: None, compensation=lambda ctx: None)
        result = coord.execute()
        self.assertIsInstance(result.saga_id, str)
        self.assertTrue(len(result.saga_id) > 0)

    def test_empty_saga_completes(self):
        coord = SagaCoordinator()
        result = coord.execute()
        self.assertEqual(result.status, SagaStatus.COMPLETED)
        self.assertEqual(result.steps_completed, [])


# ---------------------------------------------------------------------------
# Task 896: StructuredLogger level validation
# ---------------------------------------------------------------------------

from lidco.logging.structured_logger import StructuredLogger, LogRecord, LEVEL_ORDER  # noqa: E402


class TestStructuredLoggerLevels(unittest.TestCase):
    """StructuredLogger validates log levels and filters correctly."""

    def test_debug_level_works(self):
        logger = StructuredLogger("test", min_level="debug")
        logger.debug("hello")
        self.assertEqual(len(logger.records), 1)
        self.assertEqual(logger.records[0].level, "debug")

    def test_info_level_works(self):
        logger = StructuredLogger("test")
        logger.info("hello")
        self.assertEqual(len(logger.records), 1)
        self.assertEqual(logger.records[0].level, "info")

    def test_warning_level_works(self):
        logger = StructuredLogger("test")
        logger.warning("warn msg")
        records = [r for r in logger.records if r.level == "warning"]
        self.assertEqual(len(records), 1)

    def test_error_level_works(self):
        logger = StructuredLogger("test")
        logger.error("err msg")
        records = [r for r in logger.records if r.level == "error"]
        self.assertEqual(len(records), 1)

    def test_critical_level_works(self):
        logger = StructuredLogger("test")
        logger.critical("crit msg")
        records = [r for r in logger.records if r.level == "critical"]
        self.assertEqual(len(records), 1)

    def test_min_level_filters_below(self):
        logger = StructuredLogger("test", min_level="warning")
        logger.debug("skip")
        logger.info("skip")
        logger.warning("keep")
        logger.error("keep")
        self.assertEqual(len(logger.records), 2)

    def test_context_merging(self):
        logger = StructuredLogger("test").with_context(user="alice")
        logger.info("hi", action="login")
        rec = logger.records[0]
        self.assertEqual(rec.context["user"], "alice")
        self.assertEqual(rec.context["action"], "login")

    def test_correlation_id(self):
        logger = StructuredLogger("test").with_correlation("req-123")
        logger.info("request")
        self.assertEqual(logger.records[0].correlation_id, "req-123")

    def test_format_json_roundtrip(self):
        import json
        logger = StructuredLogger("test")
        logger.info("hello")
        text = StructuredLogger.format_json(logger.records[0])
        parsed = json.loads(text)
        self.assertEqual(parsed["level"], "info")
        self.assertEqual(parsed["message"], "hello")
        self.assertEqual(parsed["logger"], "test")

    def test_format_text(self):
        logger = StructuredLogger("test")
        logger.error("boom")
        text = StructuredLogger.format_text(logger.records[0])
        self.assertIn("[ERROR]", text)
        self.assertIn("test", text)
        self.assertIn("boom", text)

    def test_clear_records(self):
        logger = StructuredLogger("test")
        logger.info("a")
        logger.info("b")
        self.assertEqual(len(logger.records), 2)
        logger.clear()
        self.assertEqual(len(logger.records), 0)

    def test_records_property_returns_copy(self):
        logger = StructuredLogger("test")
        logger.info("x")
        recs = logger.records
        recs.clear()
        self.assertEqual(len(logger.records), 1)


if __name__ == "__main__":
    unittest.main()
