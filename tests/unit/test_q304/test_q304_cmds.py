"""Tests for Q304 CLI commands."""

import asyncio
from unittest.mock import MagicMock

import pytest


def _make_registry():
    registry = MagicMock()
    registered = {}

    def register_async(name, desc, handler):
        registered[name] = handler

    registry.register_async.side_effect = register_async
    registry._handlers = registered
    return registry


def _get(registry, name):
    return registry._handlers[name]


class TestRegisterQ304:
    def test_all_commands_registered(self):
        from lidco.cli.commands.q304_cmds import register_q304_commands
        r = _make_registry()
        register_q304_commands(r)
        assert "bump-version" in r._handlers
        assert "changelog" in r._handlers
        assert "release-notes" in r._handlers
        assert "tag" in r._handlers


class TestBumpVersionCommand:
    def _register(self):
        from lidco.cli.commands.q304_cmds import register_q304_commands
        r = _make_registry()
        register_q304_commands(r)
        return _get(r, "bump-version")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_bump_patch(self):
        handler = self._register()
        result = asyncio.run(handler("1.0.0 patch"))
        assert "1.0.1" in result

    def test_bump_minor(self):
        handler = self._register()
        result = asyncio.run(handler("1.0.0 minor"))
        assert "1.1.0" in result

    def test_bump_major(self):
        handler = self._register()
        result = asyncio.run(handler("1.0.0 major"))
        assert "2.0.0" in result

    def test_invalid_version(self):
        handler = self._register()
        result = asyncio.run(handler("bad patch"))
        assert "Error" in result

    def test_auto_detect(self):
        handler = self._register()
        result = asyncio.run(handler('auto 1.0.0 "feat: add widget"'))
        assert "1.1.0" in result

    def test_unknown_bump_type(self):
        handler = self._register()
        result = asyncio.run(handler("1.0.0 mega"))
        assert "Unknown" in result

    def test_missing_args(self):
        handler = self._register()
        result = asyncio.run(handler("1.0.0"))
        assert "Error" in result or "Usage" in result


class TestChangelogCommand:
    def _register(self):
        from lidco.cli.commands.q304_cmds import register_q304_commands
        r = _make_registry()
        register_q304_commands(r)
        return _get(r, "changelog")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_add_and_generate(self):
        handler = self._register()
        asyncio.run(handler('add added "new feature"'))
        result = asyncio.run(handler("generate 1.0.0"))
        assert "new feature" in result

    def test_clear(self):
        handler = self._register()
        asyncio.run(handler('add added "item"'))
        asyncio.run(handler("clear"))
        result = asyncio.run(handler("generate 1.0.0"))
        assert "No changes" in result

    def test_keep_a_changelog(self):
        handler = self._register()
        asyncio.run(handler('add fixed "bug"'))
        result = asyncio.run(handler("keep-a-changelog 1.0.0 --date 2026-04-04"))
        assert "[1.0.0]" in result

    def test_unknown_subcmd(self):
        handler = self._register()
        result = asyncio.run(handler("nope"))
        assert "Unknown" in result

    def test_add_missing_args(self):
        handler = self._register()
        result = asyncio.run(handler("add"))
        assert "Error" in result

    def test_generate_missing_version(self):
        handler = self._register()
        result = asyncio.run(handler("generate"))
        assert "Error" in result

    def test_add_with_pr_url(self):
        handler = self._register()
        result = asyncio.run(handler('add fixed "fix" --pr https://example.com'))
        assert "Added" in result


class TestReleaseNotesCommand:
    def _register(self):
        from lidco.cli.commands.q304_cmds import register_q304_commands
        r = _make_registry()
        register_q304_commands(r)
        return r

    def test_no_args_shows_usage(self):
        r = self._register()
        handler = _get(r, "release-notes")
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_generate_notes(self):
        r = self._register()
        changelog = _get(r, "changelog")
        asyncio.run(changelog('add added "cool feature"'))
        handler = _get(r, "release-notes")
        result = asyncio.run(handler("2.0.0"))
        assert "Release 2.0.0" in result


class TestTagCommand:
    def _register(self):
        from lidco.cli.commands.q304_cmds import register_q304_commands
        r = _make_registry()
        register_q304_commands(r)
        return _get(r, "tag")

    def test_no_args_shows_usage(self):
        handler = self._register()
        result = asyncio.run(handler(""))
        assert "Usage" in result

    def test_create_tag(self):
        handler = self._register()
        result = asyncio.run(handler("create v1.0.0"))
        assert "created" in result.lower()

    def test_create_duplicate(self):
        handler = self._register()
        asyncio.run(handler("create v1.0.0"))
        result = asyncio.run(handler("create v1.0.0"))
        assert "Error" in result

    def test_list_tags(self):
        handler = self._register()
        asyncio.run(handler("create v1.0.0"))
        result = asyncio.run(handler("list"))
        assert "v1.0.0" in result

    def test_delete_tag(self):
        handler = self._register()
        asyncio.run(handler("create v1.0.0"))
        result = asyncio.run(handler("delete v1.0.0"))
        assert "deleted" in result.lower()

    def test_latest(self):
        handler = self._register()
        asyncio.run(handler("create v1.0.0"))
        result = asyncio.run(handler("latest"))
        assert "v1.0.0" in result

    def test_find_pattern(self):
        handler = self._register()
        asyncio.run(handler("create v1.0.0"))
        asyncio.run(handler("create v1.1.0"))
        result = asyncio.run(handler("find v1.*"))
        assert "v1.0.0" in result

    def test_annotated_tag(self):
        handler = self._register()
        result = asyncio.run(handler('annotated v2.0.0 "major release"'))
        assert "Annotated" in result or "created" in result.lower()

    def test_unknown_subcmd(self):
        handler = self._register()
        result = asyncio.run(handler("nope"))
        assert "Unknown" in result
