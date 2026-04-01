"""Tests for Q181 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q181_cmds as q181_mod
from lidco.templates.approval_gate import ApprovalGate, ApprovalManager
from lidco.templates.conversation import ConversationTemplate, ConversationTurn
from lidco.templates.recipe_engine import Recipe, RecipeEngine, RecipeStep
from lidco.templates.team_registry import TeamTemplateRegistry


def _setup_cmd_registry():
    """Create a minimal CommandRegistry and register Q181 commands."""
    q181_mod._state.clear()
    from lidco.cli.commands.registry import CommandRegistry
    cr = CommandRegistry.__new__(CommandRegistry)
    cr._commands = {}
    cr._session = None
    q181_mod.register(cr)
    return cr


class TestTemplateCmds(unittest.TestCase):
    def setUp(self):
        cr = _setup_cmd_registry()
        self.handler = cr._commands["template"].handler
        # Inject a template into module state
        tmpl = ConversationTemplate(
            name="greet",
            description="A greeting",
            turns=(ConversationTurn(role="user", content="Hi"),),
            version="1.0",
        )
        q181_mod._state["templates"] = {"greet": tmpl}

    def test_list(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("greet", result)
        self.assertIn("1 template(s)", result)

    def test_show(self):
        result = asyncio.run(self.handler("show greet"))
        self.assertIn("name: greet", result)

    def test_render(self):
        result = asyncio.run(self.handler("render greet"))
        self.assertIn("Hi", result)

    def test_help(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


class TestRecipeCmds(unittest.TestCase):
    def setUp(self):
        cr = _setup_cmd_registry()
        self.handler = cr._commands["recipe"].handler
        engine = RecipeEngine()
        engine.register(Recipe(
            name="build",
            description="Build pipeline",
            steps=(RecipeStep(name="compile", template_name="t"),),
        ))
        q181_mod._state["engine"] = engine

    def test_list(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("build", result)
        self.assertIn("1 recipe(s)", result)

    def test_run(self):
        result = asyncio.run(self.handler("run build"))
        self.assertIn("finished", result)
        self.assertIn("completed", result)

    def test_status(self):
        asyncio.run(self.handler("run build"))
        result = asyncio.run(self.handler("status build"))
        self.assertIn("completed", result)

    def test_help(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


class TestTeamTemplatesCmds(unittest.TestCase):
    def setUp(self):
        cr = _setup_cmd_registry()
        self.handler = cr._commands["team-templates"].handler
        reg = TeamTemplateRegistry()
        reg.add("starter", {"x": 1}, version="1.0", author="dev")
        q181_mod._state["team_registry"] = reg

    def test_list(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("starter", result)
        self.assertIn("1 team template(s)", result)

    def test_search(self):
        result = asyncio.run(self.handler("search starter"))
        self.assertIn("starter", result)

    def test_info(self):
        result = asyncio.run(self.handler("info starter"))
        self.assertIn("Name: starter", result)

    def test_help(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


class TestApproveCmds(unittest.TestCase):
    def setUp(self):
        cr = _setup_cmd_registry()
        self.handler = cr._commands["approve"].handler
        mgr = ApprovalManager()
        mgr.add_gate(ApprovalGate(name="deploy"))
        mgr.request_approval("deploy", "alice")
        q181_mod._state["approval"] = mgr

    def test_list_pending(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("1 pending", result)
        self.assertIn("alice", result)

    def test_approve(self):
        result = asyncio.run(self.handler("approve 1 looks good"))
        self.assertIn("Approved", result)

    def test_reject(self):
        result = asyncio.run(self.handler("reject 1 not ready"))
        self.assertIn("Rejected", result)

    def test_audit(self):
        asyncio.run(self.handler("approve 1 ok"))
        result = asyncio.run(self.handler("audit"))
        self.assertIn("1 audit entries", result)

    def test_help(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
