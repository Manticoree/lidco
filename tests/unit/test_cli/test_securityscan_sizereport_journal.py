"""Tests for /security-scan (#229), /size-report (#230), /journal (#231)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


# ── Task 229: /security-scan ─────────────────────────────────────────────────

class TestSecurityScanCommand:
    def test_registered(self):
        assert _make_registry().get("security-scan") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("security-scan").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_shows_error(self):
        result = _run(_make_registry().get("security-scan").handler(arg="/nonexistent/path"))
        assert "не найден" in result or "not found" in result.lower()

    def test_clean_file_shows_ok(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "✅" in result or "не обнаружено" in result.lower()

    def test_detects_hardcoded_password(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text('password = "supersecret123"\n')
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "password" in result.lower() or "секрет" in result.lower() or "HIGH" in result

    def test_detects_eval(self, tmp_path):
        f = tmp_path / "eval_use.py"
        f.write_text("result = eval(user_input)\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "eval" in result

    def test_detects_subprocess_shell_true(self, tmp_path):
        f = tmp_path / "shell.py"
        f.write_text("import subprocess\nsubprocess.run(cmd, shell=True)\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "shell" in result.lower() or "subprocess" in result.lower()

    def test_detects_pickle(self, tmp_path):
        f = tmp_path / "pickle_use.py"
        f.write_text("import pickle\ndata = pickle.loads(raw)\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "pickle" in result

    def test_detects_verify_false(self, tmp_path):
        f = tmp_path / "ssl_bad.py"
        f.write_text("requests.get(url, verify=False)\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "verify" in result.lower() or "SSL" in result or "ssl" in result.lower()

    def test_detects_md5(self, tmp_path):
        f = tmp_path / "weak_hash.py"
        f.write_text("import hashlib\nh = hashlib.md5(data)\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "md5" in result.lower() or "слабый" in result.lower() or "LOW" in result

    def test_shows_severity_levels(self, tmp_path):
        f = tmp_path / "mixed.py"
        f.write_text(
            'password = "hardcoded"\n'
            "result = eval(x)\n"
            "h = hashlib.md5(d)\n"
        )
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "HIGH" in result or "LOW" in result or "MEDIUM" in result

    def test_shows_file_and_line(self, tmp_path):
        f = tmp_path / "located.py"
        f.write_text("x = 1\nresult = eval(user_code)\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "located.py" in result and "2" in result

    def test_scans_directory(self, tmp_path):
        (tmp_path / "a.py").write_text('secret = "abc123"\n')
        (tmp_path / "b.py").write_text("eval(x)\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(tmp_path)))
        assert "2" in result or "файлов" in result.lower() or "находок" in result.lower()

    def test_shows_total_count(self, tmp_path):
        f = tmp_path / "multi.py"
        f.write_text('password = "x"\nsecret = "y"\neval(z)\n')
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "находок" in result.lower() or "3" in result or "2" in result

    def test_non_python_file_rejected(self, tmp_path):
        f = tmp_path / "config.yaml"
        f.write_text("password: secret\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert ".py" in result or "python" in result.lower()

    def test_detects_pdb(self, tmp_path):
        f = tmp_path / "debug.py"
        f.write_text("import pdb\npdb.set_trace()\n")
        result = _run(_make_registry().get("security-scan").handler(arg=str(f)))
        assert "pdb" in result or "breakpoint" in result.lower() or "LOW" in result


# ── Task 230: /size-report ────────────────────────────────────────────────────

class TestSizeReportCommand:
    def test_registered(self):
        assert _make_registry().get("size-report") is not None

    def test_returns_string(self):
        result = _run(_make_registry().get("size-report").handler())
        assert isinstance(result, str) and len(result) > 0

    def test_nonexistent_shows_error(self):
        result = _run(_make_registry().get("size-report").handler(arg="/nonexistent/path"))
        assert "не найден" in result or "not found" in result.lower()

    def test_shows_file_count(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        result = _run(_make_registry().get("size-report").handler(arg=str(tmp_path)))
        assert "2" in result or "файл" in result.lower()

    def test_shows_line_count(self, tmp_path):
        (tmp_path / "lines.py").write_text("a\nb\nc\nd\ne\n")
        result = _run(_make_registry().get("size-report").handler(arg=str(tmp_path)))
        assert "5" in result or "строк" in result.lower()

    def test_shows_by_extension(self, tmp_path):
        (tmp_path / "code.py").write_text("x = 1\n")
        (tmp_path / "data.json").write_text("{}\n")
        result = _run(_make_registry().get("size-report").handler(arg=str(tmp_path)))
        assert ".py" in result or ".json" in result

    def test_shows_largest_files(self, tmp_path):
        big = tmp_path / "big.py"
        big.write_text("\n".join(f"x_{i} = {i}" for i in range(100)))
        small = tmp_path / "small.py"
        small.write_text("x = 1\n")
        result = _run(_make_registry().get("size-report").handler(arg=str(tmp_path)))
        assert "big.py" in result

    def test_shows_total_size(self, tmp_path):
        (tmp_path / "f.py").write_text("x" * 1000)
        result = _run(_make_registry().get("size-report").handler(arg=str(tmp_path)))
        assert "КБ" in result or "Б" in result or "МБ" in result

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "module.pyc").write_bytes(b"x" * 1000)
        (tmp_path / "real.py").write_text("x = 1\n")
        result = _run(_make_registry().get("size-report").handler(arg=str(tmp_path)))
        assert "module.pyc" not in result

    def test_shows_directory_breakdown(self, tmp_path):
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "module.py").write_text("x = 1\n" * 10)
        result = _run(_make_registry().get("size-report").handler(arg=str(tmp_path)))
        assert "src" in result or "директор" in result.lower()

    def test_empty_dir_shows_message(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = _run(_make_registry().get("size-report").handler(arg=str(empty)))
        assert "не найдено" in result or "not found" in result.lower() or "0" in result


# ── Task 231: /journal ────────────────────────────────────────────────────────

class TestJournalCommand:
    def test_registered(self):
        assert _make_registry().get("journal") is not None

    def test_empty_journal_shows_message(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("journal").handler())
        assert "нет" in result.lower() or "empty" in result.lower() or "добавьте" in result.lower()

    def test_add_entry(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("journal").handler(arg="fixed the auth bug"))
        assert "✓" in result or "добавлена" in result.lower()

    def test_entry_persists(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="important note"))
        result = _run(_make_registry().get("journal").handler(arg="today"))
        assert "important note" in result

    def test_today_shows_todays_entries(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="morning entry"))
        _run(_make_registry().get("journal").handler(arg="afternoon entry"))
        result = _run(_make_registry().get("journal").handler(arg="today"))
        assert "morning entry" in result
        assert "afternoon entry" in result

    def test_list_shows_entries(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="entry one"))
        result = _run(_make_registry().get("journal").handler(arg="list"))
        assert "entry one" in result

    def test_search_finds_entry(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="fixed the oauth redirect bug"))
        _run(_make_registry().get("journal").handler(arg="reviewed PR #42"))
        result = _run(_make_registry().get("journal").handler(arg="search oauth"))
        assert "oauth" in result.lower()

    def test_search_no_match(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="unrelated entry"))
        result = _run(_make_registry().get("journal").handler(arg="search xyzzy_no_match"))
        assert "ничего" in result or "not found" in result.lower()

    def test_tag_support(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("journal").handler(arg="#bug fixed login issue"))
        assert "bug" in result or "✓" in result

    def test_stats_shows_count(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="entry 1"))
        _run(_make_registry().get("journal").handler(arg="entry 2"))
        _run(_make_registry().get("journal").handler(arg="entry 3"))
        result = _run(_make_registry().get("journal").handler(arg="stats"))
        assert "3" in result

    def test_del_entry(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="to be deleted"))
        _run(_make_registry().get("journal").handler(arg="del 1"))
        result = _run(_make_registry().get("journal").handler(arg="today"))
        assert "to be deleted" not in result

    def test_clear_empties_journal(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="entry a"))
        _run(_make_registry().get("journal").handler(arg="entry b"))
        _run(_make_registry().get("journal").handler(arg="clear"))
        result = _run(_make_registry().get("journal").handler(arg="list"))
        assert "пуст" in result or "empty" in result.lower()

    def test_stores_in_lidco_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="check file"))
        journal_file = tmp_path / ".lidco" / "journal.json"
        assert journal_file.exists()
        data = json.loads(journal_file.read_text())
        assert len(data) == 1
        assert data[0]["text"] == "check file"

    def test_shows_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _run(_make_registry().get("journal").handler(arg="timed entry"))
        result = _run(_make_registry().get("journal").handler(arg="today"))
        import re
        assert re.search(r"\d{2}:\d{2}", result)  # HH:MM timestamp

    def test_add_prefix_works(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = _run(_make_registry().get("journal").handler(arg="add explicit add entry"))
        assert "✓" in result or "добавлена" in result.lower()
