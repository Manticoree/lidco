"""Tests for PRChecklistGenerator (Q300)."""
import unittest

from lidco.pr.checklist import PRChecklistGenerator, Checklist, CheckItem


class TestPRChecklistGenerator(unittest.TestCase):

    def test_generate_feature(self):
        gen = PRChecklistGenerator()
        cl = gen.generate("feature")
        self.assertEqual(cl.pr_type, "feature")
        self.assertGreater(len(cl.items), 0)

    def test_generate_bugfix(self):
        gen = PRChecklistGenerator()
        cl = gen.generate("bugfix")
        texts = [i.text for i in cl.items]
        self.assertTrue(any("root cause" in t.lower() for t in texts))

    def test_generate_refactor(self):
        gen = PRChecklistGenerator()
        cl = gen.generate("refactor")
        texts = [i.text for i in cl.items]
        self.assertTrue(any("behavior" in t.lower() for t in texts))

    def test_generate_unknown_type_falls_back(self):
        gen = PRChecklistGenerator()
        cl = gen.generate("unknown")
        self.assertGreater(len(cl.items), 0)

    def test_add_check_appears_in_generated(self):
        gen = PRChecklistGenerator()
        gen.add_check("custom", "Custom check item")
        cl = gen.generate("feature")
        texts = [i.text for i in cl.items]
        self.assertIn("Custom check item", texts)

    def test_required_checks_basic(self):
        gen = PRChecklistGenerator()
        checks = gen.required_checks("some diff")
        self.assertIn("Code review completed", checks)
        self.assertIn("Tests pass", checks)

    def test_required_checks_with_tests(self):
        gen = PRChecklistGenerator()
        checks = gen.required_checks("--- a/test_foo.py\n+++ b/test_foo.py")
        self.assertIn("Test changes reviewed", checks)

    def test_required_checks_with_config(self):
        gen = PRChecklistGenerator()
        checks = gen.required_checks("--- a/config.yml\n+++ b/config.yml")
        self.assertIn("Configuration changes validated", checks)

    def test_security_checks_detects_password(self):
        gen = PRChecklistGenerator()
        checks = gen.security_checks("password = get_env()")
        self.assertTrue(any("password" in c for c in checks))

    def test_security_checks_no_issues(self):
        gen = PRChecklistGenerator()
        checks = gen.security_checks("x = 1 + 2")
        self.assertEqual(checks, [])

    def test_deployment_notes_detects_dockerfile(self):
        gen = PRChecklistGenerator()
        notes = gen.deployment_notes("--- a/Dockerfile\n+++ b/Dockerfile")
        self.assertTrue(any("dockerfile" in n.lower() for n in notes))

    def test_deployment_notes_no_deploy(self):
        gen = PRChecklistGenerator()
        notes = gen.deployment_notes("--- a/foo.py\n+++ b/foo.py")
        self.assertEqual(notes, [])

    def test_checklist_as_markdown(self):
        cl = Checklist(pr_type="feature", items=[
            CheckItem(category="code", text="Test item", required=True),
        ])
        md = cl.as_markdown()
        self.assertIn("## feature Checklist", md)
        self.assertIn("- [ ]", md)

    def test_checklist_required_count(self):
        cl = Checklist(pr_type="test", items=[
            CheckItem(category="a", text="req", required=True),
            CheckItem(category="b", text="opt", required=False),
        ])
        self.assertEqual(cl.required_count, 1)


if __name__ == "__main__":
    unittest.main()
