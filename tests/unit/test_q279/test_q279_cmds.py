"""Tests for Q279 CLI commands."""
import asyncio
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands import q279_cmds


class TestQ279Commands(unittest.TestCase):

    def setUp(self):
        self.registry = MagicMock()
        q279_cmds._state.clear()
        q279_cmds.register(self.registry)
        self.calls = {c.args[0].name: c.args[0] for c in self.registry.register.call_args_list}

    def _run(self, name, args=""):
        return asyncio.run(self.calls[name].handler(args))

    def test_debate_start(self):
        result = self._run("debate", "start Use microservices?")
        self.assertIn("Debate created", result)

    def test_debate_status_no_active(self):
        result = self._run("debate", "status")
        self.assertIn("No active debate", result)

    def test_debate_add_participant(self):
        self._run("debate", "start Topic")
        result = self._run("debate", "add agent1 proposition")
        self.assertIn("Added agent1", result)

    def test_personas_list(self):
        result = self._run("personas", "list")
        self.assertIn("optimist", result)

    def test_personas_show(self):
        result = self._run("personas", "show optimist")
        self.assertIn("optimist", result)

    def test_evaluate_args_empty(self):
        result = self._run("evaluate-args", "")
        self.assertIn("No evaluations", result)

    def test_evaluate_args_score(self):
        result = self._run("evaluate-args", "agent1 | This is a solid argument because reasons")
        self.assertIn("Score for agent1", result)

    def test_consensus_vote(self):
        result = self._run("consensus", "vote agent1 approve")
        self.assertIn("Vote recorded", result)

    def test_consensus_build(self):
        self._run("consensus", "vote a approve")
        result = self._run("consensus", "build")
        self.assertIn("Decision", result)

    def test_consensus_status(self):
        result = self._run("consensus", "status")
        self.assertIn("votes", result)


if __name__ == "__main__":
    unittest.main()
