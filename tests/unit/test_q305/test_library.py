"""Tests for HookLibrary."""

import pytest

from lidco.githooks.library import HookDefinition, HookLibrary
from lidco.githooks.manager import HookType


class TestHookDefinition:
    def test_frozen(self):
        hd = HookDefinition(name="test", type=HookType.PRE_COMMIT, script="#!/bin/sh\nexit 0")
        with pytest.raises(AttributeError):
            hd.name = "other"  # type: ignore[misc]

    def test_defaults(self):
        hd = HookDefinition(name="test", type=HookType.PRE_COMMIT, script="exit 0")
        assert hd.description == ""
        assert hd.category == "general"
        assert hd.language == ""


class TestHookLibrary:
    def test_builtin_hooks_not_empty(self):
        lib = HookLibrary()
        hooks = lib.builtin_hooks()
        assert len(hooks) >= 8

    def test_get_existing(self):
        lib = HookLibrary()
        h = lib.get("no-debug")
        assert h is not None
        assert h.name == "no-debug"
        assert h.type == HookType.PRE_COMMIT

    def test_get_missing_returns_none(self):
        lib = HookLibrary()
        assert lib.get("nonexistent-hook") is None

    def test_categories_sorted(self):
        lib = HookLibrary()
        cats = lib.categories()
        assert cats == sorted(cats)
        assert len(cats) >= 3

    def test_categories_unique(self):
        lib = HookLibrary()
        cats = lib.categories()
        assert len(cats) == len(set(cats))

    def test_hooks_for_language_python(self):
        lib = HookLibrary()
        py_hooks = lib.hooks_for_language("python")
        assert len(py_hooks) >= 2
        for h in py_hooks:
            assert h.language.lower() == "python"

    def test_hooks_for_language_case_insensitive(self):
        lib = HookLibrary()
        assert lib.hooks_for_language("Python") == lib.hooks_for_language("python")

    def test_hooks_for_language_no_match(self):
        lib = HookLibrary()
        assert lib.hooks_for_language("cobol") == []

    def test_extra_hooks(self):
        custom = HookDefinition(
            name="custom-hook",
            type=HookType.PRE_PUSH,
            script="#!/bin/sh\nexit 0",
            description="A custom hook",
            category="custom",
            language="ruby",
        )
        lib = HookLibrary(extra=[custom])
        assert lib.get("custom-hook") is not None
        assert lib.get("custom-hook") == custom

    def test_extra_overrides_builtin(self):
        override = HookDefinition(
            name="no-debug",
            type=HookType.PRE_COMMIT,
            script="#!/bin/sh\nexit 42",
            description="Overridden",
        )
        lib = HookLibrary(extra=[override])
        h = lib.get("no-debug")
        assert h is not None
        assert "exit 42" in h.script

    def test_hooks_for_language_javascript(self):
        lib = HookLibrary()
        js_hooks = lib.hooks_for_language("javascript")
        assert len(js_hooks) >= 2
        names = {h.name for h in js_hooks}
        assert "no-console-log" in names
