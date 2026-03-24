"""Tests for ArchitectEditorRouter — T451."""
from __future__ import annotations

import pytest

from lidco.llm.architect_editor import ArchitectEditorConfig, ArchitectEditorRouter, TokenUsage


class TestArchitectEditorRouter:
    def test_default_model_when_no_split(self):
        router = ArchitectEditorRouter()
        assert router.get_model("planner") == "openai/glm-4.7"
        assert router.get_model("executor") == "openai/glm-4.7"

    def test_architect_role_uses_architect_model(self):
        cfg = ArchitectEditorConfig(architect_model="claude-opus", editor_model="claude-haiku")
        router = ArchitectEditorRouter(cfg)
        assert router.get_model("planner") == "claude-opus"
        assert router.get_model("critique") == "claude-opus"
        assert router.get_model("review") == "claude-opus"

    def test_editor_role_uses_editor_model(self):
        cfg = ArchitectEditorConfig(architect_model="claude-opus", editor_model="claude-haiku")
        router = ArchitectEditorRouter(cfg)
        assert router.get_model("executor") == "claude-haiku"
        assert router.get_model("code_gen") == "claude-haiku"

    def test_unknown_role_falls_back_to_default(self):
        cfg = ArchitectEditorConfig(architect_model="claude-opus", editor_model="claude-haiku", default_model="gpt-4")
        router = ArchitectEditorRouter(cfg)
        assert router.get_model("unknown_role") == "gpt-4"

    def test_set_architect_model(self):
        router = ArchitectEditorRouter()
        router.set_architect_model("claude-opus")
        assert router.get_model("planner") == "claude-opus"

    def test_set_editor_model(self):
        router = ArchitectEditorRouter()
        router.set_editor_model("claude-haiku")
        assert router.get_model("code_gen") == "claude-haiku"

    def test_record_usage_architect(self):
        router = ArchitectEditorRouter()
        router.record_usage("planner", 500)
        router.record_usage("critique", 300)
        assert router.usage.architect_tokens == 800
        assert router.usage.editor_tokens == 0

    def test_record_usage_editor(self):
        router = ArchitectEditorRouter()
        router.record_usage("executor", 1000)
        assert router.usage.editor_tokens == 1000
        assert router.usage.architect_tokens == 0

    def test_usage_total(self):
        router = ArchitectEditorRouter()
        router.record_usage("planner", 500)
        router.record_usage("executor", 700)
        assert router.usage.total == 1200

    def test_summary(self):
        cfg = ArchitectEditorConfig(architect_model="opus", editor_model="haiku")
        router = ArchitectEditorRouter(cfg)
        router.record_usage("planner", 100)
        s = router.summary()
        assert s["architect_model"] == "opus"
        assert s["editor_model"] == "haiku"
        assert s["architect_tokens"] == 100

    def test_no_architect_model_falls_back(self):
        cfg = ArchitectEditorConfig(editor_model="haiku", default_model="gpt4")
        router = ArchitectEditorRouter(cfg)
        # planner has no architect_model → falls to default
        assert router.get_model("planner") == "gpt4"

    def test_token_usage_dataclass(self):
        usage = TokenUsage()
        usage.add("planner", 200)
        usage.add("executor", 400)
        assert usage.architect_tokens == 200
        assert usage.editor_tokens == 400
        assert usage.total == 600
