"""Tests for src/lidco/onboard/contrib.py — ContributionGuideGenerator."""

from __future__ import annotations

import unittest

from lidco.onboard.contrib import (
    ContributionGuide,
    ContributionGuideGenerator,
    Convention,
    PRTemplate,
    Pitfall,
    WorkflowStep,
)


class TestWorkflowStep(unittest.TestCase):
    def test_defaults(self) -> None:
        s = WorkflowStep(name="fork", description="Fork repo")
        self.assertEqual(s.command, "")
        self.assertEqual(s.order, 0)

    def test_frozen(self) -> None:
        s = WorkflowStep(name="a", description="b")
        with self.assertRaises(AttributeError):
            s.name = "x"  # type: ignore[misc]


class TestConvention(unittest.TestCase):
    def test_defaults(self) -> None:
        c = Convention(name="lint", description="Run linter")
        self.assertEqual(c.example, "")
        self.assertEqual(c.category, "general")


class TestPitfall(unittest.TestCase):
    def test_defaults(self) -> None:
        p = Pitfall(name="big PR", description="Too large")
        self.assertEqual(p.fix, "")
        self.assertEqual(p.severity, "medium")


class TestPRTemplate(unittest.TestCase):
    def test_defaults(self) -> None:
        t = PRTemplate(title_format="type: desc", body_template="## Summary")
        self.assertEqual(t.labels, [])
        self.assertEqual(t.checklist, [])


class TestContributionGuide(unittest.TestCase):
    def test_render_empty(self) -> None:
        g = ContributionGuide(project_name="test")
        text = g.render()
        self.assertIn("# Contributing to test", text)

    def test_render_full(self) -> None:
        g = ContributionGuide(
            project_name="myapp",
            workflow=[
                WorkflowStep(name="Fork", description="Fork it", order=1),
                WorkflowStep(name="Code", description="Write code", command="vim", order=2),
            ],
            conventions=[
                Convention(name="Lint", description="Run lint", example="npm run lint", category="code"),
            ],
            testing_instructions="Run pytest",
            pr_template=PRTemplate(
                title_format="type: desc",
                body_template="## Summary",
                labels=["review"],
                checklist=["Tests", "Docs"],
            ),
            pitfalls=[
                Pitfall(name="Big PR", description="Too big", fix="Split", severity="high"),
            ],
        )
        text = g.render()
        self.assertIn("# Contributing to myapp", text)
        self.assertIn("## Workflow", text)
        self.assertIn("Fork", text)
        self.assertIn("`vim`", text)
        self.assertIn("## Conventions", text)
        self.assertIn("Lint", text)
        self.assertIn("`npm run lint`", text)
        self.assertIn("## Testing", text)
        self.assertIn("Run pytest", text)
        self.assertIn("## Pull Request Process", text)
        self.assertIn("review", text)
        self.assertIn("- [ ] Tests", text)
        self.assertIn("## Common Pitfalls", text)
        self.assertIn("Big PR", text)
        self.assertIn("[high]", text)


class TestContributionGuideGenerator(unittest.TestCase):
    def test_project_name(self) -> None:
        g = ContributionGuideGenerator(project_name="lidco")
        self.assertEqual(g.project_name, "lidco")

    def test_add_workflow_step(self) -> None:
        g = ContributionGuideGenerator()
        g.add_workflow_step(WorkflowStep(name="fork", description="Fork"))
        guide = g.generate()
        self.assertEqual(len(guide.workflow), 1)

    def test_add_workflow_steps(self) -> None:
        g = ContributionGuideGenerator()
        g.add_workflow_steps([
            WorkflowStep(name="a", description="A"),
            WorkflowStep(name="b", description="B"),
        ])
        guide = g.generate()
        self.assertEqual(len(guide.workflow), 2)

    def test_add_convention(self) -> None:
        g = ContributionGuideGenerator()
        g.add_convention(Convention(name="lint", description="Lint"))
        guide = g.generate()
        self.assertEqual(len(guide.conventions), 1)

    def test_add_conventions(self) -> None:
        g = ContributionGuideGenerator()
        g.add_conventions([Convention(name="a", description="A"), Convention(name="b", description="B")])
        guide = g.generate()
        self.assertEqual(len(guide.conventions), 2)

    def test_add_pitfall(self) -> None:
        g = ContributionGuideGenerator()
        g.add_pitfall(Pitfall(name="p", description="P"))
        guide = g.generate()
        self.assertEqual(len(guide.pitfalls), 1)

    def test_add_pitfalls(self) -> None:
        g = ContributionGuideGenerator()
        g.add_pitfalls([Pitfall(name="a", description="A"), Pitfall(name="b", description="B")])
        guide = g.generate()
        self.assertEqual(len(guide.pitfalls), 2)

    def test_set_testing_instructions(self) -> None:
        g = ContributionGuideGenerator()
        g.set_testing_instructions("pytest -q")
        guide = g.generate()
        self.assertEqual(guide.testing_instructions, "pytest -q")

    def test_set_pr_template(self) -> None:
        g = ContributionGuideGenerator()
        t = PRTemplate(title_format="f", body_template="b")
        g.set_pr_template(t)
        guide = g.generate()
        self.assertIsNotNone(guide.pr_template)
        self.assertEqual(guide.pr_template.title_format, "f")

    def test_generate_empty(self) -> None:
        g = ContributionGuideGenerator(project_name="test")
        guide = g.generate()
        self.assertEqual(guide.project_name, "test")
        self.assertEqual(guide.workflow, [])

    def test_generate_default(self) -> None:
        g = ContributionGuideGenerator(project_name="lidco")
        guide = g.generate_default()
        self.assertEqual(guide.project_name, "lidco")
        self.assertGreater(len(guide.workflow), 0)
        self.assertGreater(len(guide.conventions), 0)
        self.assertGreater(len(guide.pitfalls), 0)
        self.assertIsNotNone(guide.pr_template)
        self.assertTrue(len(guide.testing_instructions) > 0)
        text = guide.render()
        self.assertIn("# Contributing to lidco", text)

    def test_summary(self) -> None:
        g = ContributionGuideGenerator(project_name="lidco")
        g.add_workflow_step(WorkflowStep(name="a", description="A"))
        g.add_convention(Convention(name="b", description="B"))
        s = g.summary()
        self.assertIn("lidco", s)
        self.assertIn("Workflow steps: 1", s)
        self.assertIn("Conventions: 1", s)


if __name__ == "__main__":
    unittest.main()
