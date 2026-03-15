"""Tests for Skill dataclass and parse_skill_file — Task 293."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from lidco.skills.skill import Skill, parse_skill_file


# ---------------------------------------------------------------------------
# Skill.render()
# ---------------------------------------------------------------------------

class TestSkillRender:
    def test_render_replaces_args(self):
        skill = Skill(name="test", prompt="Review {args} carefully.")
        assert skill.render("src/foo.py") == "Review src/foo.py carefully."

    def test_render_empty_args(self):
        skill = Skill(name="test", prompt="Do something. {args}")
        assert skill.render("") == "Do something."

    def test_render_no_placeholder(self):
        skill = Skill(name="test", prompt="Plain prompt")
        assert skill.render("extra") == "Plain prompt"

    def test_render_strips_whitespace(self):
        skill = Skill(name="test", prompt="  Hello {args}  ")
        assert skill.render("world") == "Hello world"


# ---------------------------------------------------------------------------
# Skill.check_requirements()
# ---------------------------------------------------------------------------

class TestSkillCheckRequirements:
    def test_no_requirements_returns_empty(self):
        skill = Skill(name="test")
        assert skill.check_requirements() == []

    def test_missing_tool_reported(self):
        skill = Skill(name="test", requires=["nonexistent_tool_xyz_abc"])
        missing = skill.check_requirements()
        assert "nonexistent_tool_xyz_abc" in missing

    def test_present_tool_not_reported(self):
        with patch("shutil.which", return_value="/usr/bin/git"):
            skill = Skill(name="test", requires=["git"])
            assert skill.check_requirements() == []

    def test_mixed_requirements(self):
        def mock_which(tool):
            return "/usr/bin/git" if tool == "git" else None

        with patch("shutil.which", side_effect=mock_which):
            skill = Skill(name="test", requires=["git", "nonexistent_xyz"])
            missing = skill.check_requirements()
            assert missing == ["nonexistent_xyz"]


# ---------------------------------------------------------------------------
# Skill.run_script()
# ---------------------------------------------------------------------------

class TestSkillRunScript:
    def test_no_script_returns_true(self):
        skill = Skill(name="test")
        ok, out = skill.run_script("pre")
        assert ok is True
        assert out == ""

    def test_successful_script(self):
        skill = Skill(name="test", scripts={"pre": "echo hello"})
        ok, out = skill.run_script("pre")
        assert ok is True
        assert "hello" in out

    def test_failed_script(self):
        skill = Skill(name="test", scripts={"pre": "exit 1"})
        ok, _out = skill.run_script("pre")
        assert ok is False

    def test_post_script(self):
        skill = Skill(name="test", scripts={"post": "echo done"})
        ok, out = skill.run_script("post")
        assert ok is True
        assert "done" in out

    def test_missing_hook_returns_true(self):
        skill = Skill(name="test", scripts={"pre": "echo hi"})
        ok, out = skill.run_script("post")
        assert ok is True
        assert out == ""


# ---------------------------------------------------------------------------
# parse_skill_file — Markdown
# ---------------------------------------------------------------------------

class TestParseSkillFileMd:
    def _write(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "review.md"
        p.write_text(content, encoding="utf-8")
        return p

    def test_basic_md(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            name: review
            description: Code review skill
            version: 1.2
            ---
            Review {args} for quality.
        """)
        skill = parse_skill_file(self._write(tmp_path, content))
        assert skill.name == "review"
        assert skill.description == "Code review skill"
        assert skill.version == "1.2"
        assert "{args}" in skill.prompt or "Review" in skill.prompt

    def test_requires_list(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            name: lint
            requires: [git, python]
            ---
            Lint code.
        """)
        skill = parse_skill_file(self._write(tmp_path, content))
        assert "git" in skill.requires
        assert "python" in skill.requires

    def test_requires_string(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            name: build
            requires: "make, git"
            ---
            Build project.
        """)
        skill = parse_skill_file(self._write(tmp_path, content))
        assert "make" in skill.requires
        assert "git" in skill.requires

    def test_scripts_parsed(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            name: deploy
            scripts:
              pre: echo pre
              post: echo post
            ---
            Deploy.
        """)
        skill = parse_skill_file(self._write(tmp_path, content))
        assert skill.scripts.get("pre") == "echo pre"
        assert skill.scripts.get("post") == "echo post"

    def test_name_defaults_to_stem(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            description: No explicit name
            ---
            Do something.
        """)
        skill = parse_skill_file(self._write(tmp_path, content))
        assert skill.name == "review"  # stem of review.md

    def test_no_frontmatter_raises(self, tmp_path):
        p = tmp_path / "bad.md"
        p.write_text("No frontmatter here", encoding="utf-8")
        with pytest.raises(ValueError, match="frontmatter"):
            parse_skill_file(p)

    def test_path_stored(self, tmp_path):
        content = textwrap.dedent("""\
            ---
            name: check
            ---
            Check.
        """)
        p = tmp_path / "check.md"
        p.write_text(content, encoding="utf-8")
        skill = parse_skill_file(p)
        assert skill.path == str(p)


# ---------------------------------------------------------------------------
# parse_skill_file — YAML
# ---------------------------------------------------------------------------

class TestParseSkillFileYaml:
    def test_yaml_skill(self, tmp_path):
        content = textwrap.dedent("""\
            name: summarize
            description: Summarize text
            prompt: Summarize {args}
            version: 2.0
            requires: []
        """)
        p = tmp_path / "summarize.yaml"
        p.write_text(content, encoding="utf-8")
        skill = parse_skill_file(p)
        assert skill.name == "summarize"
        assert skill.version == "2.0"
        assert "Summarize" in skill.prompt

    def test_yml_extension(self, tmp_path):
        content = "name: fmt\nprompt: Format {args}\n"
        p = tmp_path / "fmt.yml"
        p.write_text(content, encoding="utf-8")
        skill = parse_skill_file(p)
        assert skill.name == "fmt"
