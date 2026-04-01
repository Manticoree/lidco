"""Tests for lidco.sdk.lifecycle — PluginLifecycleManager."""

from lidco.sdk.lifecycle import (
    InvalidTransitionError,
    PluginInfo,
    PluginLifecycleManager,
    PluginNotRegisteredError,
    PluginState,
)


class _FakePlugin:
    """Minimal plugin with lifecycle hooks."""

    def __init__(self, *, fail_on: str | None = None):
        self.calls: list[str] = []
        self._fail_on = fail_on

    def on_init(self) -> None:
        self.calls.append("init")
        if self._fail_on == "init":
            raise RuntimeError("init boom")

    def on_activate(self) -> None:
        self.calls.append("activate")
        if self._fail_on == "activate":
            raise RuntimeError("activate boom")

    def on_deactivate(self) -> None:
        self.calls.append("deactivate")

    def on_uninstall(self) -> None:
        self.calls.append("uninstall")


def test_register():
    mgr = PluginLifecycleManager()
    plugin = _FakePlugin()
    info = mgr.register("foo", plugin, version="1.0.0")
    assert isinstance(info, PluginInfo)
    assert info.name == "foo"
    assert info.version == "1.0.0"
    assert info.state == PluginState.REGISTERED
    assert "foo" in mgr


def test_full_lifecycle():
    mgr = PluginLifecycleManager()
    plugin = _FakePlugin()
    mgr.register("bar", plugin)
    mgr.initialize("bar")
    assert mgr.get_info("bar").state == PluginState.INITIALIZED
    mgr.activate("bar")
    assert mgr.is_active("bar") is True
    mgr.deactivate("bar")
    assert mgr.get_info("bar").state == PluginState.DEACTIVATED
    mgr.uninstall("bar")
    assert "bar" not in mgr
    assert plugin.calls == ["init", "activate", "deactivate", "uninstall"]


def test_invalid_transition_raises():
    mgr = PluginLifecycleManager()
    mgr.register("p", _FakePlugin())
    try:
        mgr.activate("p")  # REGISTERED -> ACTIVE not allowed
        assert False, "Expected InvalidTransitionError"
    except InvalidTransitionError as exc:
        assert exc.current_state == PluginState.REGISTERED
        assert exc.target_state == PluginState.ACTIVE


def test_not_registered_raises():
    mgr = PluginLifecycleManager()
    try:
        mgr.initialize("ghost")
        assert False, "Expected PluginNotRegisteredError"
    except PluginNotRegisteredError as exc:
        assert exc.plugin_name == "ghost"


def test_error_state_on_init_failure():
    mgr = PluginLifecycleManager()
    plugin = _FakePlugin(fail_on="init")
    mgr.register("bad", plugin)
    try:
        mgr.initialize("bad")
        assert False, "Expected PluginLifecycleError"
    except Exception:
        pass
    assert mgr.get_info("bad").state == PluginState.ERROR


def test_hot_reload():
    mgr = PluginLifecycleManager()
    old_plugin = _FakePlugin()
    mgr.register("hot", old_plugin)
    mgr.initialize("hot")
    mgr.activate("hot")
    assert mgr.is_active("hot")

    new_plugin = _FakePlugin()
    info = mgr.hot_reload("hot", new_instance=new_plugin)
    assert info.state == PluginState.ACTIVE
    assert old_plugin.calls == ["init", "activate", "deactivate"]
    assert new_plugin.calls == ["init", "activate"]


def test_list_plugins():
    mgr = PluginLifecycleManager()
    mgr.register("b_plugin", _FakePlugin())
    mgr.register("a_plugin", _FakePlugin())
    plugins = mgr.list_plugins()
    assert [p.name for p in plugins] == ["a_plugin", "b_plugin"]


def test_list_by_state():
    mgr = PluginLifecycleManager()
    mgr.register("p1", _FakePlugin())
    mgr.register("p2", _FakePlugin())
    mgr.initialize("p1")
    active = mgr.list_by_state(PluginState.INITIALIZED)
    assert len(active) == 1
    assert active[0].name == "p1"


def test_listener_callback():
    mgr = PluginLifecycleManager()
    transitions: list[tuple[str, PluginState, PluginState]] = []
    mgr.add_listener(lambda name, old, new: transitions.append((name, old, new)))
    mgr.register("x", _FakePlugin())
    mgr.initialize("x")
    assert len(transitions) == 1
    assert transitions[0] == ("x", PluginState.REGISTERED, PluginState.INITIALIZED)


def test_len_and_clear():
    mgr = PluginLifecycleManager()
    mgr.register("a", _FakePlugin())
    mgr.register("b", _FakePlugin())
    assert len(mgr) == 2
    mgr.clear()
    assert len(mgr) == 0
