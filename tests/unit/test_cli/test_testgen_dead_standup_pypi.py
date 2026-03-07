"""Tests for /test-gen (#218), /dead (#219), /standup (#220), /pypi (#221)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


def _make_session_registry(**kwargs) -> CommandRegistry:
    reg = _make_registry()
    sess = MagicMock()
    cfg = MagicMock()
    cfg.llm.default_model = kwargs.get("model", "claude-sonnet-4-6")
    sess.config = cfg
    sess.project_dir = kwargs.get("project_dir", Path("."))
    reg.set_session(sess)
    return reg


# ── Task 218: /test-gen ───────────────────────────────────────────────────────

class TestTestGenCommand:
    def test_registered(self):
        assert _make_registry().get("test-gen") is not None

    def test_no_session_shows_error(self):
        result = _run(_make_registry().get("test-gen").handler(arg="file.py"))
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_no_arg_shows_usage(self):
        reg = _make_session_registry()
        result = _run(reg.get("test-gen").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_file_shows_error(self):
        reg = _make_session_registry()
        result = _run(reg.get("test-gen").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_non_python_file_rejected(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("{}")
        reg = _make_session_registry()
        result = _run(reg.get("test-gen").handler(arg=str(f)))
        assert ".py" in result or "python" in result.lower() or "поддерживаются" in result.lower()

    def test_generates_tests(self, tmp_path):
        f = tmp_path / "utils.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(
            return_value=MagicMock(content="def test_add():\n    assert add(1, 2) == 3\n")
        )
        result = _run(reg.get("test-gen").handler(arg=str(f)))
        assert "test_add" in result or "utils.py" in result

    def test_shows_file_name_in_header(self, tmp_path):
        f = tmp_path / "auth.py"
        f.write_text("def login(user): pass\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(return_value=MagicMock(content="# tests"))
        result = _run(reg.get("test-gen").handler(arg=str(f)))
        assert "auth.py" in result

    def test_suggests_test_file_path(self, tmp_path):
        f = tmp_path / "parser.py"
        f.write_text("def parse(s): pass\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(return_value=MagicMock(content="# tests"))
        result = _run(reg.get("test-gen").handler(arg=str(f)))
        assert "test_parser.py" in result

    def test_framework_pytest_default(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def foo(): pass\n")
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="# tests")
        reg._session.llm.complete = cap
        _run(reg.get("test-gen").handler(arg=str(f)))
        assert any("pytest" in str(m) for m in captured)

    def test_framework_unittest_flag(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def bar(): pass\n")
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="# tests")
        reg._session.llm.complete = cap
        _run(reg.get("test-gen").handler(arg=f"{f} --framework unittest"))
        assert any("unittest" in str(m) for m in captured)

    def test_passes_code_to_llm(self, tmp_path):
        f = tmp_path / "secret.py"
        f.write_text("def secret_fn(x): return x * 2\n")
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="# tests")
        reg._session.llm.complete = cap
        _run(reg.get("test-gen").handler(arg=str(f)))
        assert any("secret_fn" in str(m) for m in captured)

    def test_llm_error_handled(self, tmp_path):
        f = tmp_path / "err.py"
        f.write_text("x = 1\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(side_effect=Exception("LLM down"))
        result = _run(reg.get("test-gen").handler(arg=str(f)))
        assert "ошибка" in result.lower() or "error" in result.lower()

    def test_large_file_truncated(self, tmp_path):
        f = tmp_path / "big.py"
        f.write_text("def fn(): pass\n" * 1000)
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="# tests")
        reg._session.llm.complete = cap
        _run(reg.get("test-gen").handler(arg=str(f)))
        assert len(str(captured)) < 50_000


# ── Task 219: /dead ───────────────────────────────────────────────────────────

class TestDeadCommand:
    def test_registered(self):
        assert _make_registry().get("dead") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("dead").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_file_shows_error(self):
        result = _run(_make_registry().get("dead").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_detects_unused_import(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("import os\nimport sys\n\ndef foo():\n    return sys.argv\n")
        result = _run(_make_registry().get("dead").handler(arg=str(f)))
        assert "os" in result  # os is unused, sys is used

    def test_no_unused_imports(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("import os\n\ndef foo():\n    return os.getcwd()\n")
        result = _run(_make_registry().get("dead").handler(arg=str(f)))
        assert "нет" in result.lower() or "✅" in result

    def test_detects_unused_function(self, tmp_path):
        f = tmp_path / "funcs.py"
        f.write_text(
            "def used(): return 1\n"
            "def unused_orphan(): return 2\n"
            "\nresult = used()\n"
        )
        result = _run(_make_registry().get("dead").handler(arg=str(f)))
        assert "unused_orphan" in result

    def test_imports_flag_only_imports(self, tmp_path):
        f = tmp_path / "both.py"
        f.write_text("import os\nimport sys\ndef unused(): pass\n\nsys.exit()\n")
        result = _run(_make_registry().get("dead").handler(arg=f"{f} --imports"))
        assert "os" in result
        # functions section should not appear
        assert "функци" not in result.lower() or "импорт" in result.lower()

    def test_functions_flag_only_functions(self, tmp_path):
        f = tmp_path / "fns.py"
        f.write_text("import os\ndef used(): pass\ndef orphan(): pass\nused()\n")
        result = _run(_make_registry().get("dead").handler(arg=f"{f} --functions"))
        assert "orphan" in result

    def test_shows_line_numbers(self, tmp_path):
        f = tmp_path / "lined.py"
        f.write_text("import os\nimport sys\n\ndef foo(): return sys.argv\n")
        result = _run(_make_registry().get("dead").handler(arg=f"{f} --imports"))
        import re
        assert re.search(r"\d+", result)  # line number present

    def test_syntax_error_shows_error(self, tmp_path):
        f = tmp_path / "broken.py"
        f.write_text("def (broken syntax:\n    pass\n")
        result = _run(_make_registry().get("dead").handler(arg=str(f)))
        assert "синтаксическ" in result.lower() or "syntax" in result.lower() or "ошибка" in result.lower()

    def test_shows_file_name_in_header(self, tmp_path):
        f = tmp_path / "mymodule.py"
        f.write_text("x = 1\n")
        result = _run(_make_registry().get("dead").handler(arg=str(f)))
        assert "mymodule.py" in result

    def test_alias_import_detected(self, tmp_path):
        f = tmp_path / "aliased.py"
        f.write_text("import numpy as np\nimport os\n\nprint(os.getcwd())\n")
        result = _run(_make_registry().get("dead").handler(arg=str(f)))
        assert "np" in result  # np (numpy alias) is unused


# ── Task 220: /standup ────────────────────────────────────────────────────────

class TestStandupCommand:
    def test_registered(self):
        assert _make_registry().get("standup") is not None

    def test_returns_string(self):
        result = _run(_make_registry().get("standup").handler())
        assert isinstance(result, str) and len(result) > 0

    def test_shows_date(self):
        result = _run(_make_registry().get("standup").handler())
        import re
        # Should have a date or "стендап"
        assert re.search(r"\d{4}|\d{2}", result) or "стендап" in result.lower()

    def test_shows_done_section(self):
        result = _run(_make_registry().get("standup").handler())
        assert "сделано" in result.lower() or "done" in result.lower() or "что" in result.lower()

    def test_shows_blockers_section(self):
        result = _run(_make_registry().get("standup").handler())
        assert "блокер" in result.lower() or "blocker" in result.lower()

    def test_shows_today_section(self):
        result = _run(_make_registry().get("standup").handler())
        assert "сегодня" in result.lower() or "today" in result.lower() or "план" in result.lower()

    def test_accepts_days_arg(self):
        result = _run(_make_registry().get("standup").handler(arg="3"))
        assert isinstance(result, str) and "3" in result

    def test_caps_days(self):
        # 100 days shouldn't crash
        result = _run(_make_registry().get("standup").handler(arg="100"))
        assert isinstance(result, str) and len(result) > 0


# ── Task 221: /pypi ───────────────────────────────────────────────────────────

class TestPypiCommand:
    def test_registered(self):
        assert _make_registry().get("pypi") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("pypi").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_known_installed_package(self):
        # pytest is definitely installed
        result = _run(_make_registry().get("pypi").handler(arg="pytest"))
        assert "pytest" in result.lower()

    def test_shows_version_for_installed(self):
        result = _run(_make_registry().get("pypi").handler(arg="pytest"))
        import re
        # Should contain a version number like 8.x.x
        assert re.search(r"\d+\.\d+", result) or "версия" in result.lower()

    def test_unknown_package_shows_message(self):
        result = _run(_make_registry().get("pypi").handler(arg="xyzzy_nonexistent_package_abc123"))
        assert "не установлен" in result or "not installed" in result.lower() or "pip install" in result

    def test_shows_package_name(self):
        result = _run(_make_registry().get("pypi").handler(arg="pip"))
        assert "pip" in result.lower()

    def test_versions_flag(self):
        result = _run(_make_registry().get("pypi").handler(arg="pip --versions"))
        assert isinstance(result, str) and len(result) > 0

    def test_shows_install_hint_for_missing(self):
        result = _run(_make_registry().get("pypi").handler(arg="totally_fake_package_xyz"))
        assert "pip install" in result or "установить" in result.lower()
