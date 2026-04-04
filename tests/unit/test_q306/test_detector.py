"""Tests for PackageDetector."""

import json
import unittest
from pathlib import Path

from lidco.monorepo.detector import MonorepoInfo, Package, PackageDetector


class TestPackageDetector(unittest.TestCase):
    def _make_root(self, tmp: Path) -> Path:
        root = tmp / "repo"
        root.mkdir()
        return root

    def _write_json(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data), encoding="utf-8")

    # -- detect_tool --------------------------------------------------

    def test_detect_tool_nx(self, tmp_path=None):
        tmp = Path(tmp_path) if tmp_path else Path(__file__).parent / "_tmp_nx"
        tmp.mkdir(exist_ok=True)
        root = self._make_root(tmp)
        self._write_json(root / "nx.json", {"projects": {}})
        try:
            d = PackageDetector()
            self.assertEqual(d.detect_tool(str(root)), "nx")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_detect_tool_turbo(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        root = self._make_root(tmp)
        self._write_json(root / "turbo.json", {"pipeline": {}})
        try:
            self.assertEqual(PackageDetector().detect_tool(str(root)), "turbo")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_detect_tool_lerna(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        root = self._make_root(tmp)
        self._write_json(root / "lerna.json", {"version": "independent"})
        try:
            self.assertEqual(PackageDetector().detect_tool(str(root)), "lerna")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_detect_tool_pnpm(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        root = self._make_root(tmp)
        (root / "pnpm-workspace.yaml").write_text("packages:\n  - packages/*\n", encoding="utf-8")
        try:
            self.assertEqual(PackageDetector().detect_tool(str(root)), "pnpm")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_detect_tool_none(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        root = self._make_root(tmp)
        try:
            self.assertIsNone(PackageDetector().detect_tool(str(root)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # -- find_packages ------------------------------------------------

    def test_find_packages_from_workspaces(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        root = self._make_root(tmp)
        self._write_json(root / "package.json", {"workspaces": ["packages/*"]})
        pkg_dir = root / "packages" / "core"
        pkg_dir.mkdir(parents=True)
        self._write_json(pkg_dir / "package.json", {"name": "@repo/core", "version": "1.0.0"})
        try:
            pkgs = PackageDetector().find_packages(str(root))
            self.assertEqual(len(pkgs), 1)
            self.assertEqual(pkgs[0].name, "@repo/core")
            self.assertEqual(pkgs[0].version, "1.0.0")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_find_packages_fallback_globs(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        root = self._make_root(tmp)
        pkg_dir = root / "packages" / "utils"
        pkg_dir.mkdir(parents=True)
        self._write_json(pkg_dir / "package.json", {"name": "utils", "version": "2.0.0"})
        try:
            pkgs = PackageDetector().find_packages(str(root))
            self.assertEqual(len(pkgs), 1)
            self.assertEqual(pkgs[0].name, "utils")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # -- workspace_config ---------------------------------------------

    def test_workspace_config_nx(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        root = self._make_root(tmp)
        self._write_json(root / "nx.json", {"tasksRunnerOptions": {}})
        try:
            cfg = PackageDetector().workspace_config(str(root))
            self.assertIn("tasksRunnerOptions", cfg)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_workspace_config_empty(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        root = self._make_root(tmp)
        try:
            self.assertEqual(PackageDetector().workspace_config(str(root)), {})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # -- detect (full) ------------------------------------------------

    def test_detect_full(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        root = self._make_root(tmp)
        self._write_json(root / "turbo.json", {"pipeline": {}})
        self._write_json(root / "package.json", {"workspaces": ["packages/*"]})
        pkg_dir = root / "packages" / "web"
        pkg_dir.mkdir(parents=True)
        self._write_json(pkg_dir / "package.json", {"name": "web", "version": "0.1.0"})
        try:
            info = PackageDetector().detect(str(root))
            self.assertIsInstance(info, MonorepoInfo)
            self.assertEqual(info.tool, "turbo")
            self.assertEqual(len(info.packages), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # -- Package dataclass --------------------------------------------

    def test_package_dataclass(self):
        p = Package(name="foo", path="/a/b", version="1.2.3", private=True, dependencies=["bar"])
        self.assertEqual(p.name, "foo")
        self.assertEqual(p.version, "1.2.3")
        self.assertTrue(p.private)
        self.assertEqual(p.dependencies, ["bar"])


if __name__ == "__main__":
    unittest.main()
