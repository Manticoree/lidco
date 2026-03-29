"""Tests for BugBotFixAgent (Task 698)."""
import unittest
from unittest.mock import MagicMock

from lidco.review.bugbot_pr_trigger import BugBotFinding, BugSeverity
from lidco.review.bugbot_fix_agent import BugBotFixAgent, BugBotFixProposal


def _finding(rule_id: str = "bare_except", severity: BugSeverity = BugSeverity.MEDIUM,
             file: str = "test.py", line: int = 5, message: str = "issue") -> BugBotFinding:
    return BugBotFinding(file=file, line=line, severity=severity, message=message, rule_id=rule_id)


class TestBugBotFixProposal(unittest.TestCase):
    def test_creation(self):
        f = _finding()
        p = BugBotFixProposal(finding=f, patch="diff", rationale="reason", confidence=0.8)
        self.assertEqual(p.patch, "diff")
        self.assertEqual(p.confidence, 0.8)

    def test_empty_patch(self):
        p = BugBotFixProposal(finding=_finding(), patch="", rationale="none", confidence=0.0)
        self.assertEqual(p.patch, "")


class TestRuleBasedFixes(unittest.TestCase):
    def setUp(self):
        self.agent = BugBotFixAgent()

    def test_bare_except_fix(self):
        source = "try:\n    x()\nexcept:\n    pass\n"
        finding = _finding("bare_except", line=3)
        proposal = self.agent.generate_fix(finding, source)
        self.assertIn("except Exception:", proposal.patch)
        self.assertGreater(proposal.confidence, 0.5)

    def test_bare_except_fix_preserves_indentation(self):
        source = "try:\n    x()\n    except:\n        pass\n"
        finding = _finding("bare_except", line=3)
        proposal = self.agent.generate_fix(finding, source)
        self.assertIn("except Exception:", proposal.patch)

    def test_bare_except_fix_out_of_bounds(self):
        finding = _finding("bare_except", line=100)
        proposal = self.agent.generate_fix(finding, "x = 1")
        self.assertIn("except", proposal.patch)
        self.assertGreater(proposal.confidence, 0.5)

    def test_eval_fix(self):
        finding = _finding("eval_usage", severity=BugSeverity.HIGH)
        proposal = self.agent.generate_fix(finding, "eval(expr)")
        self.assertIn("eval", proposal.patch.lower())
        self.assertGreater(proposal.confidence, 0.3)

    def test_hardcoded_secret_fix(self):
        finding = _finding("hardcoded_secret", severity=BugSeverity.CRITICAL)
        proposal = self.agent.generate_fix(finding, 'password = "p"')
        self.assertIn("env", proposal.patch.lower())
        self.assertGreater(proposal.confidence, 0.5)

    def test_todo_no_fix(self):
        finding = _finding("todo_fixme", severity=BugSeverity.LOW)
        proposal = self.agent.generate_fix(finding, "# TODO fix this")
        self.assertEqual(proposal.patch, "")
        self.assertEqual(proposal.confidence, 0.0)

    def test_unknown_rule_no_fix(self):
        finding = _finding("some_unknown_rule")
        proposal = self.agent.generate_fix(finding, "x = 1")
        self.assertEqual(proposal.patch, "")
        self.assertEqual(proposal.confidence, 0.0)

    def test_rationale_is_set(self):
        finding = _finding("bare_except")
        proposal = self.agent.generate_fix(finding, "except:\n    pass")
        self.assertTrue(len(proposal.rationale) > 0)

    def test_eval_rationale_mentions_safe(self):
        finding = _finding("eval_usage")
        proposal = self.agent.generate_fix(finding, "eval(x)")
        self.assertIn("eval", proposal.rationale.lower())


class TestGenerateFixes(unittest.TestCase):
    def setUp(self):
        self.agent = BugBotFixAgent()

    def test_empty_findings(self):
        result = self.agent.generate_fixes([], {})
        self.assertEqual(result, [])

    def test_multiple_findings(self):
        findings = [
            _finding("bare_except", file="a.py", line=3),
            _finding("eval_usage", file="b.py", line=7),
        ]
        source_map = {
            "a.py": "try:\n    x()\nexcept:\n    pass\n",
            "b.py": "eval(x)",
        }
        result = self.agent.generate_fixes(findings, source_map)
        self.assertEqual(len(result), 2)

    def test_missing_source_map_entry(self):
        findings = [_finding("bare_except", file="missing.py")]
        result = self.agent.generate_fixes(findings, {})
        self.assertEqual(len(result), 1)
        # Should still produce a proposal with empty source
        self.assertIsInstance(result[0], BugBotFixProposal)

    def test_returns_proposals_for_all(self):
        findings = [
            _finding("todo_fixme"),
            _finding("bare_except"),
            _finding("hardcoded_secret"),
        ]
        result = self.agent.generate_fixes(findings, {"test.py": ""})
        self.assertEqual(len(result), 3)


class TestLLMBasedFixes(unittest.TestCase):
    def test_llm_fix_called(self):
        llm_fn = MagicMock(return_value="fixed code\n---\nLLM rationale")
        agent = BugBotFixAgent(llm_fn=llm_fn)
        finding = _finding("bare_except")
        proposal = agent.generate_fix(finding, "except:\n    pass")
        llm_fn.assert_called_once()
        self.assertEqual(proposal.patch, "fixed code")
        self.assertEqual(proposal.rationale, "LLM rationale")

    def test_llm_fix_no_separator(self):
        llm_fn = MagicMock(return_value="just a patch")
        agent = BugBotFixAgent(llm_fn=llm_fn)
        proposal = agent.generate_fix(_finding(), "code")
        self.assertEqual(proposal.patch, "just a patch")
        self.assertEqual(proposal.rationale, "LLM-generated fix")

    def test_llm_fix_confidence(self):
        llm_fn = MagicMock(return_value="patch---reason")
        agent = BugBotFixAgent(llm_fn=llm_fn)
        proposal = agent.generate_fix(_finding(), "code")
        self.assertEqual(proposal.confidence, 0.8)

    def test_llm_fix_exception_graceful(self):
        llm_fn = MagicMock(side_effect=RuntimeError("LLM down"))
        agent = BugBotFixAgent(llm_fn=llm_fn)
        proposal = agent.generate_fix(_finding(), "code")
        self.assertEqual(proposal.patch, "")
        self.assertEqual(proposal.confidence, 0.0)
        self.assertIn("LLM fix failed", proposal.rationale)

    def test_llm_prompt_includes_file(self):
        llm_fn = MagicMock(return_value="p---r")
        agent = BugBotFixAgent(llm_fn=llm_fn)
        finding = _finding(file="myfile.py")
        agent.generate_fix(finding, "source")
        prompt = llm_fn.call_args[0][0]
        self.assertIn("myfile.py", prompt)

    def test_llm_prompt_includes_severity(self):
        llm_fn = MagicMock(return_value="p---r")
        agent = BugBotFixAgent(llm_fn=llm_fn)
        finding = _finding(severity=BugSeverity.CRITICAL)
        agent.generate_fix(finding, "source")
        prompt = llm_fn.call_args[0][0]
        self.assertIn("critical", prompt)

    def test_llm_prompt_includes_source(self):
        llm_fn = MagicMock(return_value="p---r")
        agent = BugBotFixAgent(llm_fn=llm_fn)
        agent.generate_fix(_finding(), "my_source_code_here")
        prompt = llm_fn.call_args[0][0]
        self.assertIn("my_source_code_here", prompt)

    def test_llm_overrides_rule_fix(self):
        """When LLM is provided, rule-based fix is NOT used."""
        llm_fn = MagicMock(return_value="llm_patch---llm_reason")
        agent = BugBotFixAgent(llm_fn=llm_fn)
        proposal = agent.generate_fix(_finding("bare_except"), "except:\n    pass")
        self.assertEqual(proposal.patch, "llm_patch")


class TestEdgeCases(unittest.TestCase):
    def test_empty_source(self):
        agent = BugBotFixAgent()
        proposal = agent.generate_fix(_finding("bare_except", line=1), "")
        self.assertIsInstance(proposal, BugBotFixProposal)

    def test_finding_is_preserved_in_proposal(self):
        agent = BugBotFixAgent()
        f = _finding("eval_usage", file="z.py", line=99)
        proposal = agent.generate_fix(f, "eval(x)")
        self.assertIs(proposal.finding, f)
        self.assertEqual(proposal.finding.file, "z.py")
        self.assertEqual(proposal.finding.line, 99)


if __name__ == "__main__":
    unittest.main()
