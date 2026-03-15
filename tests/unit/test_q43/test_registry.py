"""Tests for SkillRegistry — Task 294 & 297."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from lidco.skills.skill import Skill
from lidco.skills.registry import SkillRegistry


def _write_skill(directory: Path, name: str, prompt: str = "Do {args}.") -> Path:
    p = directory / f"{name}.md"
    content = textwrap.dedent(f"""\
        ---
        name: {name}
        description: {name} skill
        ---
        {prompt}
    """)
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# SkillRegistry.load()
# ---------------------------------------------------------------------------

class TestSkillRegistryLoad:
    def test_empty_dir_loads_zero(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        reg = SkillRegistry(project_dir=tmp_path, extra_dirs=[skills_dir])
        n = reg.load()
        assert n == 0

    def test_loads_md_skills(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "review")
        _write_skill(skills_dir, "lint")
        reg = SkillRegistry(project_dir=tmp_path, extra_dirs=[skills_dir])
        n = reg.load()
        assert n == 2

    def test_loads_yaml_skills(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "fmt.yaml").write_text(
            "name: fmt\nprompt: Format.\n", encoding="utf-8"
        )
        reg = SkillRegistry(project_dir=tmp_path, extra_dirs=[skills_dir])
        n = reg.load()
        assert n == 1

    def test_project_overrides_global(self, tmp_path):
        global_dir = tmp_path / "global"
        global_dir.mkdir()
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        _write_skill(global_dir, "review")
        # Write project-local version with different prompt
        p = project_dir / "review.md"
        p.write_text(
            "---\nname: review\n---\nProject review prompt.\n",
            encoding="utf-8",
        )
        reg = SkillRegistry(
            project_dir=tmp_path,
            extra_dirs=[global_dir, project_dir],
        )
        reg.load()
        skill = reg.get("review")
        assert skill is not None
        assert "Project" in skill.prompt

    def test_invalid_file_skipped(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "bad.md").write_text("no frontmatter", encoding="utf-8")
        _write_skill(skills_dir, "good")
        reg = SkillRegistry(project_dir=tmp_path, extra_dirs=[skills_dir])
        n = reg.load()
        assert n == 1  # only "good" loaded


# ---------------------------------------------------------------------------
# SkillRegistry CRUD
# ---------------------------------------------------------------------------

class TestSkillRegistryCRUD:
    def _reg_with_one(self, tmp_path) -> SkillRegistry:
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "review")
        reg = SkillRegistry(project_dir=tmp_path, extra_dirs=[skills_dir])
        reg.load()
        return reg

    def test_get_existing(self, tmp_path):
        reg = self._reg_with_one(tmp_path)
        skill = reg.get("review")
        assert skill is not None
        assert skill.name == "review"

    def test_get_missing_returns_none(self, tmp_path):
        reg = self._reg_with_one(tmp_path)
        assert reg.get("nonexistent") is None

    def test_list_skills_sorted(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "zap")
        _write_skill(skills_dir, "alpha")
        _write_skill(skills_dir, "middle")
        reg = SkillRegistry(project_dir=tmp_path, extra_dirs=[skills_dir])
        reg.load()
        names = [s.name for s in reg.list_skills()]
        assert names == sorted(names)

    def test_names_returns_sorted_list(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        _write_skill(skills_dir, "b_skill")
        _write_skill(skills_dir, "a_skill")
        reg = SkillRegistry(project_dir=tmp_path, extra_dirs=[skills_dir])
        reg.load()
        assert reg.names() == ["a_skill", "b_skill"]

    def test_register_manual(self, tmp_path):
        reg = SkillRegistry(project_dir=tmp_path)
        skill = Skill(name="manual", prompt="Manual prompt")
        reg.register(skill)
        assert reg.get("manual") is skill

    def test_unregister_existing(self, tmp_path):
        reg = SkillRegistry(project_dir=tmp_path)
        skill = Skill(name="temp", prompt="Temp")
        reg.register(skill)
        result = reg.unregister("temp")
        assert result is True
        assert reg.get("temp") is None

    def test_unregister_missing_returns_false(self, tmp_path):
        reg = SkillRegistry(project_dir=tmp_path)
        assert reg.unregister("ghost") is False

    def test_reload_refreshes(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        reg = SkillRegistry(project_dir=tmp_path, extra_dirs=[skills_dir])
        assert reg.load() == 0
        _write_skill(skills_dir, "new_skill")
        n = reg.reload()
        assert n == 1
        assert reg.get("new_skill") is not None
