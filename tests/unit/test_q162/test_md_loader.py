"""Tests for lidco.workflows.md_loader — Q162 Task 924."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from lidco.workflows.md_loader import WorkflowDef, WorkflowLoader


class TestWorkflowDef(unittest.TestCase):
    def test_fields(self) -> None:
        wf = WorkflowDef(name="test", title="Test", description="desc", steps=["a", "b"], source_path="/x.md")
        self.assertEqual(wf.name, "test")
        self.assertEqual(wf.title, "Test")
        self.assertEqual(wf.steps, ["a", "b"])

    def test_frozen(self) -> None:
        wf = WorkflowDef(name="n", title="t", description="", steps=[], source_path="")
        with self.assertRaises(AttributeError):
            wf.name = "other"  # type: ignore[misc]


class TestWorkflowLoader(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._wf_dir = os.path.join(self._tmpdir, "workflows")
        os.makedirs(self._wf_dir)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write(self, name: str, content: str) -> None:
        Path(self._wf_dir, name).write_text(content, encoding="utf-8")

    def test_load_all_empty_dir(self) -> None:
        loader = WorkflowLoader(self._wf_dir)
        self.assertEqual(loader.load_all(), [])

    def test_load_all_missing_dir(self) -> None:
        loader = WorkflowLoader("/nonexistent/path")
        self.assertEqual(loader.load_all(), [])

    def test_load_all_with_files(self) -> None:
        self._write("deploy.md", "---\ntitle: Deploy\ndescription: Deploy stuff\n---\n- Build\n- Ship\n")
        loader = WorkflowLoader(self._wf_dir)
        wfs = loader.load_all()
        self.assertEqual(len(wfs), 1)
        self.assertEqual(wfs[0].name, "deploy")
        self.assertEqual(wfs[0].title, "Deploy")
        self.assertEqual(wfs[0].description, "Deploy stuff")
        self.assertEqual(wfs[0].steps, ["Build", "Ship"])

    def test_load_one_found(self) -> None:
        self._write("ci.md", "- Lint\n- Test\n- Deploy\n")
        loader = WorkflowLoader(self._wf_dir)
        wf = loader.load_one("ci")
        self.assertIsNotNone(wf)
        self.assertEqual(wf.name, "ci")
        self.assertEqual(wf.steps, ["Lint", "Test", "Deploy"])

    def test_load_one_not_found(self) -> None:
        loader = WorkflowLoader(self._wf_dir)
        self.assertIsNone(loader.load_one("nope"))

    def test_frontmatter_parsing(self) -> None:
        content = "---\ntitle: My Workflow\ndescription: Does things\n---\n\n- Step A\n- Step B\n"
        self._write("mine.md", content)
        loader = WorkflowLoader(self._wf_dir)
        wf = loader.load_one("mine")
        self.assertEqual(wf.title, "My Workflow")
        self.assertEqual(wf.description, "Does things")

    def test_ordered_list_steps(self) -> None:
        self._write("ordered.md", "1. First\n2. Second\n3. Third\n")
        loader = WorkflowLoader(self._wf_dir)
        wf = loader.load_one("ordered")
        self.assertEqual(wf.steps, ["First", "Second", "Third"])

    def test_mixed_list_steps(self) -> None:
        self._write("mixed.md", "- Alpha\n1. Beta\n- Gamma\n")
        loader = WorkflowLoader(self._wf_dir)
        wf = loader.load_one("mixed")
        self.assertEqual(wf.steps, ["Alpha", "Beta", "Gamma"])

    def test_no_frontmatter_title_from_stem(self) -> None:
        self._write("my-flow.md", "- Step one\n")
        loader = WorkflowLoader(self._wf_dir)
        wf = loader.load_one("my-flow")
        self.assertEqual(wf.title, "My Flow")

    def test_register_as_commands(self) -> None:
        self._write("test-wf.md", "---\ntitle: Test WF\n---\n- Do stuff\n")
        loader = WorkflowLoader(self._wf_dir)

        registered: dict[str, object] = {}

        class FakeRegistry:
            def register(self, cmd):
                registered[cmd.name] = cmd

        loader.register_as_commands(FakeRegistry())
        self.assertIn("workflow-test-wf", registered)

    def test_register_handler_returns_plan(self) -> None:
        import asyncio
        self._write("abc.md", "---\ntitle: ABC\ndescription: The ABC workflow\n---\n- A\n- B\n- C\n")
        loader = WorkflowLoader(self._wf_dir)

        registered: dict[str, object] = {}

        class FakeRegistry:
            def register(self, cmd):
                registered[cmd.name] = cmd

        loader.register_as_commands(FakeRegistry())
        cmd = registered["workflow-abc"]
        result = asyncio.run(cmd.handler())
        self.assertIn("ABC", result)
        self.assertIn("1. A", result)

    def test_source_path_set(self) -> None:
        self._write("sp.md", "- x\n")
        loader = WorkflowLoader(self._wf_dir)
        wf = loader.load_one("sp")
        self.assertIn("sp.md", wf.source_path)

    def test_non_md_files_ignored(self) -> None:
        self._write("readme.txt", "- Not a workflow\n")
        self._write("real.md", "- Real\n")
        loader = WorkflowLoader(self._wf_dir)
        wfs = loader.load_all()
        self.assertEqual(len(wfs), 1)
        self.assertEqual(wfs[0].name, "real")


if __name__ == "__main__":
    unittest.main()
