"""Tests for vscode/package.json — Q64 Task 431."""

from __future__ import annotations

import json
import pytest
from pathlib import Path


VSCODE_PKG_PATH = Path(__file__).parents[3] / "vscode" / "package.json"


class TestVSCodeManifest:
    def test_manifest_exists(self):
        assert VSCODE_PKG_PATH.exists(), f"vscode/package.json not found at {VSCODE_PKG_PATH}"

    def test_manifest_valid_json(self):
        data = json.loads(VSCODE_PKG_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_has_name_field(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        assert "name" in data
        assert data["name"] == "lidco-vscode"

    def test_has_version(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        assert "version" in data

    def test_has_engines_vscode(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        assert "engines" in data
        assert "vscode" in data["engines"]

    def test_has_contributes_commands(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        assert "contributes" in data
        assert "commands" in data["contributes"]

    def test_has_lidco_chat_command(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        commands = data["contributes"]["commands"]
        cmd_ids = [c["command"] for c in commands]
        assert "lidco.chat" in cmd_ids

    def test_has_run_on_selection_command(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        commands = data["contributes"]["commands"]
        cmd_ids = [c["command"] for c in commands]
        assert "lidco.runOnSelection" in cmd_ids

    def test_has_main_field(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        assert "main" in data

    def test_has_display_name(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        assert "displayName" in data
        assert data["displayName"] == "LIDCO"

    def test_has_publisher(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        assert "publisher" in data

    def test_has_activation_events(self):
        data = json.loads(VSCODE_PKG_PATH.read_text())
        assert "activationEvents" in data
