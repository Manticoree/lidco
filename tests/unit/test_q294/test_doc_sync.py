"""Tests for DocSync."""
import os
import tempfile

import pytest

from lidco.notion.client import NotionClient
from lidco.notion.doc_sync import DocSync, SyncResult


class TestDocSyncFile:
    def test_sync_file_creates_page(self):
        c = NotionClient()
        ds = DocSync(c)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Hello\nWorld")
            f.flush()
            path = f.name
        try:
            result = ds.sync_file(path)
            assert isinstance(result, SyncResult)
            assert result.status == "created"
            assert result.page_id is not None
        finally:
            os.unlink(path)

    def test_sync_file_unchanged(self):
        c = NotionClient()
        ds = DocSync(c)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("same content")
            f.flush()
            path = f.name
        try:
            ds.sync_file(path)
            result = ds.sync_file(path)
            assert result.status == "unchanged"
        finally:
            os.unlink(path)

    def test_sync_file_updated(self):
        c = NotionClient()
        ds = DocSync(c)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("v1")
            f.flush()
            path = f.name
        try:
            ds.sync_file(path)
            with open(path, "w") as fh:
                fh.write("v2")
            result = ds.sync_file(path)
            assert result.status == "updated"
        finally:
            os.unlink(path)

    def test_sync_file_not_found_raises(self):
        c = NotionClient()
        ds = DocSync(c)
        with pytest.raises(FileNotFoundError):
            ds.sync_file("/nonexistent/file.md")

    def test_sync_file_recreates_deleted_remote(self):
        c = NotionClient()
        ds = DocSync(c)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("content")
            f.flush()
            path = f.name
        try:
            result1 = ds.sync_file(path)
            c.delete_page(result1.page_id)
            with open(path, "w") as fh:
                fh.write("new content")
            result2 = ds.sync_file(path)
            assert result2.status == "updated"
            assert result2.page_id is not None
        finally:
            os.unlink(path)


class TestDocSyncAll:
    def test_sync_all_syncs_md_files(self):
        c = NotionClient()
        ds = DocSync(c)
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["a.md", "b.md", "c.txt"]:
                with open(os.path.join(tmpdir, name), "w") as fh:
                    fh.write(f"content of {name}")
            results = ds.sync_all(tmpdir)
            assert len(results) == 2  # only .md
            assert all(r.status == "created" for r in results)

    def test_sync_all_not_a_dir_raises(self):
        c = NotionClient()
        ds = DocSync(c)
        with pytest.raises(NotADirectoryError):
            ds.sync_all("/nonexistent/dir")

    def test_sync_all_empty_dir(self):
        c = NotionClient()
        ds = DocSync(c)
        with tempfile.TemporaryDirectory() as tmpdir:
            results = ds.sync_all(tmpdir)
            assert results == []


class TestDocSyncConflict:
    def test_conflict_local_wins_no_remote_only(self):
        result = DocSync.conflict_resolution("line1\nline2", "line1\nline2")
        assert result == "line1\nline2"

    def test_conflict_appends_remote_additions(self):
        result = DocSync.conflict_resolution("local line", "remote only")
        assert "## Remote additions" in result
        assert "remote only" in result

    def test_conflict_local_content_preserved(self):
        result = DocSync.conflict_resolution("my stuff", "extra")
        assert result.startswith("my stuff")


class TestDocSyncLastSync:
    def test_last_sync_never_synced(self):
        c = NotionClient()
        ds = DocSync(c)
        assert ds.last_sync("/never.md") == 0.0

    def test_last_sync_after_sync(self):
        c = NotionClient()
        ds = DocSync(c)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("data")
            f.flush()
            path = f.name
        try:
            ds.sync_file(path)
            assert ds.last_sync(path) > 0.0
        finally:
            os.unlink(path)
