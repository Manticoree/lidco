"""Tests for src/lidco/cli/commands/q110_cmds.py."""
import asyncio


def _run(coro):
    return asyncio.run(coro)


class FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


def _load():
    import lidco.cli.commands.q110_cmds as mod
    mod._state.clear()
    reg = FakeRegistry()
    mod.register(reg)
    return reg


# ------------------------------------------------------------------ #
# /semver                                                               #
# ------------------------------------------------------------------ #

class TestSemverCommand:
    def test_registered(self):
        assert "semver" in _load().commands

    def test_no_args(self):
        result = _run(_load().commands["semver"].handler(""))
        assert "Usage" in result

    def test_demo(self):
        result = _run(_load().commands["semver"].handler("demo"))
        assert "1.2.3" in result or "SemVer" in result

    def test_parse_valid(self):
        result = _run(_load().commands["semver"].handler("parse 1.2.3"))
        assert "1" in result and "2" in result and "3" in result

    def test_parse_invalid(self):
        result = _run(_load().commands["semver"].handler("parse not_a_version"))
        assert "Error" in result

    def test_parse_no_args(self):
        result = _run(_load().commands["semver"].handler("parse"))
        assert "Usage" in result

    def test_bump_patch(self):
        result = _run(_load().commands["semver"].handler("bump 1.2.3 patch"))
        assert "1.2.4" in result

    def test_bump_minor(self):
        result = _run(_load().commands["semver"].handler("bump 1.2.3 minor"))
        assert "1.3.0" in result

    def test_bump_major(self):
        result = _run(_load().commands["semver"].handler("bump 1.2.3 major"))
        assert "2.0.0" in result

    def test_bump_no_args(self):
        result = _run(_load().commands["semver"].handler("bump"))
        assert "Usage" in result

    def test_compare_less(self):
        result = _run(_load().commands["semver"].handler("compare 1.0.0 2.0.0"))
        assert "<" in result

    def test_compare_equal(self):
        result = _run(_load().commands["semver"].handler("compare 1.0.0 1.0.0"))
        assert "==" in result

    def test_compare_no_args(self):
        result = _run(_load().commands["semver"].handler("compare"))
        assert "Usage" in result

    def test_satisfies_true(self):
        result = _run(_load().commands["semver"].handler("satisfies 1.2.5 ^1.2.0"))
        assert "True" in result or "true" in result.lower()

    def test_satisfies_false(self):
        result = _run(_load().commands["semver"].handler("satisfies 2.0.0 ^1.2.0"))
        assert "False" in result or "false" in result.lower()

    def test_satisfies_no_args(self):
        result = _run(_load().commands["semver"].handler("satisfies"))
        assert "Usage" in result

    def test_sort(self):
        result = _run(_load().commands["semver"].handler("sort 2.0.0 1.0.0 1.5.0"))
        assert "1.0.0" in result

    def test_latest(self):
        result = _run(_load().commands["semver"].handler("latest 1.0.0 2.0.0 1.5.0"))
        assert "2.0.0" in result

    def test_next(self):
        result = _run(_load().commands["semver"].handler("next 1.2.3"))
        assert "major" in result or "minor" in result or "patch" in result


# ------------------------------------------------------------------ #
# /mock                                                                 #
# ------------------------------------------------------------------ #

class TestMockCommand:
    def test_registered(self):
        assert "mock" in _load().commands

    def test_no_args(self):
        result = _run(_load().commands["mock"].handler(""))
        assert "Usage" in result

    def test_demo(self):
        result = _run(_load().commands["mock"].handler("demo"))
        assert "MagicMock" in result or "mock" in result.lower()

    def test_generate(self):
        src = "class Svc:\n    def run(self) -> bool: ...\n"
        result = _run(_load().commands["mock"].handler(f"generate {src}"))
        assert "MagicMock" in result or "Svc" in result

    def test_generate_no_args(self):
        result = _run(_load().commands["mock"].handler("generate"))
        assert "Usage" in result

    def test_fixture(self):
        src = "class Repo:\n    def find(self, id: int) -> dict: ...\n"
        result = _run(_load().commands["mock"].handler(f"fixture Repo {src}"))
        assert "pytest" in result or "fixture" in result.lower() or "Repo" in result

    def test_fixture_not_found(self):
        result = _run(_load().commands["mock"].handler("fixture Ghost class X: pass"))
        assert "not found" in result.lower() or "Ghost" in result

    def test_parse(self):
        src = "class A:\n    def go(self): ...\n"
        result = _run(_load().commands["mock"].handler(f"parse {src}"))
        assert "A" in result or "go" in result

    def test_parse_no_args(self):
        result = _run(_load().commands["mock"].handler("parse"))
        assert "Usage" in result

    def test_patch(self):
        src = "class Svc:\n    def run(self): ...\n"
        result = _run(_load().commands["mock"].handler(f"patch Svc {src}"))
        assert "patch" in result.lower() or "test" in result.lower()


# ------------------------------------------------------------------ #
# /conflict                                                             #
# ------------------------------------------------------------------ #

_CONFLICT_TEXT = "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> feature\n"

class TestConflictCommand:
    def test_registered(self):
        assert "conflict" in _load().commands

    def test_no_args(self):
        result = _run(_load().commands["conflict"].handler(""))
        assert "Usage" in result

    def test_demo(self):
        result = _run(_load().commands["conflict"].handler("demo"))
        assert "conflict" in result.lower() or "Conflict" in result

    def test_parse(self):
        result = _run(_load().commands["conflict"].handler(f"parse {_CONFLICT_TEXT}"))
        assert "Conflict" in result or "HEAD" in result

    def test_parse_no_conflict(self):
        result = _run(_load().commands["conflict"].handler("parse no markers here"))
        assert "No conflicts" in result or "0" in result

    def test_count(self):
        result = _run(_load().commands["conflict"].handler(f"count {_CONFLICT_TEXT}"))
        assert "1" in result

    def test_check_true(self):
        content = "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> feature"
        result = _run(_load().commands["conflict"].handler(f"check {content}"))
        assert "True" in result or "true" in result.lower() or "Has" in result

    def test_check_false(self):
        result = _run(_load().commands["conflict"].handler("check clean content"))
        assert "False" in result or "false" in result.lower()

    def test_resolve(self):
        result = _run(_load().commands["conflict"].handler(f"resolve {_CONFLICT_TEXT}"))
        assert "<<<<<<<" not in result or "Resolved" in result

    def test_summary(self):
        result = _run(_load().commands["conflict"].handler(f"summary {_CONFLICT_TEXT}"))
        assert "Conflicts" in result or "total" in result.lower()


# ------------------------------------------------------------------ #
# /format                                                               #
# ------------------------------------------------------------------ #

class TestFormatCommand:
    def test_registered(self):
        assert "format" in _load().commands

    def test_no_args(self):
        result = _run(_load().commands["format"].handler(""))
        assert "Usage" in result

    def test_demo(self):
        result = _run(_load().commands["format"].handler("demo"))
        assert "formatter" in result.lower() or "black" in result

    def test_list(self):
        result = _run(_load().commands["format"].handler("list"))
        assert "black" in result or "ruff" in result or "Formatters" in result

    def test_available(self):
        result = _run(_load().commands["format"].handler("available"))
        assert isinstance(result, str)

    def test_available_named(self):
        result = _run(_load().commands["format"].handler("available black"))
        assert "black" in result

    def test_detect_empty_dir(self, tmp_path):
        result = _run(_load().commands["format"].handler(f"detect {tmp_path}"))
        assert "No formatters" in result or "Detected" in result

    def test_detect_with_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.black]\n")
        result = _run(_load().commands["format"].handler(f"detect {tmp_path}"))
        assert "black" in result

    def test_summary(self):
        result = _run(_load().commands["format"].handler("summary"))
        assert "Registered" in result or "black" in result

    def test_reset(self):
        result = _run(_load().commands["format"].handler("reset"))
        assert "reset" in result.lower()
