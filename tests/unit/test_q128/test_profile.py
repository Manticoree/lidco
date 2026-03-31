"""Tests for lidco.config.profile."""
import json
import pytest
from lidco.config.profile import ConfigProfile, ProfileManager


def make_manager():
    written = {}

    def write_fn(path, data):
        written[path] = data

    def read_fn(path):
        if path not in written:
            raise FileNotFoundError(path)
        return written[path]

    mgr = ProfileManager(
        store_path="/tmp/test_profiles.json",
        write_fn=write_fn,
        read_fn=read_fn,
    )
    return mgr, written


class TestConfigProfile:
    def test_dataclass_defaults(self):
        p = ConfigProfile(name="dev", settings={})
        assert p.description == ""
        assert p.is_active is False
        assert p.created_at == ""

    def test_dataclass_fields(self):
        p = ConfigProfile(name="prod", settings={"k": "v"}, description="Production")
        assert p.name == "prod"
        assert p.settings == {"k": "v"}
        assert p.description == "Production"


class TestProfileManager:
    def test_create_returns_profile(self):
        mgr, _ = make_manager()
        p = mgr.create("dev", {"debug": True})
        assert isinstance(p, ConfigProfile)
        assert p.name == "dev"
        assert p.settings["debug"] is True

    def test_create_sets_timestamp(self):
        mgr, _ = make_manager()
        p = mgr.create("dev", {})
        assert p.created_at != ""

    def test_get_existing(self):
        mgr, _ = make_manager()
        mgr.create("dev", {"x": 1})
        p = mgr.get("dev")
        assert p is not None
        assert p.name == "dev"

    def test_get_missing_returns_none(self):
        mgr, _ = make_manager()
        assert mgr.get("nope") is None

    def test_list_all_empty(self):
        mgr, _ = make_manager()
        assert mgr.list_all() == []

    def test_list_all_returns_all(self):
        mgr, _ = make_manager()
        mgr.create("a", {})
        mgr.create("b", {})
        assert len(mgr.list_all()) == 2

    def test_delete_existing(self):
        mgr, _ = make_manager()
        mgr.create("dev", {})
        result = mgr.delete("dev")
        assert result is True
        assert mgr.get("dev") is None

    def test_delete_missing(self):
        mgr, _ = make_manager()
        assert mgr.delete("nope") is False

    def test_activate_sets_active(self):
        mgr, _ = make_manager()
        mgr.create("dev", {})
        p = mgr.activate("dev")
        assert p.is_active is True

    def test_activate_deactivates_others(self):
        mgr, _ = make_manager()
        mgr.create("dev", {})
        mgr.create("prod", {})
        mgr.activate("dev")
        mgr.activate("prod")
        assert mgr.get("dev").is_active is False
        assert mgr.get("prod").is_active is True

    def test_activate_missing_raises(self):
        mgr, _ = make_manager()
        with pytest.raises(KeyError):
            mgr.activate("nope")

    def test_active_returns_none_when_none(self):
        mgr, _ = make_manager()
        mgr.create("dev", {})
        assert mgr.active() is None

    def test_active_returns_active(self):
        mgr, _ = make_manager()
        mgr.create("dev", {})
        mgr.activate("dev")
        p = mgr.active()
        assert p is not None
        assert p.name == "dev"

    def test_update_merges_settings(self):
        mgr, _ = make_manager()
        mgr.create("dev", {"a": 1, "b": 2})
        p = mgr.update("dev", {"b": 99, "c": 3})
        assert p.settings == {"a": 1, "b": 99, "c": 3}

    def test_update_missing_raises(self):
        mgr, _ = make_manager()
        with pytest.raises(KeyError):
            mgr.update("nope", {})

    def test_export_returns_json(self):
        mgr, _ = make_manager()
        mgr.create("dev", {"x": 1})
        raw = mgr.export()
        data = json.loads(raw)
        assert isinstance(data, list)
        assert data[0]["name"] == "dev"

    def test_import_profiles_count(self):
        mgr, _ = make_manager()
        raw = json.dumps([
            {"name": "a", "settings": {}, "description": "", "is_active": False, "created_at": ""},
            {"name": "b", "settings": {}, "description": "", "is_active": False, "created_at": ""},
        ])
        count = mgr.import_profiles(raw)
        assert count == 2
        assert mgr.get("a") is not None
        assert mgr.get("b") is not None

    def test_persistence_via_write_fn(self):
        written = {}
        write_fn = lambda path, data: written.__setitem__(path, data)
        read_fn = lambda path: written[path] if path in written else (_ for _ in ()).throw(FileNotFoundError())
        mgr = ProfileManager("/tmp/p.json", write_fn=write_fn, read_fn=read_fn)
        mgr.create("dev", {"x": 1})
        assert "/tmp/p.json" in written

    def test_create_immutable_settings(self):
        mgr, _ = make_manager()
        s = {"a": 1}
        p = mgr.create("dev", s)
        s["a"] = 999
        assert p.settings["a"] == 1

    def test_description_stored(self):
        mgr, _ = make_manager()
        p = mgr.create("dev", {}, description="Development environment")
        assert p.description == "Development environment"

    def test_multiple_activations(self):
        mgr, _ = make_manager()
        for name in ["a", "b", "c"]:
            mgr.create(name, {})
        mgr.activate("a")
        mgr.activate("c")
        active = [p for p in mgr.list_all() if p.is_active]
        assert len(active) == 1
        assert active[0].name == "c"

    def test_round_trip_export_import(self):
        mgr, _ = make_manager()
        mgr.create("x", {"key": "val"}, description="desc")
        exported = mgr.export()
        mgr2, _ = make_manager()
        mgr2.import_profiles(exported)
        p = mgr2.get("x")
        assert p is not None
        assert p.settings["key"] == "val"
        assert p.description == "desc"
