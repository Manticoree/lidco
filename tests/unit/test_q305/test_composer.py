"""Tests for HookComposer."""

import pytest

from lidco.githooks.composer import HookComposer
from lidco.githooks.library import HookDefinition
from lidco.githooks.manager import HookType


def _hook(name: str, hook_type: HookType = HookType.PRE_COMMIT, script: str = "#!/bin/sh\nexit 0") -> HookDefinition:
    return HookDefinition(name=name, type=hook_type, script=script)


class TestHookComposer:
    def test_compose_empty(self):
        c = HookComposer()
        script = c.compose(HookType.PRE_COMMIT)
        assert "#!/bin/sh" in script
        assert "exit 0" in script

    def test_add_and_compose_single(self):
        c = HookComposer()
        c.add(_hook("lint", script="#!/bin/sh\nflake8 ."))
        script = c.compose(HookType.PRE_COMMIT)
        assert "flake8 ." in script
        assert "#!/bin/sh" in script

    def test_compose_strips_shebang(self):
        c = HookComposer()
        c.add(_hook("lint", script="#!/bin/sh\nflake8 ."))
        script = c.compose(HookType.PRE_COMMIT)
        # Should have exactly one shebang (the top-level one)
        assert script.count("#!/bin/sh") == 1

    def test_ordering(self):
        c = HookComposer()
        c.add(_hook("second", script="#!/bin/sh\necho second"), order=2)
        c.add(_hook("first", script="#!/bin/sh\necho first"), order=1)
        script = c.compose(HookType.PRE_COMMIT)
        assert script.index("echo first") < script.index("echo second")

    def test_composed_hooks_order(self):
        c = HookComposer()
        h1 = _hook("b", script="#!/bin/sh\necho b")
        h2 = _hook("a", script="#!/bin/sh\necho a")
        c.add(h1, order=2)
        c.add(h2, order=1)
        hooks = c.composed_hooks(HookType.PRE_COMMIT)
        assert [h.name for h in hooks] == ["a", "b"]

    def test_composed_hooks_empty_type(self):
        c = HookComposer()
        c.add(_hook("test"))
        assert c.composed_hooks(HookType.PRE_PUSH) == []

    def test_set_condition(self):
        c = HookComposer()
        c.add(_hook("lint", script="#!/bin/sh\nflake8 ."))
        c.set_condition("lint", '[ -f ".flake8" ]')
        script = c.compose(HookType.PRE_COMMIT)
        assert '[ -f ".flake8" ]' in script
        assert "if" in script

    def test_set_condition_missing_raises(self):
        c = HookComposer()
        with pytest.raises(KeyError, match="not-here"):
            c.set_condition("not-here", "true")

    def test_skip_pattern(self):
        c = HookComposer()
        c.add(_hook("lint", script="#!/bin/sh\nflake8 ."))
        c.skip_pattern("lint", "*.md")
        script = c.compose(HookType.PRE_COMMIT)
        assert "*.md" in script

    def test_skip_pattern_missing_raises(self):
        c = HookComposer()
        with pytest.raises(KeyError):
            c.skip_pattern("nope", "*.txt")

    def test_multiple_hooks_same_type(self):
        c = HookComposer()
        c.add(_hook("a", script="#!/bin/sh\necho a"), order=0)
        c.add(_hook("b", script="#!/bin/sh\necho b"), order=1)
        c.add(_hook("c", script="#!/bin/sh\necho c"), order=2)
        script = c.compose(HookType.PRE_COMMIT)
        assert "echo a" in script
        assert "echo b" in script
        assert "echo c" in script

    def test_different_types_separate(self):
        c = HookComposer()
        c.add(_hook("pre", hook_type=HookType.PRE_COMMIT, script="#!/bin/sh\necho pre"))
        c.add(_hook("post", hook_type=HookType.POST_COMMIT, script="#!/bin/sh\necho post"))
        pre_script = c.compose(HookType.PRE_COMMIT)
        post_script = c.compose(HookType.POST_COMMIT)
        assert "echo pre" in pre_script
        assert "echo post" not in pre_script
        assert "echo post" in post_script
