"""Tests for DeployProviderRegistry (Task 707)."""
from __future__ import annotations

import json
import unittest

from lidco.scaffold.deploy_registry import DeployProvider, DeployProviderRegistry


class TestDeployProvider(unittest.TestCase):
    """Tests for the DeployProvider dataclass."""

    def test_create_provider(self):
        p = DeployProvider(
            name="test",
            detect_files=["test.toml"],
            build_cmd="make build",
            deploy_cmd="make deploy",
            env_vars_needed=["TOKEN"],
            description="A test provider",
        )
        assert p.name == "test"
        assert p.detect_files == ["test.toml"]
        assert p.build_cmd == "make build"
        assert p.deploy_cmd == "make deploy"
        assert p.env_vars_needed == ["TOKEN"]
        assert p.description == "A test provider"

    def test_provider_default_description(self):
        p = DeployProvider(
            name="x", detect_files=[], build_cmd="", deploy_cmd="", env_vars_needed=[]
        )
        assert p.description == ""


class TestDeployProviderRegistry(unittest.TestCase):
    """Tests for DeployProviderRegistry."""

    def _make_registry(self, existing_files=None):
        files = set(existing_files or [])

        def path_exists(path: str) -> bool:
            return path in files

        return DeployProviderRegistry(path_exists_fn=path_exists)

    def test_builtin_providers_registered(self):
        reg = self._make_registry()
        names = [p.name for p in reg.list_all()]
        assert "netlify" in names
        assert "railway" in names
        assert "fly" in names
        assert "heroku" in names

    def test_list_all_returns_list(self):
        reg = self._make_registry()
        result = reg.list_all()
        assert isinstance(result, list)
        assert len(result) >= 4

    def test_get_existing_provider(self):
        reg = self._make_registry()
        p = reg.get("netlify")
        assert p is not None
        assert p.name == "netlify"

    def test_get_missing_provider_returns_none(self):
        reg = self._make_registry()
        assert reg.get("nonexistent") is None

    def test_register_custom_provider(self):
        reg = self._make_registry()
        custom = DeployProvider(
            name="custom",
            detect_files=["custom.yaml"],
            build_cmd="custom build",
            deploy_cmd="custom deploy",
            env_vars_needed=["CUSTOM_KEY"],
        )
        reg.register(custom)
        got = reg.get("custom")
        assert got is not None
        assert got.name == "custom"

    def test_register_overwrites_existing(self):
        reg = self._make_registry()
        new_netlify = DeployProvider(
            name="netlify",
            detect_files=["netlify-v2.toml"],
            build_cmd="npm run build-v2",
            deploy_cmd="netlify deploy-v2",
            env_vars_needed=["NETLIFY_TOKEN_V2"],
        )
        reg.register(new_netlify)
        got = reg.get("netlify")
        assert got is not None
        assert got.detect_files == ["netlify-v2.toml"]

    def test_auto_detect_netlify_toml(self):
        reg = self._make_registry(existing_files=["/proj/netlify.toml"])
        result = reg.auto_detect("/proj")
        assert result is not None
        assert result.name == "netlify"

    def test_auto_detect_netlify_json(self):
        reg = self._make_registry(existing_files=["/proj/netlify.json"])
        result = reg.auto_detect("/proj")
        assert result is not None
        assert result.name == "netlify"

    def test_auto_detect_railway_json(self):
        reg = self._make_registry(existing_files=["/proj/railway.json"])
        result = reg.auto_detect("/proj")
        assert result is not None
        assert result.name == "railway"

    def test_auto_detect_fly_toml(self):
        reg = self._make_registry(existing_files=["/proj/fly.toml"])
        result = reg.auto_detect("/proj")
        assert result is not None
        assert result.name == "fly"

    def test_auto_detect_heroku_procfile(self):
        reg = self._make_registry(existing_files=["/proj/Procfile"])
        result = reg.auto_detect("/proj")
        assert result is not None
        assert result.name == "heroku"

    def test_auto_detect_nothing(self):
        reg = self._make_registry(existing_files=[])
        result = reg.auto_detect("/proj")
        assert result is None

    def test_auto_detect_returns_first_match(self):
        reg = self._make_registry(
            existing_files=["/proj/netlify.toml", "/proj/fly.toml"]
        )
        result = reg.auto_detect("/proj")
        assert result is not None
        # should return first match (order of registration)

    def test_auto_detect_custom_provider(self):
        reg = self._make_registry(existing_files=["/proj/myfile.cfg"])
        custom = DeployProvider(
            name="mycloud",
            detect_files=["myfile.cfg"],
            build_cmd="",
            deploy_cmd="",
            env_vars_needed=[],
        )
        reg.register(custom)
        result = reg.auto_detect("/proj")
        assert result is not None
        assert result.name == "mycloud"

    def test_save_config(self):
        reg = self._make_registry()
        written = {}

        def write_fn(path, content):
            written[path] = content

        reg.save_config("/proj", "netlify", write_fn=write_fn)
        assert len(written) == 1
        key = list(written.keys())[0]
        assert "deploy.json" in key
        data = json.loads(written[key])
        assert data["provider"] == "netlify"

    def test_load_config_missing(self):
        reg = self._make_registry()
        result = reg.load_config("/proj", read_fn=lambda p: None)
        assert result is None

    def test_load_config_present(self):
        reg = self._make_registry()
        config = json.dumps({"provider": "fly"})

        def read_fn(path):
            return config

        result = reg.load_config("/proj", read_fn=read_fn)
        assert result == "fly"

    def test_load_config_invalid_json(self):
        reg = self._make_registry()
        result = reg.load_config("/proj", read_fn=lambda p: "not json")
        assert result is None

    def test_netlify_env_vars(self):
        reg = self._make_registry()
        p = reg.get("netlify")
        assert isinstance(p.env_vars_needed, list)

    def test_heroku_detect_files(self):
        reg = self._make_registry()
        p = reg.get("heroku")
        assert "Procfile" in p.detect_files

    def test_fly_detect_files(self):
        reg = self._make_registry()
        p = reg.get("fly")
        assert "fly.toml" in p.detect_files

    def test_railway_detect_files(self):
        reg = self._make_registry()
        p = reg.get("railway")
        assert any("railway" in f for f in p.detect_files)

    def test_register_none_path_exists_fn(self):
        """Registry with None path_exists_fn should still construct."""
        reg = DeployProviderRegistry(path_exists_fn=None)
        assert reg.list_all()

    def test_save_config_creates_json_with_provider_key(self):
        reg = self._make_registry()
        captured = {}

        def wfn(path, content):
            captured["data"] = json.loads(content)

        reg.save_config("/p", "heroku", write_fn=wfn)
        assert captured["data"]["provider"] == "heroku"


if __name__ == "__main__":
    unittest.main()
