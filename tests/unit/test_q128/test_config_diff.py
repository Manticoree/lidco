"""Tests for lidco.config.config_diff."""
from lidco.config.config_diff import ConfigDiff, DiffEntry


class TestDiffEntry:
    def test_fields(self):
        e = DiffEntry(key="x", old_value=1, new_value=2, kind="changed")
        assert e.key == "x"
        assert e.kind == "changed"


class TestConfigDiff:
    def setup_method(self):
        self.diff = ConfigDiff()

    def test_diff_added(self):
        entries = self.diff.diff({}, {"a": 1})
        assert len(entries) == 1
        assert entries[0].kind == "added"
        assert entries[0].key == "a"
        assert entries[0].new_value == 1

    def test_diff_removed(self):
        entries = self.diff.diff({"a": 1}, {})
        assert len(entries) == 1
        assert entries[0].kind == "removed"
        assert entries[0].old_value == 1

    def test_diff_changed(self):
        entries = self.diff.diff({"a": 1}, {"a": 2})
        assert len(entries) == 1
        assert entries[0].kind == "changed"
        assert entries[0].old_value == 1
        assert entries[0].new_value == 2

    def test_diff_no_change(self):
        entries = self.diff.diff({"a": 1}, {"a": 1})
        assert entries == []

    def test_diff_nested_dot_notation(self):
        old = {"db": {"host": "localhost", "port": 5432}}
        new = {"db": {"host": "remotehost", "port": 5432}}
        entries = self.diff.diff(old, new)
        assert len(entries) == 1
        assert entries[0].key == "db.host"
        assert entries[0].kind == "changed"

    def test_diff_nested_added_key(self):
        old = {"db": {"host": "localhost"}}
        new = {"db": {"host": "localhost", "port": 5432}}
        entries = self.diff.diff(old, new)
        assert len(entries) == 1
        assert entries[0].key == "db.port"
        assert entries[0].kind == "added"

    def test_apply_added(self):
        base = {}
        entries = [DiffEntry("a", None, 1, "added")]
        result = self.diff.apply(base, entries)
        assert result["a"] == 1

    def test_apply_removed(self):
        base = {"a": 1}
        entries = [DiffEntry("a", 1, None, "removed")]
        result = self.diff.apply(base, entries)
        assert "a" not in result

    def test_apply_changed(self):
        base = {"a": 1}
        entries = [DiffEntry("a", 1, 99, "changed")]
        result = self.diff.apply(base, entries)
        assert result["a"] == 99

    def test_apply_immutable(self):
        base = {"a": 1}
        entries = [DiffEntry("a", 1, 2, "changed")]
        result = self.diff.apply(base, entries)
        assert base["a"] == 1  # original unchanged

    def test_summary_all_kinds(self):
        entries = [
            DiffEntry("a", None, 1, "added"),
            DiffEntry("b", 2, None, "removed"),
            DiffEntry("c", 3, 4, "changed"),
        ]
        s = self.diff.summary(entries)
        assert "3 changes" in s
        assert "+1" in s
        assert "-1" in s
        assert "~1" in s

    def test_summary_empty(self):
        s = self.diff.summary([])
        assert "0 changes" in s

    def test_diff_multiple_changes(self):
        old = {"x": 1, "y": 2, "z": 3}
        new = {"x": 10, "y": 2, "w": 4}
        entries = self.diff.diff(old, new)
        kinds = {e.kind for e in entries}
        assert "changed" in kinds
        assert "removed" in kinds
        assert "added" in kinds

    def test_apply_nested_result(self):
        base = {"db": {"host": "localhost"}}
        entries = [DiffEntry("db.host", "localhost", "remote", "changed")]
        result = self.diff.apply(base, entries)
        assert result["db"]["host"] == "remote"

    def test_diff_sorted_keys(self):
        old = {"b": 1, "a": 2}
        new = {"b": 1, "a": 3}
        entries = self.diff.diff(old, new)
        assert entries[0].key == "a"

    def test_round_trip_diff_apply(self):
        old = {"x": 1, "y": 2}
        new = {"x": 10, "z": 3}
        entries = self.diff.diff(old, new)
        result = self.diff.apply(old, entries)
        assert result == new

    def test_diff_empty_dicts(self):
        entries = self.diff.diff({}, {})
        assert entries == []

    def test_apply_no_entries(self):
        base = {"a": 1}
        result = self.diff.apply(base, [])
        assert result == {"a": 1}

    def test_summary_only_added(self):
        entries = [DiffEntry("a", None, 1, "added")]
        s = self.diff.summary(entries)
        assert "+1" in s
        assert "-0" in s
