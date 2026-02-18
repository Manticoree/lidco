"""Tests for the rules management system."""

import pytest
from pathlib import Path

from lidco.core.rules import RulesManager, Rule, _DEFAULT_RULES_TEMPLATE


class TestRulesManagerInit:
    """Tests for RulesManager initialization and path resolution."""

    def test_default_paths(self, tmp_path):
        mgr = RulesManager(tmp_path)
        assert mgr.rules_file == tmp_path / "LIDCO.md"
        assert mgr.rules_dir == tmp_path / ".lidco" / "rules"

    def test_project_dir_stored(self, tmp_path):
        mgr = RulesManager(tmp_path)
        assert mgr.project_dir == tmp_path


class TestHasRulesFile:
    """Tests for has_rules_file detection."""

    def test_false_when_no_file(self, tmp_path):
        mgr = RulesManager(tmp_path)
        assert mgr.has_rules_file() is False

    def test_true_when_file_exists(self, tmp_path):
        (tmp_path / "LIDCO.md").write_text("# Rules")
        mgr = RulesManager(tmp_path)
        assert mgr.has_rules_file() is True


class TestInitRules:
    """Tests for init_rules — creating the default LIDCO.md."""

    def test_creates_lidco_md(self, tmp_path):
        mgr = RulesManager(tmp_path)
        path = mgr.init_rules()
        assert path == tmp_path / "LIDCO.md"
        assert path.exists()

    def test_uses_dir_name_as_default_project_name(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        content = mgr.rules_file.read_text(encoding="utf-8")
        assert tmp_path.name in content

    def test_uses_custom_project_name(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules(project_name="MyApp")
        content = mgr.rules_file.read_text(encoding="utf-8")
        assert "MyApp" in content

    def test_creates_rules_directory(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        assert (tmp_path / ".lidco" / "rules").is_dir()

    def test_raises_if_file_already_exists(self, tmp_path):
        (tmp_path / "LIDCO.md").write_text("# Existing")
        mgr = RulesManager(tmp_path)
        with pytest.raises(FileExistsError):
            mgr.init_rules()

    def test_content_contains_default_sections(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        content = mgr.rules_file.read_text(encoding="utf-8")
        assert "## Code Style" in content
        assert "## Project Structure" in content
        assert "## Git Workflow" in content
        assert "## Testing" in content

    def test_returns_path_to_created_file(self, tmp_path):
        mgr = RulesManager(tmp_path)
        result = mgr.init_rules()
        assert isinstance(result, Path)
        assert result.exists()


class TestAddRule:
    """Tests for appending rules to LIDCO.md."""

    def test_appends_rule_to_existing_file(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        mgr.add_rule("No Magic Numbers", "Always use named constants")
        content = mgr.rules_file.read_text(encoding="utf-8")
        assert "## No Magic Numbers" in content
        assert "Always use named constants" in content

    def test_creates_file_if_missing_then_appends(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.add_rule("Security", "Validate all inputs")
        assert mgr.rules_file.exists()
        content = mgr.rules_file.read_text(encoding="utf-8")
        assert "## Security" in content
        assert "Validate all inputs" in content
        # Default sections should also be present
        assert "## Code Style" in content

    def test_multiple_rules_appended_in_order(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        mgr.add_rule("Rule A", "First rule")
        mgr.add_rule("Rule B", "Second rule")
        content = mgr.rules_file.read_text(encoding="utf-8")
        pos_a = content.index("## Rule A")
        pos_b = content.index("## Rule B")
        assert pos_a < pos_b

    def test_preserves_existing_content(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules(project_name="TestProject")
        original = mgr.rules_file.read_text(encoding="utf-8")
        mgr.add_rule("Extra", "Extra content")
        updated = mgr.rules_file.read_text(encoding="utf-8")
        # Original content (minus trailing whitespace) should be a prefix
        assert updated.startswith(original.rstrip())


class TestAddRuleFile:
    """Tests for creating separate rule files in .lidco/rules/."""

    def test_creates_file_in_rules_dir(self, tmp_path):
        mgr = RulesManager(tmp_path)
        path = mgr.add_rule_file("security", "Always sanitize HTML")
        assert path.exists()
        assert path.parent == tmp_path / ".lidco" / "rules"

    def test_creates_rules_dir_if_missing(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.add_rule_file("test", "content")
        assert (tmp_path / ".lidco" / "rules").is_dir()

    def test_sanitizes_filename_spaces(self, tmp_path):
        mgr = RulesManager(tmp_path)
        path = mgr.add_rule_file("Code Style Guide", "Use tabs")
        assert path.name == "code-style-guide.md"

    def test_sanitizes_filename_lowercase(self, tmp_path):
        mgr = RulesManager(tmp_path)
        path = mgr.add_rule_file("MyRules", "content")
        assert path.name == "myrules.md"

    def test_appends_md_extension(self, tmp_path):
        mgr = RulesManager(tmp_path)
        path = mgr.add_rule_file("testing", "write tests first")
        assert path.suffix == ".md"

    def test_does_not_double_md_extension(self, tmp_path):
        mgr = RulesManager(tmp_path)
        path = mgr.add_rule_file("testing.md", "write tests first")
        assert path.name == "testing.md"
        assert not path.name.endswith(".md.md")

    def test_file_content_has_heading_and_body(self, tmp_path):
        mgr = RulesManager(tmp_path)
        path = mgr.add_rule_file("auth", "Use JWT tokens")
        content = path.read_text(encoding="utf-8")
        assert content.startswith("# auth")
        assert "Use JWT tokens" in content

    def test_returns_path(self, tmp_path):
        mgr = RulesManager(tmp_path)
        result = mgr.add_rule_file("test", "content")
        assert isinstance(result, Path)


class TestListRules:
    """Tests for listing rules parsed from LIDCO.md."""

    def test_empty_when_no_file(self, tmp_path):
        mgr = RulesManager(tmp_path)
        assert mgr.list_rules() == []

    def test_parses_default_rules(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        rules = mgr.list_rules()
        titles = [r.title for r in rules]
        assert "Code Style" in titles
        assert "Project Structure" in titles
        assert "Git Workflow" in titles
        assert "Testing" in titles

    def test_includes_added_rules(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        mgr.add_rule("Custom Rule", "Do the thing")
        rules = mgr.list_rules()
        titles = [r.title for r in rules]
        assert "Custom Rule" in titles

    def test_rule_content_is_stripped(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        rules = mgr.list_rules()
        for rule in rules:
            assert rule.content == rule.content.strip()

    def test_returns_rule_objects(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        rules = mgr.list_rules()
        assert all(isinstance(r, Rule) for r in rules)


class TestListRuleFiles:
    """Tests for listing .md files in .lidco/rules/."""

    def test_empty_when_no_dir(self, tmp_path):
        mgr = RulesManager(tmp_path)
        assert mgr.list_rule_files() == []

    def test_empty_when_dir_exists_but_empty(self, tmp_path):
        (tmp_path / ".lidco" / "rules").mkdir(parents=True)
        mgr = RulesManager(tmp_path)
        assert mgr.list_rule_files() == []

    def test_lists_created_files(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.add_rule_file("alpha", "content a")
        mgr.add_rule_file("beta", "content b")
        files = mgr.list_rule_files()
        assert len(files) == 2
        names = [f.name for f in files]
        assert "alpha.md" in names
        assert "beta.md" in names

    def test_sorted_alphabetically(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.add_rule_file("zebra", "z")
        mgr.add_rule_file("alpha", "a")
        files = mgr.list_rule_files()
        assert files[0].name == "alpha.md"
        assert files[1].name == "zebra.md"

    def test_ignores_non_md_files(self, tmp_path):
        rules_dir = tmp_path / ".lidco" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "notes.txt").write_text("not a rule")
        (rules_dir / "rule.md").write_text("# Rule")
        mgr = RulesManager(tmp_path)
        files = mgr.list_rule_files()
        assert len(files) == 1
        assert files[0].name == "rule.md"


class TestGetAllRulesText:
    """Tests for combined rules text output."""

    def test_empty_when_nothing(self, tmp_path):
        mgr = RulesManager(tmp_path)
        assert mgr.get_all_rules_text() == ""

    def test_includes_lidco_md(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules(project_name="Demo")
        text = mgr.get_all_rules_text()
        assert "Demo" in text
        assert "## Code Style" in text

    def test_includes_rule_files(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        mgr.add_rule_file("security", "Never trust user input")
        text = mgr.get_all_rules_text()
        assert "Never trust user input" in text

    def test_separator_between_sections(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.init_rules()
        mgr.add_rule_file("extra", "Extra rules here")
        text = mgr.get_all_rules_text()
        assert "\n---\n" in text

    def test_only_rule_files_without_lidco_md(self, tmp_path):
        mgr = RulesManager(tmp_path)
        mgr.add_rule_file("standalone", "Standalone rule")
        text = mgr.get_all_rules_text()
        assert "Standalone rule" in text


class TestParseRules:
    """Tests for the static _parse_rules method."""

    def test_empty_text(self):
        assert RulesManager._parse_rules("") == []

    def test_text_without_headings(self):
        assert RulesManager._parse_rules("Just plain text\nno headings") == []

    def test_single_rule(self):
        text = "## My Rule\n\nDo something important."
        rules = RulesManager._parse_rules(text)
        assert len(rules) == 1
        assert rules[0].title == "My Rule"
        assert rules[0].content == "Do something important."

    def test_multiple_rules(self):
        text = "## Rule A\n\nContent A\n\n## Rule B\n\nContent B"
        rules = RulesManager._parse_rules(text)
        assert len(rules) == 2
        assert rules[0].title == "Rule A"
        assert rules[1].title == "Rule B"

    def test_ignores_h1_headings(self):
        text = "# Title\n\nIntro text\n\n## Actual Rule\n\nContent"
        rules = RulesManager._parse_rules(text)
        assert len(rules) == 1
        assert rules[0].title == "Actual Rule"

    def test_ignores_h3_headings(self):
        text = "## Parent Rule\n\n### Sub-heading\n\nSub content"
        rules = RulesManager._parse_rules(text)
        assert len(rules) == 1
        assert "### Sub-heading" in rules[0].content

    def test_multiline_content(self):
        text = "## Style\n\n- Use tabs\n- No semicolons\n- Max 80 chars"
        rules = RulesManager._parse_rules(text)
        assert len(rules) == 1
        assert "- Use tabs" in rules[0].content
        assert "- Max 80 chars" in rules[0].content

    def test_content_is_stripped(self):
        text = "## Rule\n\n\n  Content here  \n\n\n"
        rules = RulesManager._parse_rules(text)
        assert rules[0].content == "Content here"

    def test_consecutive_headings(self):
        text = "## First\n## Second\n\nContent"
        rules = RulesManager._parse_rules(text)
        assert len(rules) == 2
        assert rules[0].title == "First"
        assert rules[0].content == ""
        assert rules[1].title == "Second"


class TestRuleDataclass:
    """Tests for the Rule frozen dataclass."""

    def test_creation(self):
        rule = Rule(title="Test", content="Body")
        assert rule.title == "Test"
        assert rule.content == "Body"

    def test_frozen(self):
        rule = Rule(title="Test", content="Body")
        with pytest.raises(AttributeError):
            rule.title = "Changed"

    def test_equality(self):
        r1 = Rule(title="A", content="B")
        r2 = Rule(title="A", content="B")
        assert r1 == r2

    def test_inequality(self):
        r1 = Rule(title="A", content="B")
        r2 = Rule(title="A", content="C")
        assert r1 != r2
