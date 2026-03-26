"""Tests for T622 SecretsManager."""
import pytest

from lidco.security.secrets_manager import SecretsManager


class TestSecretsManager:
    def _make(self, tmp_path):
        return SecretsManager(store_path=tmp_path / "secrets.json", machine_key="test-key")

    def test_set_and_get(self, tmp_path):
        sm = self._make(tmp_path)
        sm.set("DB_PASSWORD", "super_secret")
        assert sm.get("DB_PASSWORD") == "super_secret"

    def test_get_missing_returns_none(self, tmp_path):
        sm = self._make(tmp_path)
        assert sm.get("nonexistent") is None

    def test_delete_existing_returns_true(self, tmp_path):
        sm = self._make(tmp_path)
        sm.set("MY_KEY", "value")
        assert sm.delete("MY_KEY") is True

    def test_delete_missing_returns_false(self, tmp_path):
        sm = self._make(tmp_path)
        assert sm.delete("nonexistent") is False

    def test_delete_removes_key(self, tmp_path):
        sm = self._make(tmp_path)
        sm.set("KEY", "val")
        sm.delete("KEY")
        assert sm.get("KEY") is None

    def test_list_returns_sorted_keys(self, tmp_path):
        sm = self._make(tmp_path)
        sm.set("ZEBRA", "z")
        sm.set("ALPHA", "a")
        sm.set("MIDDLE", "m")
        assert sm.list() == ["ALPHA", "MIDDLE", "ZEBRA"]

    def test_list_empty(self, tmp_path):
        sm = self._make(tmp_path)
        assert sm.list() == []

    def test_export_env(self, tmp_path):
        sm = self._make(tmp_path)
        sm.set("KEY1", "value1")
        sm.set("KEY2", "value2")
        env = sm.export_env()
        assert env == {"KEY1": "value1", "KEY2": "value2"}

    def test_persistence_across_instances(self, tmp_path):
        path = tmp_path / "secrets.json"
        sm1 = SecretsManager(store_path=path, machine_key="same-key")
        sm1.set("PERSISTENT", "hello")
        sm2 = SecretsManager(store_path=path, machine_key="same-key")
        assert sm2.get("PERSISTENT") == "hello"

    def test_set_empty_key_raises(self, tmp_path):
        sm = self._make(tmp_path)
        with pytest.raises(ValueError):
            sm.set("", "value")

    def test_set_whitespace_key_raises(self, tmp_path):
        sm = self._make(tmp_path)
        with pytest.raises(ValueError):
            sm.set("my key", "value")

    def test_overwrite_updates_value(self, tmp_path):
        sm = self._make(tmp_path)
        sm.set("KEY", "first")
        sm.set("KEY", "second")
        assert sm.get("KEY") == "second"

    def test_overwrite_preserves_created_at(self, tmp_path):
        import json
        path = tmp_path / "secrets.json"
        sm = SecretsManager(store_path=path, machine_key="test-key")
        sm.set("KEY", "first")
        data1 = json.loads(path.read_text())
        created_at = data1["KEY"]["created_at"]
        sm.set("KEY", "second")
        data2 = json.loads(path.read_text())
        assert data2["KEY"]["created_at"] == created_at

    def test_encrypted_value_differs_from_plaintext(self, tmp_path):
        import json
        path = tmp_path / "secrets.json"
        sm = SecretsManager(store_path=path, machine_key="test-key")
        sm.set("SECRET", "plaintext_value")
        data = json.loads(path.read_text())
        assert data["SECRET"]["encrypted_value"] != "plaintext_value"
