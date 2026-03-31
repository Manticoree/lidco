"""Tests for Task 906 — Unified config storage path constants."""

from lidco.core.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    GLOBAL_CONFIG,
    MEMORY_DB,
    CHECKPOINTS_FILE,
    APPROVAL_QUEUE_FILE,
    SESSION_HISTORY_FILE,
    EVENT_STORE_FILE,
    KV_STORE_FILE,
    SNAPSHOTS_DIR,
)


class TestConfigPathConstants:
    """All canonical path constants are defined and correct."""

    def test_config_dir(self):
        assert CONFIG_DIR == ".lidco"

    def test_config_file(self):
        assert CONFIG_FILE == ".lidco/config.yaml"

    def test_global_config(self):
        assert GLOBAL_CONFIG == "~/.lidco/config.yaml"

    def test_memory_db(self):
        assert MEMORY_DB == ".lidco/agent_memory.db"

    def test_checkpoints_file(self):
        assert CHECKPOINTS_FILE == ".lidco/checkpoints.json"

    def test_approval_queue_file(self):
        assert APPROVAL_QUEUE_FILE == ".lidco/approval_queue.json"

    def test_session_history_file(self):
        assert SESSION_HISTORY_FILE == ".lidco/session_history.json"

    def test_event_store_file(self):
        assert EVENT_STORE_FILE == ".lidco/event_store.json"

    def test_kv_store_file(self):
        assert KV_STORE_FILE == ".lidco/kv_store.json"

    def test_snapshots_dir(self):
        assert SNAPSHOTS_DIR == ".lidco/workspace_snapshots"

    def test_all_project_paths_start_with_lidco_dir(self):
        """All project-local paths use the canonical .lidco/ prefix."""
        project_paths = [
            CONFIG_FILE, MEMORY_DB, CHECKPOINTS_FILE,
            APPROVAL_QUEUE_FILE, SESSION_HISTORY_FILE,
            EVENT_STORE_FILE, KV_STORE_FILE, SNAPSHOTS_DIR,
        ]
        for p in project_paths:
            assert p.startswith(".lidco/"), f"{p} does not start with .lidco/"
