"""Tests for TagManager (Q304)."""

import pytest

from lidco.release.tags import Tag, TagManager


class TestTagManagerCreate:
    def _make(self):
        return TagManager()

    def test_create_tag(self):
        mgr = self._make()
        tag = mgr.create_tag("v1.0.0")
        assert tag.name == "v1.0.0"
        assert tag.annotated is False

    def test_create_tag_with_message(self):
        mgr = self._make()
        tag = mgr.create_tag("v1.0.0", "release 1.0")
        assert tag.message == "release 1.0"

    def test_create_duplicate_raises(self):
        mgr = self._make()
        mgr.create_tag("v1.0.0")
        with pytest.raises(ValueError, match="already exists"):
            mgr.create_tag("v1.0.0")

    def test_create_annotated(self):
        mgr = self._make()
        tag = mgr.annotated("v2.0.0", "major release")
        assert tag.annotated is True
        assert tag.message == "major release"

    def test_annotated_empty_message_raises(self):
        mgr = self._make()
        with pytest.raises(ValueError, match="non-empty"):
            mgr.annotated("v1.0.0", "")

    def test_annotated_duplicate_raises(self):
        mgr = self._make()
        mgr.annotated("v1.0.0", "msg")
        with pytest.raises(ValueError, match="already exists"):
            mgr.annotated("v1.0.0", "msg2")

    def test_create_multiple(self):
        mgr = self._make()
        mgr.create_tag("v1.0.0")
        mgr.create_tag("v1.1.0")
        assert len(mgr.tags) == 2

    def test_tags_returns_copy(self):
        mgr = self._make()
        mgr.create_tag("v1.0.0")
        tags = mgr.tags
        tags.clear()
        assert len(mgr.tags) == 1


class TestTagManagerList:
    def _make(self):
        return TagManager()

    def test_list_empty(self):
        assert self._make().list_tags() == []

    def test_list_returns_all(self):
        mgr = self._make()
        mgr.create_tag("a")
        mgr.create_tag("b")
        assert len(mgr.list_tags()) == 2


class TestTagManagerDelete:
    def _make(self):
        return TagManager()

    def test_delete_existing(self):
        mgr = self._make()
        mgr.create_tag("v1.0.0")
        assert mgr.delete_tag("v1.0.0") is True
        assert len(mgr.tags) == 0

    def test_delete_nonexistent(self):
        mgr = self._make()
        assert mgr.delete_tag("nope") is False


class TestTagManagerLatest:
    def _make(self):
        return TagManager()

    def test_latest_none(self):
        assert self._make().latest() is None

    def test_latest_returns_most_recent(self):
        mgr = self._make()
        mgr.create_tag("v1.0.0")
        mgr.create_tag("v2.0.0")
        latest = mgr.latest()
        assert latest is not None
        assert latest.name == "v2.0.0"


class TestTagManagerPattern:
    def _make(self):
        return TagManager()

    def test_tags_for_version_exact(self):
        mgr = self._make()
        mgr.create_tag("v1.0.0")
        mgr.create_tag("v2.0.0")
        matches = mgr.tags_for_version("v1.0.0")
        assert len(matches) == 1
        assert matches[0].name == "v1.0.0"

    def test_tags_for_version_wildcard(self):
        mgr = self._make()
        mgr.create_tag("v1.0.0")
        mgr.create_tag("v1.1.0")
        mgr.create_tag("v2.0.0")
        matches = mgr.tags_for_version("v1.*")
        assert len(matches) == 2

    def test_tags_for_version_no_match(self):
        mgr = self._make()
        mgr.create_tag("v1.0.0")
        assert mgr.tags_for_version("v9.*") == []

    def test_tags_for_version_star_all(self):
        mgr = self._make()
        mgr.create_tag("a")
        mgr.create_tag("b")
        assert len(mgr.tags_for_version("*")) == 2
