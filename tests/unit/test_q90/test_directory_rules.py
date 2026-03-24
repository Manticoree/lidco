"""Tests for DirectoryRulesResolver (T582)."""

import os
import time

import pytest
from pathlib import Path

from lidco.context.directory_rules import (
    DirectoryRule,
    DirectoryRulesResolver,
    RulesCache,
)


# ---------------------------------------------------------------------------
# RulesCache tests
# ---------------------------------------------------------------------------


class TestRulesCache:
    def test_get_returns_none_for_unknown_path(self, tmp_path):
        cache = RulesCache()
        assert cache.get(tmp_path / "nope") is None

    def test_set_and_get_round_trip(self, tmp_path):
        f = tmp_path / "rules"
        f.write_text("hello")
        cache = RulesCache()
        cache.set(f, "hello")
        assert cache.get(f) == "hello"

    def test_cache_invalidated_on_mtime_change(self, tmp_path):
        f = tmp_path / "rules"
        f.write_text("v1")
        cache = RulesCache()
        cache.set(f, "v1")
        assert cache.get(f) == "v1"

        # Force mtime change
        time.sleep(0.05)
        f.write_text("v2")
        # mtime changed -> cache miss
        assert cache.get(f) is None

    def test_get_returns_none_when_file_deleted(self, tmp_path):
        f = tmp_path / "rules"
        f.write_text("content")
        cache = RulesCache()
        cache.set(f, "content")
        f.unlink()
        assert cache.get(f) is None


# ---------------------------------------------------------------------------
# DirectoryRulesResolver.resolve
# ---------------------------------------------------------------------------


class TestResolve:
    def test_resolve_finds_parent_rules(self, tmp_path):
        rules_file = tmp_path / ".lidco-rules"
        rules_file.write_text("Be concise.")

        resolver = DirectoryRulesResolver(tmp_path)
        file_path = tmp_path / "src" / "foo.py"
        file_path.parent.mkdir(parents=True)

        rules = resolver.resolve(file_path)
        assert len(rules) == 1
        assert "Be concise." in rules[0].content

    def test_nearest_rules_highest_priority(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("root rule")
        src = tmp_path / "src"
        src.mkdir()
        (src / ".lidco-rules").write_text("src rule")

        resolver = DirectoryRulesResolver(tmp_path)
        rules = resolver.resolve(src / "foo.py")
        # root has lower priority (appears first), src has higher (appears last)
        assert len(rules) == 2
        assert rules[0].content == "root rule"
        assert rules[1].content == "src rule"
        assert rules[0].priority < rules[1].priority

    def test_deep_nesting_collects_all_levels(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("root")
        a = tmp_path / "a"
        a.mkdir()
        (a / ".lidco-rules").write_text("a")
        b = a / "b"
        b.mkdir()
        (b / ".lidco-rules").write_text("b")
        c = b / "c"
        c.mkdir()

        resolver = DirectoryRulesResolver(tmp_path)
        rules = resolver.resolve(c / "file.py")
        assert len(rules) == 3
        assert [r.content for r in rules] == ["root", "a", "b"]
        assert rules[0].priority < rules[1].priority < rules[2].priority

    def test_handles_missing_file_gracefully(self, tmp_path):
        resolver = DirectoryRulesResolver(tmp_path)
        # Nonexistent intermediate dirs should not crash
        rules = resolver.resolve(tmp_path / "nonexistent" / "file.py")
        assert isinstance(rules, list)

    def test_does_not_walk_above_project_root(self, tmp_path):
        # Place a rules file in the parent of project_root
        parent_rules = tmp_path / ".lidco-rules"
        parent_rules.write_text("parent leak")

        project = tmp_path / "project"
        project.mkdir()

        resolver = DirectoryRulesResolver(project)
        rules = resolver.resolve(project / "file.py")
        # Should NOT find the parent's rules
        assert len(rules) == 0

    def test_empty_rules_file_skipped(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("")

        resolver = DirectoryRulesResolver(tmp_path)
        rules = resolver.resolve(tmp_path / "file.py")
        assert len(rules) == 0

    def test_whitespace_only_rules_file_skipped(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("   \n\n  ")

        resolver = DirectoryRulesResolver(tmp_path)
        rules = resolver.resolve(tmp_path / "file.py")
        assert len(rules) == 0

    def test_custom_filename(self, tmp_path):
        (tmp_path / ".my-rules").write_text("custom")

        resolver = DirectoryRulesResolver(tmp_path, filename=".my-rules")
        rules = resolver.resolve(tmp_path / "file.py")
        assert len(rules) == 1
        assert rules[0].content == "custom"

    def test_source_file_field_is_set(self, tmp_path):
        rf = tmp_path / ".lidco-rules"
        rf.write_text("content")

        resolver = DirectoryRulesResolver(tmp_path)
        rules = resolver.resolve(tmp_path / "file.py")
        assert rules[0].source_file == str(rf)

    def test_path_field_matches_directory(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("hi")

        resolver = DirectoryRulesResolver(tmp_path)
        rules = resolver.resolve(tmp_path / "file.py")
        assert rules[0].path == str(tmp_path)

    def test_unreadable_file_skipped(self, tmp_path):
        rf = tmp_path / ".lidco-rules"
        rf.write_text("secret")

        resolver = DirectoryRulesResolver(tmp_path)
        # Simulate read failure via cache that always raises
        original_read = Path.read_text

        def bad_read(self, *a, **kw):
            if self.name == ".lidco-rules":
                raise PermissionError("denied")
            return original_read(self, *a, **kw)

        import unittest.mock as mock

        with mock.patch.object(Path, "read_text", bad_read):
            rules = resolver.resolve(tmp_path / "file.py")
        assert len(rules) == 0


# ---------------------------------------------------------------------------
# DirectoryRulesResolver.resolve_merged
# ---------------------------------------------------------------------------


class TestResolveMerged:
    def test_resolve_merged_contains_all(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("root rule")
        src = tmp_path / "src"
        src.mkdir()
        (src / ".lidco-rules").write_text("src rule")

        resolver = DirectoryRulesResolver(tmp_path)
        merged = resolver.resolve_merged(src / "foo.py")
        assert "root rule" in merged
        assert "src rule" in merged

    def test_merged_has_section_headers(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("root rule")
        src = tmp_path / "src"
        src.mkdir()
        (src / ".lidco-rules").write_text("src rule")

        resolver = DirectoryRulesResolver(tmp_path)
        merged = resolver.resolve_merged(src / "foo.py")
        assert "--- Rules from" in merged

    def test_merged_returns_empty_when_no_rules(self, tmp_path):
        resolver = DirectoryRulesResolver(tmp_path)
        merged = resolver.resolve_merged(tmp_path / "file.py")
        assert merged == ""

    def test_merged_nearest_appears_last(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("root rule")
        src = tmp_path / "src"
        src.mkdir()
        (src / ".lidco-rules").write_text("src rule")

        resolver = DirectoryRulesResolver(tmp_path)
        merged = resolver.resolve_merged(src / "foo.py")
        root_pos = merged.index("root rule")
        src_pos = merged.index("src rule")
        assert root_pos < src_pos


# ---------------------------------------------------------------------------
# DirectoryRulesResolver.find_all_rules
# ---------------------------------------------------------------------------


class TestFindAllRules:
    def test_find_all_rules(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("root")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / ".lidco-rules").write_text("sub")

        resolver = DirectoryRulesResolver(tmp_path)
        all_rules = resolver.find_all_rules()
        assert len(all_rules) == 2

    def test_find_all_rules_empty_project(self, tmp_path):
        resolver = DirectoryRulesResolver(tmp_path)
        assert resolver.find_all_rules() == []

    def test_find_all_rules_skips_empty_files(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / ".lidco-rules").write_text("has content")

        resolver = DirectoryRulesResolver(tmp_path)
        all_rules = resolver.find_all_rules()
        assert len(all_rules) == 1
        assert all_rules[0].content == "has content"


# ---------------------------------------------------------------------------
# DirectoryRulesResolver.inject_for_context
# ---------------------------------------------------------------------------


class TestInjectForContext:
    def test_inject_deduplicates_shared_ancestors(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("shared rule")
        src = tmp_path / "src"
        src.mkdir()

        resolver = DirectoryRulesResolver(tmp_path)
        text = resolver.inject_for_context(
            [str(src / "a.py"), str(src / "b.py")]
        )
        assert text.count("shared rule") == 1

    def test_inject_for_context_prefix(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("use type hints")

        resolver = DirectoryRulesResolver(tmp_path)
        text = resolver.inject_for_context([str(tmp_path / "foo.py")])
        assert text.startswith("## AI Rules")

    def test_inject_combines_different_branches(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("shared")
        a = tmp_path / "a"
        a.mkdir()
        (a / ".lidco-rules").write_text("branch-a")
        b = tmp_path / "b"
        b.mkdir()
        (b / ".lidco-rules").write_text("branch-b")

        resolver = DirectoryRulesResolver(tmp_path)
        text = resolver.inject_for_context(
            [str(a / "f.py"), str(b / "g.py")]
        )
        assert text.count("shared") == 1
        assert "branch-a" in text
        assert "branch-b" in text

    def test_inject_returns_empty_when_no_rules(self, tmp_path):
        resolver = DirectoryRulesResolver(tmp_path)
        text = resolver.inject_for_context([str(tmp_path / "f.py")])
        assert text == ""

    def test_inject_empty_file_list(self, tmp_path):
        (tmp_path / ".lidco-rules").write_text("rule")
        resolver = DirectoryRulesResolver(tmp_path)
        text = resolver.inject_for_context([])
        assert text == ""
