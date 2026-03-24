"""Tests for HTTPSlashCommand — T495."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from lidco.cli.http_commands import HTTPCommandRegistry, HTTPSlashCommand


class TestHTTPSlashCommand:
    def test_execute_success(self):
        cmd = HTTPSlashCommand(name="deploy", url="http://example.com/cmd")
        with patch("lidco.cli.http_commands.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = b"deployed!"
            mock_open.return_value = mock_resp
            result = cmd.execute("prod")
        assert result == "deployed!"

    def test_execute_url_error(self):
        from urllib.error import URLError
        cmd = HTTPSlashCommand(name="x", url="http://bad.url")
        with patch("lidco.cli.http_commands.urlopen", side_effect=URLError("no route")):
            result = cmd.execute("args")
        assert "HTTP error" in result

    def test_default_method_post(self):
        cmd = HTTPSlashCommand(name="x", url="http://x.com")
        assert cmd.method == "POST"


class TestHTTPCommandRegistry:
    def test_register_and_get(self):
        reg = HTTPCommandRegistry()
        cmd = HTTPSlashCommand(name="deploy", url="http://x.com")
        reg.register(cmd)
        assert reg.get("deploy") is cmd

    def test_get_missing(self):
        reg = HTTPCommandRegistry()
        assert reg.get("nope") is None

    def test_list(self):
        reg = HTTPCommandRegistry()
        reg.register(HTTPSlashCommand(name="a", url="http://a"))
        reg.register(HTTPSlashCommand(name="b", url="http://b"))
        assert len(reg.list()) == 2

    def test_unregister(self):
        reg = HTTPCommandRegistry()
        reg.register(HTTPSlashCommand(name="x", url="http://x"))
        assert reg.unregister("x")
        assert reg.get("x") is None

    def test_load_yaml(self, tmp_path):
        yaml_file = tmp_path / "http_commands.yaml"
        yaml_file.write_text("- name: deploy\n  url: http://x.com\n")
        reg = HTTPCommandRegistry()
        count = reg.load_yaml(yaml_file)
        assert count >= 1
        assert reg.get("deploy") is not None

    def test_load_yaml_missing_file(self, tmp_path):
        reg = HTTPCommandRegistry()
        count = reg.load_yaml(tmp_path / "missing.yaml")
        assert count == 0
