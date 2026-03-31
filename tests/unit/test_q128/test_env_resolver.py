"""Tests for lidco.config.env_resolver."""
import pytest
from lidco.config.env_resolver import EnvResolver


class TestEnvResolver:
    def test_resolve_brace_var(self):
        r = EnvResolver(env={"HOME": "/home/user"})
        assert r.resolve("${HOME}/docs") == "/home/user/docs"

    def test_resolve_bare_var(self):
        r = EnvResolver(env={"NAME": "alice"})
        assert r.resolve("Hello $NAME") == "Hello alice"

    def test_resolve_unknown_brace_empty(self):
        r = EnvResolver(env={})
        assert r.resolve("${UNKNOWN}") == ""

    def test_resolve_unknown_bare_unchanged(self):
        r = EnvResolver(env={})
        assert r.resolve("$BARE_UNKNOWN") == "$BARE_UNKNOWN"

    def test_resolve_strict_raises(self):
        r = EnvResolver(env={})
        with pytest.raises(KeyError):
            r.resolve("${MISSING}", strict=True)

    def test_resolve_non_string_passthrough(self):
        r = EnvResolver(env={})
        assert r.resolve(42) == 42

    def test_resolve_no_vars(self):
        r = EnvResolver(env={})
        assert r.resolve("plain text") == "plain text"

    def test_set_env(self):
        r = EnvResolver(env={})
        r.set_env("FOO", "bar")
        assert r.resolve("${FOO}") == "bar"

    def test_resolve_dict(self):
        r = EnvResolver(env={"A": "1", "B": "2"})
        result = r.resolve_dict({"x": "${A}", "y": "prefix_${B}"})
        assert result == {"x": "1", "y": "prefix_2"}

    def test_resolve_dict_nested(self):
        r = EnvResolver(env={"X": "val"})
        result = r.resolve_dict({"outer": {"inner": "${X}"}})
        assert result["outer"]["inner"] == "val"

    def test_resolve_list(self):
        r = EnvResolver(env={"A": "hello"})
        result = r.resolve_list(["${A}", "world"])
        assert result == ["hello", "world"]

    def test_resolve_list_nested_dict(self):
        r = EnvResolver(env={"K": "v"})
        result = r.resolve_list([{"key": "${K}"}])
        assert result[0]["key"] == "v"

    def test_resolve_multiple_vars_same_string(self):
        r = EnvResolver(env={"A": "foo", "B": "bar"})
        assert r.resolve("${A}_${B}") == "foo_bar"

    def test_resolve_dict_non_string_values(self):
        r = EnvResolver(env={})
        result = r.resolve_dict({"num": 42, "flag": True})
        assert result == {"num": 42, "flag": True}

    def test_default_uses_os_environ(self):
        import os
        r = EnvResolver()
        # PATH should always be in os.environ on any system
        assert r.resolve("${PATH}") == os.environ.get("PATH", "")

    def test_resolve_empty_string(self):
        r = EnvResolver(env={})
        assert r.resolve("") == ""

    def test_resolve_list_non_string(self):
        r = EnvResolver(env={})
        result = r.resolve_list([1, 2.5, None])
        assert result == [1, 2.5, None]

    def test_brace_takes_priority_over_bare(self):
        r = EnvResolver(env={"X": "brace"})
        result = r.resolve("${X}")
        assert result == "brace"

    def test_set_env_overrides(self):
        r = EnvResolver(env={"FOO": "original"})
        r.set_env("FOO", "new")
        assert r.resolve("${FOO}") == "new"

    def test_resolve_dict_list_value(self):
        r = EnvResolver(env={"A": "x"})
        result = r.resolve_dict({"items": ["${A}", "literal"]})
        assert result["items"] == ["x", "literal"]
