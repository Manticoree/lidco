"""Tests for SkillValidator — Task 299."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lidco.skills.skill import Skill
from lidco.skills.validator import SkillValidator, ValidationResult


@pytest.fixture
def validator() -> SkillValidator:
    return SkillValidator()


def _good_skill(**kwargs) -> Skill:
    defaults = {
        "name": "review",
        "prompt": "Review {args} for quality.",
        "version": "1.0",
        "requires": [],
        "scripts": {},
    }
    defaults.update(kwargs)
    return Skill(**defaults)


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

class TestValidationResult:
    def test_valid_when_no_issues(self):
        r = ValidationResult(skill_name="test", issues=[])
        assert r.valid is True

    def test_invalid_when_issues(self):
        r = ValidationResult(skill_name="test", issues=["problem"])
        assert r.valid is False

    def test_str_ok(self):
        r = ValidationResult(skill_name="good", issues=[])
        assert "OK" in str(r)

    def test_str_shows_count(self):
        r = ValidationResult(skill_name="bad", issues=["issue1", "issue2"])
        assert "2" in str(r)
        assert "issue1" in str(r)


# ---------------------------------------------------------------------------
# Name validation
# ---------------------------------------------------------------------------

class TestValidateName:
    def test_valid_name(self, validator):
        skill = _good_skill(name="review")
        result = validator.validate(skill)
        name_issues = [i for i in result.issues if "Name" in i]
        assert not name_issues

    def test_hyphen_allowed(self, validator):
        skill = _good_skill(name="code-review")
        result = validator.validate(skill)
        name_issues = [i for i in result.issues if "Name" in i]
        assert not name_issues

    def test_underscore_allowed(self, validator):
        skill = _good_skill(name="my_skill")
        result = validator.validate(skill)
        name_issues = [i for i in result.issues if "Name" in i]
        assert not name_issues

    def test_uppercase_invalid(self, validator):
        skill = _good_skill(name="Review")
        result = validator.validate(skill)
        name_issues = [i for i in result.issues if "Name" in i or "name" in i.lower()]
        assert name_issues

    def test_empty_name_invalid(self, validator):
        skill = _good_skill(name="")
        result = validator.validate(skill)
        assert not result.valid

    def test_starts_with_digit_valid(self, validator):
        skill = _good_skill(name="2review")
        result = validator.validate(skill)
        name_issues = [i for i in result.issues if "Name" in i]
        assert not name_issues


# ---------------------------------------------------------------------------
# Version validation
# ---------------------------------------------------------------------------

class TestValidateVersion:
    def test_valid_version_1_0(self, validator):
        skill = _good_skill(version="1.0")
        result = validator.validate(skill)
        ver_issues = [i for i in result.issues if "version" in i.lower() or "Version" in i]
        assert not ver_issues

    def test_valid_version_2_1_3(self, validator):
        skill = _good_skill(version="2.1.3")
        result = validator.validate(skill)
        ver_issues = [i for i in result.issues if "version" in i.lower() or "Version" in i]
        assert not ver_issues

    def test_invalid_version_alpha(self, validator):
        skill = _good_skill(version="abc")
        result = validator.validate(skill)
        ver_issues = [i for i in result.issues if "version" in i.lower() or "Version" in i]
        assert ver_issues

    def test_invalid_version_with_v_prefix(self, validator):
        skill = _good_skill(version="v1.0")
        result = validator.validate(skill)
        ver_issues = [i for i in result.issues if "version" in i.lower() or "Version" in i]
        assert ver_issues

    def test_empty_version_ok(self, validator):
        skill = _good_skill(version="")
        result = validator.validate(skill)
        ver_issues = [i for i in result.issues if "version" in i.lower() or "Version" in i]
        assert not ver_issues


# ---------------------------------------------------------------------------
# Prompt validation
# ---------------------------------------------------------------------------

class TestValidatePrompt:
    def test_empty_prompt_invalid(self, validator):
        skill = _good_skill(prompt="")
        result = validator.validate(skill)
        prompt_issues = [i for i in result.issues if "prompt" in i.lower()]
        assert prompt_issues

    def test_whitespace_prompt_invalid(self, validator):
        skill = _good_skill(prompt="   ")
        result = validator.validate(skill)
        prompt_issues = [i for i in result.issues if "prompt" in i.lower()]
        assert prompt_issues

    def test_non_empty_prompt_valid(self, validator):
        skill = _good_skill(prompt="Do something useful.")
        result = validator.validate(skill)
        prompt_issues = [i for i in result.issues if "prompt" in i.lower()]
        assert not prompt_issues


# ---------------------------------------------------------------------------
# Requirements validation
# ---------------------------------------------------------------------------

class TestValidateRequires:
    def test_missing_tool_reported(self, validator):
        skill = _good_skill(requires=["nonexistent_tool_xyz_12345"])
        result = validator.validate(skill)
        req_issues = [i for i in result.issues if "nonexistent_tool_xyz" in i]
        assert req_issues

    def test_present_tool_ok(self, validator):
        with patch("shutil.which", return_value="/usr/bin/git"):
            skill = _good_skill(requires=["git"])
            result = validator.validate(skill)
            req_issues = [i for i in result.issues if "git" in i and "PATH" in i]
            assert not req_issues

    def test_no_requires_ok(self, validator):
        skill = _good_skill(requires=[])
        result = validator.validate(skill)
        req_issues = [i for i in result.issues if "PATH" in i]
        assert not req_issues


# ---------------------------------------------------------------------------
# Scripts validation
# ---------------------------------------------------------------------------

class TestValidateScripts:
    def test_valid_scripts(self, validator):
        skill = _good_skill(scripts={"pre": "echo hi", "post": "echo done"})
        result = validator.validate(skill)
        script_issues = [i for i in result.issues if "hook" in i.lower() or "script" in i.lower()]
        assert not script_issues

    def test_unknown_hook_reported(self, validator):
        skill = _good_skill(scripts={"build": "make all"})
        result = validator.validate(skill)
        hook_issues = [i for i in result.issues if "hook" in i.lower() or "Unknown" in i]
        assert hook_issues

    def test_empty_command_reported(self, validator):
        skill = _good_skill(scripts={"pre": "   "})
        result = validator.validate(skill)
        cmd_issues = [i for i in result.issues if "empty" in i.lower() or "command" in i.lower()]
        assert cmd_issues


# ---------------------------------------------------------------------------
# validate_many()
# ---------------------------------------------------------------------------

class TestValidateMany:
    def test_validate_many_returns_all_results(self, validator):
        skills = [
            _good_skill(name="review"),
            _good_skill(name="lint"),
            _good_skill(name=""),   # invalid
        ]
        results = validator.validate_many(skills)
        assert len(results) == 3
        assert results[2].valid is False

    def test_validate_many_preserves_order(self, validator):
        skills = [_good_skill(name=n) for n in ("a", "b", "c")]
        results = validator.validate_many(skills)
        names = [r.skill_name for r in results]
        assert names == ["a", "b", "c"]
