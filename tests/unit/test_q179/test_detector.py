"""Tests for WorkspaceDetector."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from lidco.workspace.detector import PackageInfo, WorkspaceDetector, WorkspaceInfo


class TestWorkspaceDetector(unittest.TestCase):
    """Tests for workspace type detection."""

    def setUp(self) -> None:
        self.detector = WorkspaceDetector()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers -------------------------------------------------------------

    def _write(self, rel_path: str, content: str) -> str:
        full = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
        return full

    def _mkdir(self, rel_path: str) -> str:
        full = os.path.join(self.root, rel_path)
        os.makedirs(full, exist_ok=True)
        return full

    # -- NX ------------------------------------------------------------------

    def test_detect_nx(self) -> None:
        self._write("nx.json", "{}")
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "nx")
        self.assertEqual(info.root, os.path.abspath(self.root))

    def test_detect_nx_with_packages(self) -> None:
        self._write("nx.json", "{}")
        self._write("packages/core/package.json", json.dumps({"name": "@app/core"}))
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "nx")
        self.assertEqual(len(info.packages), 1)
        self.assertEqual(info.packages[0].name, "@app/core")

    # -- Turborepo -----------------------------------------------------------

    def test_detect_turborepo(self) -> None:
        self._write("turbo.json", "{}")
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "turborepo")

    def test_detect_turborepo_with_apps(self) -> None:
        self._write("turbo.json", "{}")
        self._write("apps/web/package.json", json.dumps({"name": "web", "dependencies": {"react": "^18"}}))
        info = self.detector.detect(self.root)
        self.assertEqual(len(info.packages), 1)
        self.assertEqual(info.packages[0].name, "web")
        self.assertIn("react", info.packages[0].deps)

    # -- Lerna ---------------------------------------------------------------

    def test_detect_lerna(self) -> None:
        self._write("lerna.json", "{}")
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "lerna")

    # -- Cargo ---------------------------------------------------------------

    def test_detect_cargo(self) -> None:
        self._write("Cargo.toml", '[workspace]\nmembers = [\n  "crate-a",\n  "crate-b"\n]\n')
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "cargo")
        self.assertEqual(len(info.packages), 2)
        names = [p.name for p in info.packages]
        self.assertIn("crate-a", names)
        self.assertIn("crate-b", names)

    def test_detect_cargo_no_workspace_section(self) -> None:
        self._write("Cargo.toml", '[package]\nname = "my-crate"\n')
        info = self.detector.detect(self.root)
        # Should NOT match cargo workspace
        self.assertNotEqual(info.workspace_type, "cargo")

    # -- Go ------------------------------------------------------------------

    def test_detect_go(self) -> None:
        self._write("go.work", "go 1.21\n\nuse (\n    ./svc-a\n    ./svc-b\n)\n")
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "go")
        self.assertEqual(len(info.packages), 2)

    def test_detect_go_single_use(self) -> None:
        self._write("go.work", "go 1.21\n\nuse ./svc-a\n")
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "go")
        self.assertEqual(len(info.packages), 1)
        self.assertEqual(info.packages[0].name, "./svc-a")

    # -- pnpm ----------------------------------------------------------------

    def test_detect_pnpm(self) -> None:
        self._write("pnpm-workspace.yaml", "packages:\n  - 'packages/*'\n")
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "pnpm")

    # -- Yarn workspaces -----------------------------------------------------

    def test_detect_yarn(self) -> None:
        self._write("package.json", json.dumps({"workspaces": ["packages/*"]}))
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "yarn")

    def test_detect_yarn_no_workspaces(self) -> None:
        self._write("package.json", json.dumps({"name": "app"}))
        info = self.detector.detect(self.root)
        # package.json without workspaces → not yarn
        self.assertNotEqual(info.workspace_type, "yarn")

    # -- pip -----------------------------------------------------------------

    def test_detect_pip_pyproject(self) -> None:
        self._write("pyproject.toml", "[project]\nname='mypkg'\n")
        self._mkdir("src/mypkg")
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "pip")
        self.assertTrue(any(p.name == "mypkg" for p in info.packages))

    def test_detect_pip_setup_cfg(self) -> None:
        self._write("setup.cfg", "[metadata]\nname = mypkg\n")
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "pip")

    # -- unknown -------------------------------------------------------------

    def test_detect_unknown(self) -> None:
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "unknown")
        self.assertEqual(info.packages, [])

    # -- priority / precedence -----------------------------------------------

    def test_nx_takes_priority_over_yarn(self) -> None:
        self._write("nx.json", "{}")
        self._write("package.json", json.dumps({"workspaces": ["packages/*"]}))
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "nx")

    def test_turborepo_takes_priority_over_pnpm(self) -> None:
        self._write("turbo.json", "{}")
        self._write("pnpm-workspace.yaml", "packages:\n  - 'packages/*'\n")
        info = self.detector.detect(self.root)
        self.assertEqual(info.workspace_type, "turborepo")

    # -- dataclasses ---------------------------------------------------------

    def test_package_info_defaults(self) -> None:
        p = PackageInfo(name="x", path="/x")
        self.assertEqual(p.deps, [])

    def test_workspace_info_fields(self) -> None:
        info = WorkspaceInfo(workspace_type="nx", packages=[], root="/ws")
        self.assertEqual(info.workspace_type, "nx")
        self.assertEqual(info.root, "/ws")

    def test_nested_packages(self) -> None:
        """Multiple packages in packages/ dir."""
        self._write("nx.json", "{}")
        self._write("packages/a/package.json", json.dumps({"name": "a"}))
        self._write("packages/b/package.json", json.dumps({"name": "b"}))
        info = self.detector.detect(self.root)
        names = sorted(p.name for p in info.packages)
        self.assertEqual(names, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
