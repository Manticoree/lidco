"""Tests for lidco.cli.commands.q129_cmds."""
import asyncio
import pytest


def _make_registry():
    from lidco.cli.commands.registry import CommandRegistry
    reg = CommandRegistry()
    import lidco.cli.commands.q129_cmds as mod
    mod._state.clear()
    mod.register(reg)
    return reg


def run(coro):
    return asyncio.run(coro)


class TestMetricsCmds:
    def setup_method(self):
        self.reg = _make_registry()
        self.handler = self.reg.get("metrics").handler

    def test_no_args_usage(self):
        result = run(self.handler(""))
        assert "Usage" in result or "metrics" in result.lower()

    def test_record(self):
        result = run(self.handler("record cpu 0.75"))
        assert "cpu" in result

    def test_record_non_numeric(self):
        result = run(self.handler("record cpu notanumber"))
        assert "number" in result.lower() or "invalid" in result.lower()

    def test_show_empty(self):
        result = run(self.handler("show"))
        assert "No metrics" in result or "metric" in result.lower()

    def test_show_after_record(self):
        run(self.handler("record mem 512"))
        result = run(self.handler("show"))
        assert "mem" in result

    def test_show_specific(self):
        run(self.handler("record disk 100"))
        result = run(self.handler("show disk"))
        assert "disk" in result

    def test_show_specific_missing(self):
        result = run(self.handler("show ghost"))
        assert "ghost" in result or "no data" in result.lower()

    def test_agg_avg(self):
        run(self.handler("record score 10"))
        run(self.handler("record score 20"))
        result = run(self.handler("agg score avg"))
        assert "15.0" in result or "15" in result

    def test_agg_no_args(self):
        result = run(self.handler("agg"))
        assert "Usage" in result

    def test_agg_bad_fn(self):
        run(self.handler("record x 1"))
        result = run(self.handler("agg x bogus"))
        assert "bogus" in result or "unknown" in result.lower() or "error" in result.lower()

    def test_clear_specific(self):
        run(self.handler("record x 1"))
        result = run(self.handler("clear x"))
        assert "x" in result.lower() or "clear" in result.lower()

    def test_clear_all(self):
        run(self.handler("record a 1"))
        run(self.handler("record b 2"))
        result = run(self.handler("clear"))
        assert "clear" in result.lower() or "all" in result.lower()

    def test_metrics_registered(self):
        assert self.reg.get("metrics") is not None


class TestHealthCmds:
    def setup_method(self):
        self.reg = _make_registry()
        self.handler = self.reg.get("health").handler

    def test_no_args_usage(self):
        result = run(self.handler(""))
        assert "Usage" in result or "health" in result.lower()

    def test_check_no_checks(self):
        result = run(self.handler("check"))
        assert "No health checks" in result or "registered" in result.lower()

    def test_status_no_checks(self):
        result = run(self.handler("status"))
        assert "healthy" in result.lower()

    def test_health_registered(self):
        assert self.reg.get("health") is not None

    def test_check_unknown_subcommand(self):
        result = run(self.handler("bogus"))
        assert "Usage" in result or "health" in result.lower()

    def test_status_returns_summary(self):
        result = run(self.handler("status"))
        assert "healthy" in result.lower()
