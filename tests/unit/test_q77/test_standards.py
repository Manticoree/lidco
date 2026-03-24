"""Tests for StandardsEnforcer (T509)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lidco.review.standards import StandardsEnforcer, StandardRule, Violation, CheckResult


class TestLoadRules:
    def test_load_rules_from_json_file(self):
        rules_data = [
            {
                "id": "R001",
                "name": "test-rule",
                "description": "A test rule",
                "pattern": r"forbidden",
                "severity": "error",
                "file_glob": "*.py",
                "fix_hint": "Remove forbidden",
            }
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(rules_data, f)
            tmp_path = f.name

        enforcer = StandardsEnforcer(rules_path=tmp_path)
        assert len(enforcer.rules()) == 1
        assert enforcer.rules()[0].id == "R001"

    def test_load_rules_mock_yaml(self):
        rules_data = [
            {
                "id": "YAML001",
                "name": "yaml-rule",
                "description": "yaml test",
                "pattern": r"bad_call\(",
                "severity": "warning",
                "file_glob": "*.py",
                "fix_hint": "avoid bad_call",
            }
        ]
        mock_yaml = MagicMock()
        mock_yaml.safe_load.return_value = rules_data

        with patch("lidco.review.standards.yaml", mock_yaml):
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                f.write("dummy yaml content")
                tmp_path = f.name
            enforcer = StandardsEnforcer(rules_path=tmp_path)

        assert len(enforcer.rules()) == 1
        assert enforcer.rules()[0].id == "YAML001"


class TestAddRule:
    def test_add_rule_appends(self):
        enforcer = StandardsEnforcer()
        rule = StandardRule(
            id="X001", name="test", description="desc",
            pattern=r"foo", severity="info", file_glob="*",
        )
        enforcer.add_rule(rule)
        assert len(enforcer.rules()) == 1
        assert enforcer.rules()[0].id == "X001"

    def test_add_rule_does_not_mutate_original(self):
        enforcer = StandardsEnforcer()
        original_rules = enforcer.rules()
        rule = StandardRule(
            id="X002", name="r", description="d",
            pattern=r"x", severity="info", file_glob="*",
        )
        enforcer.add_rule(rule)
        assert len(original_rules) == 0  # original snapshot unchanged


class TestCheckFile:
    def test_check_file_detects_violation(self):
        enforcer = StandardsEnforcer()
        enforcer.add_rule(StandardRule(
            id="P001", name="no-print", description="no print",
            pattern=r"\bprint\s*\(", severity="warning", file_glob="*.py",
        ))
        violations = enforcer.check_file("main.py", "print('hello')\n")
        assert len(violations) == 1
        assert violations[0].rule_id == "P001"
        assert violations[0].severity == "warning"

    def test_check_file_no_match(self):
        enforcer = StandardsEnforcer()
        enforcer.add_rule(StandardRule(
            id="P001", name="no-print", description="no print",
            pattern=r"\bprint\s*\(", severity="warning", file_glob="*.py",
        ))
        violations = enforcer.check_file("main.py", "logging.info('hello')\n")
        assert violations == []

    def test_file_glob_filters_correctly(self):
        enforcer = StandardsEnforcer()
        enforcer.add_rule(StandardRule(
            id="PY001", name="py-only", description="python only rule",
            pattern=r"todo", severity="info", file_glob="*.py",
        ))
        # .js file should not trigger .py-only rule
        violations = enforcer.check_file("app.js", "// todo fix this\n")
        assert violations == []


class TestCheckDiff:
    def test_check_diff_passed_when_clean(self):
        enforcer = StandardsEnforcer()
        enforcer.add_rule(StandardRule(
            id="P001", name="no-print", description="",
            pattern=r"\bprint\s*\(", severity="error", file_glob="*.py",
        ))
        result = enforcer.check_diff({"main.py": "logging.info('hi')\n"})
        assert result.passed is True
        assert result.violations == []

    def test_check_diff_failed_on_error_violation(self):
        enforcer = StandardsEnforcer()
        enforcer.add_rule(StandardRule(
            id="P001", name="no-print", description="",
            pattern=r"\bprint\s*\(", severity="error", file_glob="*.py",
        ))
        result = enforcer.check_diff({"main.py": "print('hello')\n"})
        assert result.passed is False
        assert len(result.violations) == 1


class TestDefaultRules:
    def test_default_rules_returns_5(self):
        rules = StandardsEnforcer.default_rules()
        assert len(rules) == 5

    def test_default_rules_ids_unique(self):
        rules = StandardsEnforcer.default_rules()
        ids = [r.id for r in rules]
        assert len(ids) == len(set(ids))


class TestRulesReturnsCopy:
    def test_rules_returns_copy(self):
        enforcer = StandardsEnforcer()
        enforcer.add_rule(StandardRule(
            id="A", name="a", description="", pattern=r"x", severity="info", file_glob="*",
        ))
        copy1 = enforcer.rules()
        copy1.clear()
        assert len(enforcer.rules()) == 1  # original unaffected


class TestFixHintPropagated:
    def test_fix_hint_in_violation(self):
        enforcer = StandardsEnforcer()
        enforcer.add_rule(StandardRule(
            id="H001", name="hint-rule", description="",
            pattern=r"bad_func\(", severity="warning", file_glob="*.py",
            fix_hint="Replace with good_func()",
        ))
        violations = enforcer.check_file("foo.py", "x = bad_func()\n")
        assert len(violations) == 1
        assert violations[0].fix_hint == "Replace with good_func()"
