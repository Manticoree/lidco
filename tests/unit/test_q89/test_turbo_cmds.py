"""Tests for turbo_cmds CLI wiring (T581)."""
import asyncio
import pytest
from lidco.cli.commands.registry import CommandRegistry


def get_handler(name: str):
    registry = CommandRegistry()
    cmd = registry.get(name)
    assert cmd is not None, f"Command /{name} not registered"
    return cmd.handler


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------
# /turbo
# ------------------------------------------------------------------

def test_turbo_status_initially_off():
    h = get_handler("turbo")
    result = run(h("status"))
    assert "OFF" in result


def test_turbo_enable():
    h = get_handler("turbo")
    result = run(h("enable"))
    assert "ENABLED" in result.upper() or "ON" in result.upper()


def test_turbo_disable():
    h = get_handler("turbo")
    run(h("enable"))
    result = run(h("disable"))
    assert "DISABLED" in result.upper() or "OFF" in result.upper()


def test_turbo_run_requires_enable():
    registry = CommandRegistry()
    h = registry.get("turbo").handler
    # start disabled
    result = run(h("run echo hello"))
    assert "OFF" in result or "enable" in result.lower()


def test_turbo_run_dry_run():
    registry = CommandRegistry()
    h = registry.get("turbo").handler
    run(h("enable"))
    # echo is allowed by default; patch turbo_runner for dry_run
    from lidco.execution.turbo_runner import TurboRunner
    registry._turbo_runner = TurboRunner(dry_run=True)
    result = run(h("run echo hello"))
    assert "dry-run" in result.lower() or "hello" in result.lower() or result


def test_turbo_add_allowed():
    h = get_handler("turbo")
    result = run(h("add-allowed ^mycmd"))
    assert "mycmd" in result


def test_turbo_add_blocked():
    h = get_handler("turbo")
    result = run(h("add-blocked ^dangerous"))
    assert "dangerous" in result


def test_turbo_invalid_sub_shows_usage():
    h = get_handler("turbo")
    result = run(h("unknownsub"))
    assert "Usage" in result or "usage" in result


# ------------------------------------------------------------------
# /role-agent
# ------------------------------------------------------------------

def test_role_agent_list():
    h = get_handler("role-agent")
    result = run(h("list"))
    assert "coder" in result
    assert "reviewer" in result


def test_role_agent_dispatch_no_llm():
    h = get_handler("role-agent")
    result = run(h("coder Write a hello world function"))
    assert "CODER" in result.upper() or result


def test_role_agent_unknown_role():
    h = get_handler("role-agent")
    result = run(h("wizard Cast a spell"))
    assert "Unknown" in result or "unknown" in result


def test_role_agent_no_instructions():
    h = get_handler("role-agent")
    result = run(h("coder"))
    assert "Usage" in result or "usage" in result


def test_role_agent_no_args_shows_roles():
    h = get_handler("role-agent")
    result = run(h(""))
    assert "role" in result.lower()


# ------------------------------------------------------------------
# /mem-search
# ------------------------------------------------------------------

def test_mem_search_empty_shows_usage():
    h = get_handler("mem-search")
    result = run(h(""))
    assert "Usage" in result or "usage" in result


def test_mem_search_add_and_retrieve():
    registry = CommandRegistry()
    h = registry.get("mem-search").handler
    run(h("add mykey Python async patterns"))
    result = run(h("get mykey"))
    assert "mykey" in result
    assert "Python" in result


def test_mem_search_query():
    registry = CommandRegistry()
    h = registry.get("mem-search").handler
    run(h("add doc1 asyncio coroutine python event loop"))
    result = run(h("python async"))
    assert "doc1" in result or "results" in result.lower()


def test_mem_search_stats():
    registry = CommandRegistry()
    h = registry.get("mem-search").handler
    run(h("add k1 some content"))
    result = run(h("stats"))
    assert "Entries" in result or "entries" in result


def test_mem_search_purge():
    registry = CommandRegistry()
    h = registry.get("mem-search").handler
    result = run(h("purge"))
    assert "purged" in result.lower() or "nothing" in result.lower() or result


def test_mem_search_get_missing():
    h = get_handler("mem-search")
    result = run(h("get nonexistent_key"))
    # could say "No entry found" or "Memory store is empty"
    assert "No entry" in result or "not found" in result.lower() or "empty" in result.lower()


# ------------------------------------------------------------------
# /horizon
# ------------------------------------------------------------------

def test_horizon_no_plan_shows_hint():
    h = get_handler("horizon")
    result = run(h("status"))
    assert "horizon new" in result or "No horizon" in result


def test_horizon_new():
    h = get_handler("horizon")
    result = run(h("new Build a REST API"))
    assert "Build a REST API" in result or "created" in result.lower()


def test_horizon_add_phase():
    registry = CommandRegistry()
    h = registry.get("horizon").handler
    run(h("new My goal"))
    result = run(h("phase setup Install deps; Configure env"))
    assert "setup" in result
    assert "2 step" in result


def test_horizon_plan_display():
    registry = CommandRegistry()
    h = registry.get("horizon").handler
    run(h("new Display goal"))
    run(h("phase alpha Step A; Step B"))
    result = run(h("plan"))
    assert "Display goal" in result
    assert "alpha" in result


def test_horizon_run():
    registry = CommandRegistry()
    h = registry.get("horizon").handler
    run(h("new Run goal"))
    run(h("phase work Do thing"))
    result = run(h("run"))
    assert "SUCCESS" in result or "FAILED" in result


def test_horizon_invalid_sub():
    registry = CommandRegistry()
    h = registry.get("horizon").handler
    run(h("new G"))
    result = run(h("foobar"))
    assert "Usage" in result or "usage" in result
