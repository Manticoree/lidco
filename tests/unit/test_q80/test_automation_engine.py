"""Tests for AutomationEngine (T523)."""
from pathlib import Path

import pytest

from lidco.scheduler.automation_engine import AutomationEngine, AutomationRule, AutomationResult


def _rule(name, trigger_type="webhook", template="task: {event.title}", enabled=True):
    return AutomationRule(
        name=name,
        trigger_type=trigger_type,
        trigger_config={},
        task_template=template,
        output_type="log",
        enabled=enabled,
    )


@pytest.fixture
def engine(tmp_path):
    return AutomationEngine(rules_path=tmp_path / "automations.yaml")


@pytest.fixture
def engine_with_agent(tmp_path):
    def agent_fn(task):
        return f"done: {task[:30]}"
    return AutomationEngine(rules_path=tmp_path / "automations.yaml", agent_fn=agent_fn)


# ---- load_rules ----

def test_load_rules_no_file_returns_empty(engine):
    rules = engine.load_rules()
    assert rules == []


def test_load_rules_from_yaml(tmp_path):
    yaml_content = """rules:
  - name: my-rule
    trigger_type: github_issue
    task_template: "fix issue {event.number}"
    output_type: pr
    enabled: true
"""
    p = tmp_path / "automations.yaml"
    p.write_text(yaml_content, encoding="utf-8")
    engine = AutomationEngine(rules_path=p)
    rules = engine.load_rules()
    # If yaml not available, falls back to JSON parse (will fail) → empty
    # If yaml is available, should parse correctly
    try:
        import yaml
        assert len(rules) == 1
        assert rules[0].name == "my-rule"
        assert rules[0].trigger_type == "github_issue"
    except ImportError:
        pass  # yaml not installed, skip


def test_load_rules_invalid_file_returns_empty(tmp_path):
    p = tmp_path / "automations.yaml"
    p.write_text("[[[[not valid yaml or json", encoding="utf-8")
    engine = AutomationEngine(rules_path=p)
    assert engine.load_rules() == []


# ---- add_rule ----

def test_add_rule_appends(engine):
    engine.add_rule(_rule("r1"))
    engine.add_rule(_rule("r2"))
    assert len(engine.rules) == 2


def test_add_rule_is_immutable(engine):
    engine.add_rule(_rule("r1"))
    old_rules = engine.rules
    engine.add_rule(_rule("r2"))
    assert len(old_rules) == 1  # old snapshot unaffected


# ---- evaluate ----

def test_evaluate_matches_by_type(engine):
    engine.add_rule(_rule("issue-rule", trigger_type="github_issue"))
    engine.add_rule(_rule("pr-rule", trigger_type="github_pr"))
    matches = engine.evaluate({"type": "github_issue"})
    names = [r.name for r in matches]
    assert "issue-rule" in names
    assert "pr-rule" not in names


def test_evaluate_webhook_matches_all_events(engine):
    engine.add_rule(_rule("any", trigger_type="webhook"))
    matches = engine.evaluate({"type": "github_issue"})
    assert len(matches) == 1


def test_evaluate_disabled_rule_excluded(engine):
    engine.add_rule(_rule("off", trigger_type="webhook", enabled=False))
    matches = engine.evaluate({"type": "any"})
    assert matches == []


# ---- run_rule ----

def test_run_rule_no_agent_returns_no_agent_msg(engine):
    rule = _rule("r", template="do {event.title}")
    result = engine.run_rule(rule, {"title": "fix bug"})
    assert isinstance(result, AutomationResult)
    assert result.success is True
    assert "no agent" in result.output


def test_run_rule_renders_template(engine_with_agent):
    rule = _rule("r", template="fix {event.title} issue #{event.number}")
    result = engine_with_agent.run_rule(rule, {"title": "login", "number": "42"})
    assert result.success is True
    assert "login" in result.task
    assert "42" in result.task


def test_run_rule_agent_exception(tmp_path):
    def bad_agent(task):
        raise RuntimeError("agent down")
    engine = AutomationEngine(rules_path=tmp_path / "a.yaml", agent_fn=bad_agent)
    rule = _rule("r")
    result = engine.run_rule(rule, {})
    assert result.success is False
    assert "agent down" in result.error


# ---- tick ----

def test_tick_runs_cron_rules(engine_with_agent):
    engine_with_agent.add_rule(_rule("cron-job", trigger_type="cron"))
    engine_with_agent.add_rule(_rule("webhook-job", trigger_type="webhook"))
    results = engine_with_agent.tick()
    assert len(results) == 1
    assert results[0].rule_name == "cron-job"


def test_tick_empty_returns_empty(engine):
    assert engine.tick() == []
