"""Tests for PrefsStore — persistent user preferences."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lidco.core.prefs import PrefsStore, _MAX_HINT_SHOWS


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def prefs_path(tmp_path: Path) -> Path:
    return tmp_path / "prefs.json"


@pytest.fixture
def prefs(prefs_path: Path) -> PrefsStore:
    return PrefsStore(path=prefs_path)


# ── loading & persistence ─────────────────────────────────────────────────────

class TestLoad:
    def test_returns_empty_dict_when_file_missing(self, prefs_path: Path) -> None:
        p = PrefsStore(path=prefs_path)
        assert p.get("anything") is None

    def test_loads_existing_json(self, prefs_path: Path) -> None:
        prefs_path.write_text('{"key": "value"}', encoding="utf-8")
        p = PrefsStore(path=prefs_path)
        assert p.get("key") == "value"

    def test_returns_empty_on_corrupt_json(self, prefs_path: Path) -> None:
        prefs_path.write_text("not valid json", encoding="utf-8")
        p = PrefsStore(path=prefs_path)
        assert p.get("x") is None

    def test_returns_empty_when_path_is_dir(self, tmp_path: Path) -> None:
        # tmp_path itself is a directory — should not raise
        p = PrefsStore(path=tmp_path / "subdir" / "prefs.json")
        assert p.get("x") is None


class TestSave:
    def test_set_persists_to_disk(self, prefs: PrefsStore, prefs_path: Path) -> None:
        prefs.set("color", "blue")
        raw = json.loads(prefs_path.read_text(encoding="utf-8"))
        assert raw["color"] == "blue"

    def test_set_overwrites_existing_key(self, prefs: PrefsStore, prefs_path: Path) -> None:
        prefs.set("n", 1)
        prefs.set("n", 2)
        raw = json.loads(prefs_path.read_text(encoding="utf-8"))
        assert raw["n"] == 2

    def test_second_instance_sees_saved_value(self, prefs: PrefsStore, prefs_path: Path) -> None:
        prefs.set("greeting", "hello")
        p2 = PrefsStore(path=prefs_path)
        assert p2.get("greeting") == "hello"

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "prefs.json"
        p = PrefsStore(path=nested)
        p.set("x", 1)
        assert nested.exists()

    def test_save_silently_ignores_os_error(self, prefs_path: Path) -> None:
        # Make the parent read-only to provoke OSError — best-effort, no crash
        prefs_path.parent.chmod(0o444)
        try:
            p = PrefsStore(path=prefs_path)
            p.set("k", "v")  # should not raise
        finally:
            prefs_path.parent.chmod(0o755)


class TestGet:
    def test_get_returns_default_when_missing(self, prefs: PrefsStore) -> None:
        assert prefs.get("missing") is None

    def test_get_returns_custom_default(self, prefs: PrefsStore) -> None:
        assert prefs.get("missing", 42) == 42

    def test_get_returns_stored_value(self, prefs: PrefsStore) -> None:
        prefs.set("flag", True)
        assert prefs.get("flag") is True


# ── newline hint ──────────────────────────────────────────────────────────────

class TestNewlineHint:
    def test_shows_when_fresh(self, prefs: PrefsStore) -> None:
        assert prefs.should_show_newline_hint() is True

    def test_shows_after_one_record(self, prefs: PrefsStore) -> None:
        prefs.record_newline_hint_shown()
        assert prefs.should_show_newline_hint() is True

    def test_shows_after_max_minus_one_records(self, prefs: PrefsStore) -> None:
        for _ in range(_MAX_HINT_SHOWS - 1):
            prefs.record_newline_hint_shown()
        assert prefs.should_show_newline_hint() is True

    def test_hidden_after_max_records(self, prefs: PrefsStore) -> None:
        for _ in range(_MAX_HINT_SHOWS):
            prefs.record_newline_hint_shown()
        assert prefs.should_show_newline_hint() is False

    def test_hidden_after_more_than_max_records(self, prefs: PrefsStore) -> None:
        for _ in range(_MAX_HINT_SHOWS + 5):
            prefs.record_newline_hint_shown()
        assert prefs.should_show_newline_hint() is False

    def test_record_increments_counter(self, prefs: PrefsStore, prefs_path: Path) -> None:
        prefs.record_newline_hint_shown()
        prefs.record_newline_hint_shown()
        raw = json.loads(prefs_path.read_text(encoding="utf-8"))
        assert raw["newline_hint_shown"] == 2

    def test_counter_persists_across_instances(self, prefs: PrefsStore, prefs_path: Path) -> None:
        for _ in range(_MAX_HINT_SHOWS):
            prefs.record_newline_hint_shown()
        p2 = PrefsStore(path=prefs_path)
        assert p2.should_show_newline_hint() is False

    def test_hint_shown_exactly_max_times(self, prefs: PrefsStore) -> None:
        show_count = 0
        for _ in range(_MAX_HINT_SHOWS + 3):
            if prefs.should_show_newline_hint():
                show_count += 1
                prefs.record_newline_hint_shown()
        assert show_count == _MAX_HINT_SHOWS
