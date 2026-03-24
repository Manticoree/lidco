"""Tests for Task 456: Notepads / persistent scratchpads."""
import time
import pytest
from lidco.notepads.store import Notepad, NotepadStore


@pytest.fixture
def store(tmp_path):
    return NotepadStore(base_dir=tmp_path / "notepads")


class TestNotepadCreate:
    def test_create_returns_notepad(self, store):
        np = store.create("todo", "- fix tests")
        assert isinstance(np, Notepad)
        assert np.name == "todo"
        assert np.content == "- fix tests"

    def test_create_writes_file(self, store, tmp_path):
        store.create("spec", "hello")
        assert (tmp_path / "notepads" / "spec.md").exists()

    def test_create_empty_content(self, store):
        np = store.create("empty")
        assert np.content == ""

    def test_create_has_timestamps(self, store):
        before = time.time()
        np = store.create("ts")
        after = time.time()
        assert before <= np.created_at <= after


class TestNotepadRead:
    def test_read_existing(self, store):
        store.create("notes", "some notes")
        np = store.read("notes")
        assert np is not None
        assert np.content == "some notes"

    def test_read_nonexistent_returns_none(self, store):
        assert store.read("does_not_exist") is None

    def test_read_preserves_multiline(self, store):
        content = "line1\nline2\nline3"
        store.create("multi", content)
        np = store.read("multi")
        assert np.content == content


class TestNotepadUpdate:
    def test_update_changes_content(self, store):
        store.create("draft", "v1")
        np = store.update("draft", "v2")
        assert np.content == "v2"
        assert store.read("draft").content == "v2"

    def test_update_nonexistent_creates_file(self, store):
        np = store.update("new", "content")
        assert np.content == "content"
        assert store.exists("new")


class TestNotepadDelete:
    def test_delete_existing_returns_true(self, store):
        store.create("tmp")
        assert store.delete("tmp") is True
        assert store.read("tmp") is None

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete("ghost") is False


class TestNotepadList:
    def test_list_empty_returns_empty(self, store):
        assert store.list() == []

    def test_list_returns_all_notepads(self, store):
        store.create("a", "alpha")
        store.create("b", "beta")
        names = {np.name for np in store.list()}
        assert names == {"a", "b"}

    def test_list_after_delete(self, store):
        store.create("x")
        store.create("y")
        store.delete("x")
        assert len(store.list()) == 1


class TestNotepadNameSanitization:
    def test_special_chars_stripped(self, store):
        np = store.create("my notepad!", "hi")
        # Name sanitized but notepad created
        assert store.exists("my notepad!")  # safe name used internally

    def test_exists_check(self, store):
        store.create("present")
        assert store.exists("present") is True
        assert store.exists("absent") is False


class TestNotepadWordCount:
    def test_word_count(self):
        np = Notepad("n", "hello world foo", 0.0, 0.0)
        assert np.word_count() == 3

    def test_word_count_empty(self):
        np = Notepad("n", "", 0.0, 0.0)
        assert np.word_count() == 0
