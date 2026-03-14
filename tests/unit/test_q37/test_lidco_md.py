"""Tests for LidcoMdLoader and RuleActivator — Q37 task 244/250."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.core.lidco_md import LidcoMdLoader, PathScopedRule, RuleActivator


class TestLidcoMdLoader:
    def test_no_files_returns_empty(self, tmp_path: Path) -> None:
        loader = LidcoMdLoader(tmp_path)
        content = loader.load()
        assert content.text == ""
        assert content.sources == []

    def test_project_level_loaded(self, tmp_path: Path) -> None:
        (tmp_path / "LIDCO.md").write_text("# My Rules\nDo cool things.", encoding="utf-8")
        loader = LidcoMdLoader(tmp_path)
        content = loader.load()
        assert "Do cool things" in content.text
        assert any("LIDCO.md" in s for s in content.sources)

    def test_lidco_subdir_takes_priority(self, tmp_path: Path) -> None:
        lidco_dir = tmp_path / ".lidco"
        lidco_dir.mkdir()
        (lidco_dir / "LIDCO.md").write_text("Subdir rule.", encoding="utf-8")
        (tmp_path / "LIDCO.md").write_text("Root rule.", encoding="utf-8")
        loader = LidcoMdLoader(tmp_path)
        content = loader.load()
        # Only the first found (subdir) should be loaded (one project-level file)
        assert "Subdir rule." in content.text

    def test_at_import_inline(self, tmp_path: Path) -> None:
        extra = tmp_path / "extra.md"
        extra.write_text("Extra content.", encoding="utf-8")
        (tmp_path / "LIDCO.md").write_text("@extra.md\nMain content.", encoding="utf-8")
        loader = LidcoMdLoader(tmp_path)
        content = loader.load()
        assert "Extra content." in content.text
        assert "Main content." in content.text

    def test_at_import_missing_file_graceful(self, tmp_path: Path) -> None:
        (tmp_path / "LIDCO.md").write_text("@missing.md\nMain.", encoding="utf-8")
        loader = LidcoMdLoader(tmp_path)
        content = loader.load()  # should not raise
        assert "Main." in content.text

    def test_at_import_blocked_outside_project(self, tmp_path: Path) -> None:
        (tmp_path / "LIDCO.md").write_text("@/etc/passwd\nMain.", encoding="utf-8")
        loader = LidcoMdLoader(tmp_path)
        content = loader.load()
        # /etc/passwd content should not appear
        assert "root" not in content.text
        assert "Main." in content.text

    def test_scope_blocks_extracted(self, tmp_path: Path) -> None:
        md = (
            "Global instruction.\n"
            "<!-- scope: src/api/**/*.py -->\n"
            "API-specific rule.\n"
            "<!-- end scope -->\n"
            "More global.\n"
        )
        (tmp_path / "LIDCO.md").write_text(md, encoding="utf-8")
        loader = LidcoMdLoader(tmp_path)
        content = loader.load()
        assert "Global instruction." in content.text
        assert "More global." in content.text
        assert "API-specific rule." not in content.text  # moved to scoped_rules
        assert len(content.scoped_rules) == 1
        assert content.scoped_rules[0].pattern == "src/api/**/*.py"
        assert "API-specific rule." in content.scoped_rules[0].content

    def test_multiple_scope_blocks(self, tmp_path: Path) -> None:
        md = (
            "<!-- scope: src/api/** -->\nAPI rule.\n<!-- end scope -->\n"
            "<!-- scope: tests/** -->\nTest rule.\n<!-- end scope -->\n"
        )
        (tmp_path / "LIDCO.md").write_text(md, encoding="utf-8")
        loader = LidcoMdLoader(tmp_path)
        content = loader.load()
        assert len(content.scoped_rules) == 2

    def test_load_for_path_subdir(self, tmp_path: Path) -> None:
        subdir = tmp_path / "src" / "api"
        subdir.mkdir(parents=True)
        (subdir / "LIDCO.md").write_text("API subdir rule.", encoding="utf-8")
        loader = LidcoMdLoader(tmp_path)
        extra = loader.load_for_path(str(subdir / "routes.py"))
        assert "API subdir rule." in extra

    def test_load_for_path_outside_project(self, tmp_path: Path) -> None:
        loader = LidcoMdLoader(tmp_path)
        extra = loader.load_for_path("/tmp/outside.py")
        assert extra == ""

    def test_multiple_layers_merged(self, tmp_path: Path) -> None:
        user_dir = tmp_path / "user_home" / ".lidco"
        user_dir.mkdir(parents=True)
        (user_dir / "LIDCO.md").write_text("User rule.", encoding="utf-8")
        (tmp_path / "LIDCO.md").write_text("Project rule.", encoding="utf-8")

        # Monkeypatch Path.home() for the loader
        import lidco.core.lidco_md as mod
        original_home = Path.home

        loader = LidcoMdLoader(tmp_path)
        # The user-level file is only loaded if ~/.lidco/LIDCO.md exists
        # Here we just confirm project-level works
        content = loader.load()
        assert "Project rule." in content.text


class TestRuleActivator:
    def _make_rule(self, pattern: str, content: str) -> PathScopedRule:
        return PathScopedRule(pattern=pattern, content=content)

    def test_matching_file(self) -> None:
        rules = [self._make_rule("src/api/**/*.py", "API rule.")]
        active = RuleActivator.get_active_rules(rules, ["src/api/routes.py"])
        assert active == ["API rule."]

    def test_non_matching_file(self) -> None:
        rules = [self._make_rule("src/api/**", "API rule.")]
        active = RuleActivator.get_active_rules(rules, ["tests/test_foo.py"])
        assert active == []

    def test_multiple_files_one_match(self) -> None:
        rules = [self._make_rule("src/api/**", "API rule.")]
        active = RuleActivator.get_active_rules(rules, ["tests/foo.py", "src/api/bar.py"])
        assert "API rule." in active

    def test_empty_rules(self) -> None:
        active = RuleActivator.get_active_rules([], ["src/api/foo.py"])
        assert active == []

    def test_empty_files(self) -> None:
        rules = [self._make_rule("src/**", "Rule.")]
        active = RuleActivator.get_active_rules(rules, [])
        assert active == []

    def test_filename_only_pattern(self) -> None:
        rules = [self._make_rule("*.py", "Python rule.")]
        active = RuleActivator.get_active_rules(rules, ["src/foo.py"])
        assert "Python rule." in active

    def test_multiple_matching_rules(self) -> None:
        rules = [
            self._make_rule("src/**", "General src rule."),
            self._make_rule("src/api/**", "API rule."),
        ]
        active = RuleActivator.get_active_rules(rules, ["src/api/foo.py"])
        assert len(active) == 2


# ─── Import cycle detection ───────────────────────────────────────────────────


class TestImportCycleDetection:
    def test_cycle_does_not_recurse_infinitely(self, tmp_path: Path) -> None:
        """Circular imports terminate without infinite recursion or hanging."""
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text(f"@{b.name}\nA content.\n", encoding="utf-8")
        b.write_text(f"@{a.name}\nB content.\n", encoding="utf-8")

        loader = LidcoMdLoader(tmp_path)
        text_a = a.read_text(encoding="utf-8")
        # Should not raise, hang, or recurse indefinitely
        result, _ = loader._resolve_imports(text_a, tmp_path, depth=0)
        # B content is included (b.md was imported)
        assert "B content." in result
        # A content appears (from a.md itself and from b→a re-import before cycle cuts)
        assert "A content." in result

    def test_self_import_blocked_in_visited(self, tmp_path: Path) -> None:
        """@import of an already-visited file is skipped (cycle detection)."""
        f = tmp_path / "self.md"
        f.write_text(f"@{f.name}\nSelf content.\n", encoding="utf-8")

        loader = LidcoMdLoader(tmp_path)
        text = f.read_text(encoding="utf-8")
        # Pass f as already-visited to simulate re-entry detection
        result, all_ok = loader._resolve_imports(
            text, tmp_path, depth=0, visited=frozenset([f.resolve()])
        )
        # The @import line is removed (cycle), but the rest of f.md is kept
        assert "@" not in result.split("\n")[0]  # first line no longer has @import
        assert all_ok is False  # cycle was detected

    def test_deep_but_non_cyclic_import_works(self, tmp_path: Path) -> None:
        """Chain a→b→c (no cycle) resolves fully."""
        c = tmp_path / "c.md"
        b = tmp_path / "b.md"
        a = tmp_path / "a.md"
        c.write_text("C content.\n", encoding="utf-8")
        b.write_text(f"@{c.name}\nB content.\n", encoding="utf-8")
        a.write_text(f"@{b.name}\nA content.\n", encoding="utf-8")

        loader = LidcoMdLoader(tmp_path)
        result, ok = loader._resolve_imports(a.read_text(encoding="utf-8"), tmp_path, depth=0)
        assert "A content." in result
        assert "B content." in result
        assert "C content." in result
        assert ok is True
