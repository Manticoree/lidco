"""Tests for src/lidco/code_actions/registry.py."""
import pytest

from lidco.code_actions.registry import (
    ActionMatch,
    CodeAction,
    CodeActionError,
    CodeActionsRegistry,
)


class TestCodeAction:
    def test_matches_pattern(self):
        action = CodeAction(id="a", title="t", pattern=r"NameError")
        assert action.matches("NameError: something") is not None

    def test_no_match(self):
        action = CodeAction(id="a", title="t", pattern=r"TypeError")
        assert action.matches("NameError: foo") is None

    def test_empty_pattern_never_matches(self):
        action = CodeAction(id="a", title="t", pattern="")
        assert action.matches("anything") is None

    def test_apply_fix_with_match(self):
        action = CodeAction(
            id="a", title="t",
            pattern=r"name '(\w+)' is not defined",
            fix_template="Import {match}",
        )
        m = action.matches("NameError: name 'requests' is not defined")
        fix = action.apply_fix(m)
        assert "requests" in fix

    def test_apply_fix_no_template(self):
        action = CodeAction(id="a", title="My Title", description="My desc")
        fix = action.apply_fix()
        assert "My desc" in fix or "My Title" in fix

    def test_apply_fix_no_match(self):
        action = CodeAction(id="a", title="t", fix_template="Fix: {match}")
        fix = action.apply_fix(None)
        assert "Fix:" in fix

    def test_tags(self):
        action = CodeAction(id="a", title="t", tags=["python", "import"])
        assert "python" in action.tags

    def test_severity_default(self):
        action = CodeAction(id="a", title="t")
        assert action.severity == "warning"


class TestCodeActionsRegistry:
    def test_register_and_get(self):
        reg = CodeActionsRegistry()
        action = CodeAction(id="foo", title="Foo")
        reg.register(action)
        assert reg.get("foo") is action

    def test_register_empty_id_raises(self):
        reg = CodeActionsRegistry()
        with pytest.raises(CodeActionError):
            reg.register(CodeAction(id="", title="t"))

    def test_len(self):
        reg = CodeActionsRegistry()
        reg.register(CodeAction(id="a", title="A"))
        reg.register(CodeAction(id="b", title="B"))
        assert len(reg) == 2

    def test_unregister_existing(self):
        reg = CodeActionsRegistry()
        reg.register(CodeAction(id="a", title="A"))
        assert reg.unregister("a") is True
        assert reg.get("a") is None

    def test_unregister_nonexistent(self):
        reg = CodeActionsRegistry()
        assert reg.unregister("ghost") is False

    def test_list_actions_all(self):
        reg = CodeActionsRegistry()
        reg.register(CodeAction(id="b", title="B", severity="error"))
        reg.register(CodeAction(id="a", title="A", severity="warning"))
        actions = reg.list_actions()
        assert len(actions) == 2
        assert actions[0].id == "a"  # sorted by id

    def test_list_actions_by_severity(self):
        reg = CodeActionsRegistry()
        reg.register(CodeAction(id="e", title="E", severity="error"))
        reg.register(CodeAction(id="w", title="W", severity="warning"))
        errors = reg.list_actions(severity="error")
        assert all(a.severity == "error" for a in errors)

    def test_find_actions_match(self):
        reg = CodeActionsRegistry()
        reg.register(CodeAction(id="ne", title="Name Error", pattern=r"NameError"))
        matches = reg.find_actions("NameError: name 'foo' is not defined")
        assert len(matches) == 1
        assert matches[0].id == "ne"

    def test_find_actions_no_match(self):
        reg = CodeActionsRegistry()
        reg.register(CodeAction(id="ne", title="t", pattern=r"NameError"))
        matches = reg.find_actions("ValueError: bad value")
        assert matches == []

    def test_find_actions_by_tag(self):
        reg = CodeActionsRegistry()
        reg.register(CodeAction(id="a", title="A", pattern=r"x", tags=["python"]))
        reg.register(CodeAction(id="b", title="B", pattern=r"x", tags=["js"]))
        matches = reg.find_actions("x", tags=["python"])
        assert all("python" in m.action.tags for m in matches)

    def test_find_by_tag(self):
        reg = CodeActionsRegistry()
        reg.register(CodeAction(id="a", title="A", tags=["security"]))
        reg.register(CodeAction(id="b", title="B", tags=["style"]))
        security = reg.find_by_tag("security")
        assert len(security) == 1
        assert security[0].id == "a"

    def test_action_match_properties(self):
        action = CodeAction(id="x", title="X", pattern=r"error", fix_template="Fix it")
        m = action.matches("some error here")
        match = ActionMatch(action=action, matched_text="error", fix="Fix it")
        assert match.id == "x"
        assert match.title == "X"

    def test_with_defaults_has_actions(self):
        reg = CodeActionsRegistry.with_defaults()
        assert len(reg) > 0

    def test_with_defaults_name_error(self):
        reg = CodeActionsRegistry.with_defaults()
        matches = reg.find_actions("NameError: name 'os' is not defined")
        assert any(m.id == "undefined-name" for m in matches)

    def test_with_defaults_none_type_error(self):
        reg = CodeActionsRegistry.with_defaults()
        matches = reg.find_actions("TypeError: 'NoneType' object is not subscriptable")
        assert any("none" in m.id.lower() for m in matches)

    def test_with_defaults_console_log(self):
        reg = CodeActionsRegistry.with_defaults()
        matches = reg.find_actions("console.log('debug')")
        assert any(m.id == "console-log" for m in matches)

    def test_analyze_groups_by_severity(self):
        reg = CodeActionsRegistry.with_defaults()
        grouped = reg.analyze("NameError: name 'foo' is not defined")
        assert "error" in grouped

    def test_analyze_empty_text_no_matches(self):
        reg = CodeActionsRegistry()
        reg.register(CodeAction(id="a", title="A", pattern=r"\w+"))
        grouped = reg.analyze("")
        # pattern won't match empty string
        assert len(grouped) == 0 or all(len(v) == 0 for v in grouped.values())
