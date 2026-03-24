"""Tests for src/lidco/config/team_config.py."""

import pytest
from pathlib import Path
from lidco.config.team_config import MergedConfig, TeamConfig, TeamConfigLoader


def make_loader(tmp_path: Path) -> TeamConfigLoader:
    return TeamConfigLoader(project_root=tmp_path)


def write_yaml(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestTeamConfigDataclass:
    def test_defaults(self):
        cfg = TeamConfig()
        assert cfg.model == ""
        assert cfg.tools == []
        assert cfg.rules == []
        assert cfg.permissions == {}
        assert cfg.members == []

    def test_custom(self):
        cfg = TeamConfig(model="claude-opus-4-6", members=["alice", "bob"])
        assert cfg.model == "claude-opus-4-6"
        assert cfg.members == ["alice", "bob"]


class TestMergedConfigDataclass:
    def test_fields(self):
        tc = TeamConfig(model="gpt-4")
        merged = MergedConfig(team=tc, personal={}, resolved={"model": "gpt-4"})
        assert merged.resolved["model"] == "gpt-4"
        assert merged.personal == {}


class TestLoadTeam:
    def test_no_file_returns_none(self, tmp_path):
        loader = make_loader(tmp_path)
        assert loader.load_team() is None

    def test_loads_model(self, tmp_path):
        write_yaml(
            tmp_path / ".lidco" / "team.yaml",
            "model: claude-sonnet-4-6\n",
        )
        loader = make_loader(tmp_path)
        cfg = loader.load_team()
        assert cfg is not None
        assert cfg.model == "claude-sonnet-4-6"

    def test_loads_tools_list(self, tmp_path):
        write_yaml(
            tmp_path / ".lidco" / "team.yaml",
            "tools:\n  - read\n  - write\n",
        )
        loader = make_loader(tmp_path)
        cfg = loader.load_team()
        assert cfg is not None
        assert "read" in cfg.tools

    def test_loads_members(self, tmp_path):
        write_yaml(
            tmp_path / ".lidco" / "team.yaml",
            "members:\n  - alice\n  - bob\n",
        )
        loader = make_loader(tmp_path)
        cfg = loader.load_team()
        assert cfg is not None
        assert set(cfg.members) == {"alice", "bob"}

    def test_loads_permissions(self, tmp_path):
        write_yaml(
            tmp_path / ".lidco" / "team.yaml",
            "permissions:\n  allow_push: true\n  allow_delete: false\n",
        )
        loader = make_loader(tmp_path)
        cfg = loader.load_team()
        assert cfg is not None
        assert cfg.permissions["allow_push"] is True
        assert cfg.permissions["allow_delete"] is False


class TestLoadPersonal:
    def test_no_file_returns_empty(self, tmp_path):
        loader = make_loader(tmp_path)
        assert loader.load_personal() == {}

    def test_loads_override(self, tmp_path):
        write_yaml(
            tmp_path / ".lidco" / "user.yaml",
            "model: claude-haiku-4-5\n",
        )
        loader = make_loader(tmp_path)
        personal = loader.load_personal()
        assert personal.get("model") == "claude-haiku-4-5"


class TestMerge:
    def test_personal_wins(self, tmp_path):
        loader = make_loader(tmp_path)
        team = TeamConfig(model="team-model")
        personal = {"model": "personal-model"}
        merged = loader.merge(team, personal)
        assert merged.resolved["model"] == "personal-model"

    def test_team_default_when_no_personal(self, tmp_path):
        loader = make_loader(tmp_path)
        team = TeamConfig(model="team-model")
        merged = loader.merge(team, {})
        assert merged.resolved["model"] == "team-model"

    def test_team_preserved_in_merged(self, tmp_path):
        loader = make_loader(tmp_path)
        team = TeamConfig(model="m")
        merged = loader.merge(team, {})
        assert merged.team is team

    def test_personal_preserved_in_merged(self, tmp_path):
        loader = make_loader(tmp_path)
        team = TeamConfig()
        personal = {"extra_key": "val"}
        merged = loader.merge(team, personal)
        assert merged.personal == personal
        assert merged.resolved.get("extra_key") == "val"

    def test_deep_merge_permissions(self, tmp_path):
        # B3: personal.permissions should merge into team.permissions, not replace
        loader = make_loader(tmp_path)
        team = TeamConfig(permissions={"allow_push": True, "allow_delete": True})
        personal = {"permissions": {"allow_push": False}}  # only override one key
        merged = loader.merge(team, personal)
        assert merged.resolved["permissions"]["allow_push"] is False
        assert merged.resolved["permissions"]["allow_delete"] is True  # kept from team

    def test_scalar_personal_replaces_team(self, tmp_path):
        # Scalars and lists are replaced (not merged) when personal provides them
        loader = make_loader(tmp_path)
        team = TeamConfig(tools=["read", "write"])
        personal = {"tools": ["read"]}
        merged = loader.merge(team, personal)
        assert merged.resolved["tools"] == ["read"]


class TestValidate:
    def test_valid_config(self, tmp_path):
        loader = make_loader(tmp_path)
        cfg = TeamConfig(model="m", tools=["t"], permissions={"a": True})
        assert loader.validate(cfg) == []

    def test_invalid_permissions_type(self, tmp_path):
        loader = make_loader(tmp_path)
        cfg = TeamConfig()
        cfg.permissions = {"allow": "yes"}  # type: ignore[assignment]
        errors = loader.validate(cfg)
        assert any("allow" in e for e in errors)

    def test_invalid_tools_type(self, tmp_path):
        loader = make_loader(tmp_path)
        cfg = TeamConfig()
        cfg.tools = "not-a-list"  # type: ignore[assignment]
        errors = loader.validate(cfg)
        assert any("tools" in e for e in errors)

    def test_invalid_tools_element_type(self, tmp_path):
        # B10: validate list element types
        loader = make_loader(tmp_path)
        cfg = TeamConfig(tools=["ok", 42])  # type: ignore[list-item]
        errors = loader.validate(cfg)
        assert any("tools[1]" in e for e in errors)

    def test_invalid_members_element_type(self, tmp_path):
        # B10: validate members list element types
        loader = make_loader(tmp_path)
        cfg = TeamConfig(members=["alice", None])  # type: ignore[list-item]
        errors = loader.validate(cfg)
        assert any("members[1]" in e for e in errors)


class TestReadYamlConsistency:
    def test_parse_error_returns_empty_dict(self, tmp_path):
        # B2: parse errors should return {} not None
        path = tmp_path / ".lidco" / "team.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("key: [unclosed bracket\n", encoding="utf-8")
        loader = make_loader(tmp_path)
        # load_team should return TeamConfig (not None) with empty fields
        cfg = loader.load_team()
        assert cfg is not None
        assert cfg.model == ""


class TestLoad:
    def test_no_files_returns_empty_merged(self, tmp_path):
        loader = make_loader(tmp_path)
        merged = loader.load()
        assert isinstance(merged, MergedConfig)
        assert merged.resolved.get("model") == ""

    def test_team_and_personal_merged(self, tmp_path):
        write_yaml(tmp_path / ".lidco" / "team.yaml", "model: team-m\n")
        write_yaml(tmp_path / ".lidco" / "user.yaml", "model: personal-m\n")
        loader = make_loader(tmp_path)
        merged = loader.load()
        assert merged.resolved["model"] == "personal-m"

    def test_full_team_config(self, tmp_path):
        write_yaml(
            tmp_path / ".lidco" / "team.yaml",
            "model: claude-opus-4-6\ntools:\n  - read\nmembers:\n  - alice\n",
        )
        loader = make_loader(tmp_path)
        merged = loader.load()
        assert merged.resolved["model"] == "claude-opus-4-6"
        assert "alice" in merged.resolved["members"]
