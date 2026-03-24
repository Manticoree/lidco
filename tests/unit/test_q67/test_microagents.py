"""Tests for Task 457: Microagent knowledge injection."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from lidco.microagents.loader import Microagent, MicroagentLoader, MicroagentMatcher


class TestMicroagentLoader:
    """Tests for MicroagentLoader."""

    def _write_md(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_load_file_with_frontmatter(self, tmp_path: Path) -> None:
        md = tmp_path / "deploy.md"
        self._write_md(md, (
            "---\n"
            "triggers: [deploy, rollback]\n"
            "priority: 5\n"
            "---\n"
            "Always use blue-green deployments.\n"
        ))
        loader = MicroagentLoader()
        ma = loader.load_file(md)
        assert ma is not None
        assert ma.name == "deploy"
        assert ma.triggers == ["deploy", "rollback"]
        assert ma.priority == 5
        assert "blue-green" in ma.content
        assert ma.source_path == str(md)

    def test_load_file_no_frontmatter_returns_none(self, tmp_path: Path) -> None:
        md = tmp_path / "plain.md"
        self._write_md(md, "Just some markdown without frontmatter.")
        loader = MicroagentLoader()
        assert loader.load_file(md) is None

    def test_load_file_no_triggers_returns_none(self, tmp_path: Path) -> None:
        md = tmp_path / "no_triggers.md"
        self._write_md(md, "---\npriority: 3\n---\nContent here.\n")
        loader = MicroagentLoader()
        assert loader.load_file(md) is None

    def test_load_file_missing_file_returns_none(self, tmp_path: Path) -> None:
        loader = MicroagentLoader()
        assert loader.load_file(tmp_path / "nonexistent.md") is None

    def test_load_file_default_priority(self, tmp_path: Path) -> None:
        md = tmp_path / "basic.md"
        self._write_md(md, "---\ntriggers: [test]\n---\nBody.\n")
        loader = MicroagentLoader()
        ma = loader.load_file(md)
        assert ma is not None
        assert ma.priority == 0

    def test_load_all_from_project_dir(self, tmp_path: Path) -> None:
        ma_dir = tmp_path / ".lidco" / "microagents"
        self._write_md(ma_dir / "one.md", "---\ntriggers: [docker]\n---\nUse compose.\n")
        self._write_md(ma_dir / "two.md", "---\ntriggers: [lint]\npriority: 2\n---\nRun ruff.\n")
        loader = MicroagentLoader()
        results = loader.load_all(tmp_path)
        assert len(results) == 2
        names = {m.name for m in results}
        assert "one" in names
        assert "two" in names

    def test_load_all_empty_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".lidco" / "microagents").mkdir(parents=True)
        loader = MicroagentLoader()
        assert loader.load_all(tmp_path) == []

    def test_load_all_no_dir(self, tmp_path: Path) -> None:
        loader = MicroagentLoader()
        assert loader.load_all(tmp_path) == []

    def test_load_file_quoted_triggers(self, tmp_path: Path) -> None:
        md = tmp_path / "quoted.md"
        self._write_md(md, '---\ntriggers: ["ci", \'cd\']\n---\nPipeline tips.\n')
        loader = MicroagentLoader()
        ma = loader.load_file(md)
        assert ma is not None
        assert ma.triggers == ["ci", "cd"]


class TestMicroagentMatcher:
    """Tests for MicroagentMatcher."""

    def _ma(self, name: str, triggers: list[str], priority: int = 0) -> Microagent:
        return Microagent(name=name, content=f"{name} content", triggers=triggers, priority=priority)

    def test_match_finds_keyword(self) -> None:
        matcher = MicroagentMatcher()
        agents = [self._ma("deploy", ["deploy", "rollback"])]
        result = matcher.match("How do I deploy to staging?", agents)
        assert len(result) == 1
        assert result[0].name == "deploy"

    def test_match_case_insensitive(self) -> None:
        matcher = MicroagentMatcher()
        agents = [self._ma("deploy", ["deploy"])]
        result = matcher.match("Deploy the app now", agents)
        assert len(result) == 1

    def test_match_no_keywords(self) -> None:
        matcher = MicroagentMatcher()
        agents = [self._ma("deploy", ["deploy"])]
        result = matcher.match("How do I write tests?", agents)
        assert result == []

    def test_match_sorted_by_priority(self) -> None:
        matcher = MicroagentMatcher()
        agents = [
            self._ma("low", ["test"], priority=1),
            self._ma("high", ["test"], priority=10),
            self._ma("mid", ["test"], priority=5),
        ]
        result = matcher.match("test something", agents)
        assert [m.name for m in result] == ["high", "mid", "low"]

    def test_format_for_prompt_empty(self) -> None:
        matcher = MicroagentMatcher()
        assert matcher.format_for_prompt([]) == ""

    def test_format_for_prompt_with_matches(self) -> None:
        matcher = MicroagentMatcher()
        agents = [self._ma("deploy", ["deploy"], priority=5)]
        text = matcher.format_for_prompt(agents)
        assert "## Project Knowledge" in text
        assert "### deploy" in text
        assert "deploy content" in text

    def test_match_multiple_agents(self) -> None:
        matcher = MicroagentMatcher()
        agents = [
            self._ma("docker", ["docker"]),
            self._ma("deploy", ["deploy"]),
            self._ma("ci", ["ci"]),
        ]
        result = matcher.match("deploy with docker in ci", agents)
        assert len(result) == 3
