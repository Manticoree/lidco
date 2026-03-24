"""Tests for MigrationAgent — T493."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess
import pytest
from lidco.agents.migration_agent import MigrationAgent, MigrationPlan, MigrationResult, MigrationRule


def make_rule(find="requests\\.get", replace="httpx.get"):
    return MigrationRule(name="r2h", description="requests→httpx", find_pattern=find, replace_template=replace)


class TestMigrationAgent:
    def test_plan_finds_affected_files(self, tmp_path):
        (tmp_path / "a.py").write_text("import requests\nrequests.get('http://x')\n")
        agent = MigrationAgent(project_dir=tmp_path)
        plan = agent.plan(make_rule())
        assert "a.py" in plan.affected_files

    def test_plan_no_matches(self, tmp_path):
        (tmp_path / "b.py").write_text("x = 1\n")
        agent = MigrationAgent(project_dir=tmp_path)
        plan = agent.plan(make_rule())
        assert "b.py" not in plan.affected_files

    def test_plan_preview_contains_new_content(self, tmp_path):
        (tmp_path / "c.py").write_text("requests.get('http://x')\n")
        agent = MigrationAgent(project_dir=tmp_path)
        plan = agent.plan(make_rule())
        assert "c.py" in plan.preview
        assert "httpx.get" in plan.preview["c.py"]

    def test_plan_change_count(self, tmp_path):
        (tmp_path / "d.py").write_text("requests.get('a')\nrequests.get('b')\n")
        agent = MigrationAgent(project_dir=tmp_path)
        plan = agent.plan(make_rule())
        assert plan.change_count == 2

    def test_execute_applies_changes(self, tmp_path):
        f = tmp_path / "e.py"
        f.write_text("requests.get('x')\n")
        agent = MigrationAgent(project_dir=tmp_path)
        plan = agent.plan(make_rule())
        with patch.object(agent, "_run_tests", return_value="5 passed"):
            result = agent.execute(plan)
        assert "e.py" in result.applied_files
        assert "httpx.get" in f.read_text()

    def test_execute_success_when_tests_pass(self, tmp_path):
        (tmp_path / "f.py").write_text("requests.get('x')\n")
        agent = MigrationAgent(project_dir=tmp_path)
        plan = agent.plan(make_rule())
        with patch.object(agent, "_run_tests", return_value="5 passed"):
            result = agent.execute(plan)
        assert result.success

    def test_execute_failure_when_tests_fail(self, tmp_path):
        (tmp_path / "g.py").write_text("requests.get('x')\n")
        agent = MigrationAgent(project_dir=tmp_path)
        plan = agent.plan(make_rule())
        with patch.object(agent, "_run_tests", return_value="1 FAILED"):
            result = agent.execute(plan)
        assert not result.success

    def test_empty_plan_no_changes(self, tmp_path):
        agent = MigrationAgent(project_dir=tmp_path)
        plan = MigrationPlan(rule=make_rule(), affected_files=[], change_count=0, preview={})
        with patch.object(agent, "_run_tests", return_value="ok"):
            result = agent.execute(plan)
        assert result.applied_files == []

    def test_rule_dataclass(self):
        r = MigrationRule(name="test", description="desc", find_pattern="foo", replace_template="bar")
        assert r.file_glob == "**/*.py"
