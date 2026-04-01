"""Tests for lidco.sdk.extension_points — ExtensionPointRegistry."""

import asyncio

from lidco.sdk.extension_points import (
    DuplicateExtensionPointError,
    ExtensionPoint,
    ExtensionPointNotFoundError,
    ExtensionPointRegistry,
    HookPriority,
    HookRegistration,
)


def _make_registry() -> ExtensionPointRegistry:
    return ExtensionPointRegistry()


# ----------------------------------------------------------------- points


def test_define_and_get_point():
    reg = _make_registry()
    pt = reg.define("on_save", description="Fires on file save")
    assert isinstance(pt, ExtensionPoint)
    assert pt.name == "on_save"
    assert pt.description == "Fires on file save"
    fetched = reg.get_point("on_save")
    assert fetched is pt


def test_define_duplicate_raises():
    reg = _make_registry()
    reg.define("on_save")
    try:
        reg.define("on_save")
        assert False, "Expected DuplicateExtensionPointError"
    except DuplicateExtensionPointError as exc:
        assert exc.point_name == "on_save"


def test_get_point_not_found_raises():
    reg = _make_registry()
    try:
        reg.get_point("nonexistent")
        assert False, "Expected ExtensionPointNotFoundError"
    except ExtensionPointNotFoundError as exc:
        assert exc.point_name == "nonexistent"


def test_list_points_sorted():
    reg = _make_registry()
    reg.define("zebra")
    reg.define("alpha")
    reg.define("middle")
    points = reg.list_points()
    names = [p.name for p in points]
    assert names == ["alpha", "middle", "zebra"]


def test_remove_point():
    reg = _make_registry()
    reg.define("temp")
    assert reg.remove_point("temp") is True
    assert "temp" not in reg
    assert reg.remove_point("temp") is False


def test_point_count_and_contains():
    reg = _make_registry()
    assert reg.point_count() == 0
    reg.define("a")
    reg.define("b")
    assert reg.point_count() == 2
    assert "a" in reg
    assert "c" not in reg


# ----------------------------------------------------------------- hooks


def test_add_hook_and_get_hooks():
    reg = _make_registry()
    reg.define("on_load")

    def my_hook(x):
        return x * 2

    registration = reg.add_hook("on_load", my_hook, name="doubler")
    assert isinstance(registration, HookRegistration)
    assert registration.name == "doubler"
    assert registration.is_async is False
    hooks = reg.get_hooks("on_load")
    assert len(hooks) == 1
    assert hooks[0].name == "doubler"


def test_hook_priority_ordering():
    reg = _make_registry()
    reg.define("on_run")
    results = []
    reg.add_hook("on_run", lambda: results.append("low"), priority=HookPriority.LOW, name="low")
    reg.add_hook("on_run", lambda: results.append("high"), priority=HookPriority.HIGH, name="high")
    reg.add_hook("on_run", lambda: results.append("normal"), priority=HookPriority.NORMAL, name="normal")
    hooks = reg.get_hooks("on_run")
    names = [h.name for h in hooks]
    assert names == ["high", "normal", "low"]


def test_remove_hook():
    reg = _make_registry()
    reg.define("on_run")
    reg.add_hook("on_run", lambda: 1, name="a")
    reg.add_hook("on_run", lambda: 2, name="b")
    assert reg.remove_hook("on_run", "a") is True
    assert len(reg.get_hooks("on_run")) == 1
    assert reg.remove_hook("on_run", "a") is False


def test_add_hook_to_nonexistent_point_raises():
    reg = _make_registry()
    try:
        reg.add_hook("nope", lambda: 1)
        assert False, "Expected ExtensionPointNotFoundError"
    except ExtensionPointNotFoundError:
        pass


# ---------------------------------------------------------------- invoke


def test_invoke_sync():
    reg = _make_registry()
    reg.define("calc")
    reg.add_hook("calc", lambda x: x + 1, name="plus1")
    reg.add_hook("calc", lambda x: x * 2, name="times2")
    results = reg.invoke_sync("calc", 5)
    assert results == [6, 10]


def test_invoke_async():
    reg = _make_registry()
    reg.define("async_point")

    async def async_hook(x):
        return x + 10

    reg.add_hook("async_point", async_hook, name="async_one")
    reg.add_hook("async_point", lambda x: x + 1, name="sync_one")
    results = asyncio.run(reg.invoke_async("async_point", 5))
    # sync runs first by priority (both NORMAL, order of insertion)
    assert 15 in results
    assert 6 in results


def test_invoke_async_parallel():
    reg = _make_registry()
    reg.define("parallel")

    async def async_a(x):
        return x + 100

    async def async_b(x):
        return x + 200

    reg.add_hook("parallel", lambda x: x + 1, name="sync")
    reg.add_hook("parallel", async_a, name="a")
    reg.add_hook("parallel", async_b, name="b")
    results = asyncio.run(reg.invoke_async_parallel("parallel", 0))
    assert 1 in results
    assert 100 in results
    assert 200 in results


def test_invoke_sync_skips_async_hooks():
    reg = _make_registry()
    reg.define("mixed")

    async def async_hook():
        return "async"

    reg.add_hook("mixed", lambda: "sync", name="s")
    reg.add_hook("mixed", async_hook, name="a")
    results = reg.invoke_sync("mixed")
    assert results == ["sync"]


def test_clear():
    reg = _make_registry()
    reg.define("a")
    reg.define("b")
    reg.add_hook("a", lambda: 1, name="h")
    reg.clear()
    assert reg.point_count() == 0
    assert reg.hook_count() == 0
