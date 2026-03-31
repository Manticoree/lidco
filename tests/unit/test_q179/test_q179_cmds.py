"""Tests for Q179 CLI commands."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from lidco.cli.commands.registry import CommandRegistry


class TestQ179Commands(unittest.TestCase):
    """Tests for /workspace, /search-all, /cross-deps, /shared-config."""

    def setUp(self) -> None:
        self.registry = CommandRegistry()

    def test_workspace_registered(self) -> None:
        cmd = self.registry.get("workspace")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "workspace")

    def test_search_all_registered(self) -> None:
        cmd = self.registry.get("search-all")
        self.assertIsNotNone(cmd)

    def test_cross_deps_registered(self) -> None:
        cmd = self.registry.get("cross-deps")
        self.assertIsNotNone(cmd)

    def test_shared_config_registered(self) -> None:
        cmd = self.registry.get("shared-config")
        self.assertIsNotNone(cmd)

    def test_workspace_handler_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cmd = self.registry.get("workspace")
            result = asyncio.run(cmd.handler(tmp))
            self.assertIn("unknown", result)

    def test_workspace_handler_nx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            nx_path = os.path.join(tmp, "nx.json")
            with open(nx_path, "w") as fh:
                fh.write("{}")
            cmd = self.registry.get("workspace")
            result = asyncio.run(cmd.handler(tmp))
            self.assertIn("nx", result)

    def test_search_all_no_args(self) -> None:
        cmd = self.registry.get("search-all")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_search_all_no_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cmd = self.registry.get("search-all")
            result = asyncio.run(cmd.handler(f"NONEXISTENT_PATTERN {tmp}"))
            self.assertIn("No results", result)

    def test_search_all_with_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fpath = os.path.join(tmp, "test.py")
            with open(fpath, "w") as fh:
                fh.write("hello world\n")
            cmd = self.registry.get("search-all")
            result = asyncio.run(cmd.handler(f"hello {tmp}"))
            self.assertIn("hello", result)
            self.assertIn("1 result", result)

    def test_cross_deps_no_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cmd = self.registry.get("cross-deps")
            result = asyncio.run(cmd.handler(tmp))
            self.assertIn("No packages", result)

    def test_cross_deps_with_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "nx.json"), "w") as fh:
                fh.write("{}")
            pkg_dir = os.path.join(tmp, "packages", "core")
            os.makedirs(pkg_dir, exist_ok=True)
            with open(os.path.join(pkg_dir, "package.json"), "w") as fh:
                json.dump({"name": "core"}, fh)
            cmd = self.registry.get("cross-deps")
            result = asyncio.run(cmd.handler(tmp))
            self.assertIn("core", result)

    def test_shared_config_no_args(self) -> None:
        cmd = self.registry.get("shared-config")
        result = asyncio.run(cmd.handler(""))
        self.assertIn("Usage", result)

    def test_shared_config_no_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = os.path.join(tmp, "ws")
            pkg = os.path.join(tmp, "pkg")
            os.makedirs(ws, exist_ok=True)
            os.makedirs(pkg, exist_ok=True)
            cmd = self.registry.get("shared-config")
            result = asyncio.run(cmd.handler(f"{ws} {pkg}"))
            self.assertIn("No configuration", result)

    def test_shared_config_with_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = os.path.join(tmp, "ws")
            pkg = os.path.join(tmp, "pkg")
            cfg_dir = os.path.join(ws, ".lidco")
            os.makedirs(cfg_dir, exist_ok=True)
            os.makedirs(pkg, exist_ok=True)
            with open(os.path.join(cfg_dir, "config.json"), "w") as fh:
                json.dump({"debug": True}, fh)
            cmd = self.registry.get("shared-config")
            result = asyncio.run(cmd.handler(f"{ws} {pkg}"))
            self.assertIn("debug", result)

    def test_workspace_description(self) -> None:
        cmd = self.registry.get("workspace")
        self.assertIn("workspace", cmd.description.lower())


if __name__ == "__main__":
    unittest.main()
