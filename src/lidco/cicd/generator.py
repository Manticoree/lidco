"""
Pipeline Generator — generate CI config from project structure.

Supports GitHub Actions, GitLab CI, and CircleCI.  Detects language,
test frameworks, and build tools to produce optimized pipeline configs.
Pure stdlib.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GeneratedStage:
    """A stage in the generated pipeline."""

    name: str
    commands: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    cache_paths: list[str] = field(default_factory=list)
    image: str = ""
    condition: str = ""


@dataclass(frozen=True)
class GeneratedPipeline:
    """Full generated pipeline config."""

    provider: str
    language: str
    stages: list[GeneratedStage]
    raw_config: str  # The YAML/JSON text ready to write


class PipelineGenerator:
    """Generate CI configuration files from project structure."""

    PROVIDERS = ("github", "gitlab", "circleci")

    def __init__(self, repo_path: str = ".") -> None:
        self._repo_path = repo_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        provider: str = "github",
        language: str | None = None,
    ) -> GeneratedPipeline:
        """Generate a pipeline config for *provider*.

        If *language* is ``None``, auto-detect from repo contents.
        """
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")

        if language is None:
            language = self._detect_language()

        stages = self._build_stages(language)
        raw = self._render(provider, language, stages)

        return GeneratedPipeline(
            provider=provider,
            language=language,
            stages=stages,
            raw_config=raw,
        )

    # ------------------------------------------------------------------
    # Language detection
    # ------------------------------------------------------------------

    def _detect_language(self) -> str:
        indicators: dict[str, list[str]] = {
            "python": ["setup.py", "pyproject.toml", "requirements.txt", "Pipfile"],
            "node": ["package.json", "yarn.lock", "pnpm-lock.yaml"],
            "rust": ["Cargo.toml"],
            "go": ["go.mod"],
            "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
        }
        for lang, files in indicators.items():
            for fname in files:
                if os.path.exists(os.path.join(self._repo_path, fname)):
                    return lang
        return "unknown"

    # ------------------------------------------------------------------
    # Stage building
    # ------------------------------------------------------------------

    def _build_stages(self, language: str) -> list[GeneratedStage]:
        builders = {
            "python": self._python_stages,
            "node": self._node_stages,
            "rust": self._rust_stages,
            "go": self._go_stages,
            "java": self._java_stages,
        }
        builder = builders.get(language, self._default_stages)
        return builder()

    def _python_stages(self) -> list[GeneratedStage]:
        return [
            GeneratedStage(
                name="lint",
                commands=["pip install ruff", "ruff check ."],
                cache_paths=["~/.cache/pip"],
            ),
            GeneratedStage(
                name="test",
                commands=[
                    "pip install -e '.[test]'",
                    "python -m pytest --tb=short -q",
                ],
                cache_paths=["~/.cache/pip"],
            ),
            GeneratedStage(
                name="build",
                commands=["pip install build", "python -m build"],
                depends_on=["lint", "test"],
                cache_paths=["~/.cache/pip"],
            ),
        ]

    def _node_stages(self) -> list[GeneratedStage]:
        return [
            GeneratedStage(
                name="install",
                commands=["npm ci"],
                cache_paths=["node_modules"],
            ),
            GeneratedStage(
                name="lint",
                commands=["npm run lint"],
                depends_on=["install"],
            ),
            GeneratedStage(
                name="test",
                commands=["npm test"],
                depends_on=["install"],
            ),
            GeneratedStage(
                name="build",
                commands=["npm run build"],
                depends_on=["lint", "test"],
            ),
        ]

    def _rust_stages(self) -> list[GeneratedStage]:
        return [
            GeneratedStage(
                name="check",
                commands=["cargo check", "cargo clippy -- -D warnings"],
                cache_paths=["~/.cargo/registry", "target"],
            ),
            GeneratedStage(
                name="test",
                commands=["cargo test"],
                cache_paths=["target"],
            ),
            GeneratedStage(
                name="build",
                commands=["cargo build --release"],
                depends_on=["check", "test"],
                cache_paths=["target"],
            ),
        ]

    def _go_stages(self) -> list[GeneratedStage]:
        return [
            GeneratedStage(
                name="lint",
                commands=["go vet ./..."],
                cache_paths=["~/go/pkg/mod"],
            ),
            GeneratedStage(
                name="test",
                commands=["go test ./..."],
                cache_paths=["~/go/pkg/mod"],
            ),
            GeneratedStage(
                name="build",
                commands=["go build ./..."],
                depends_on=["lint", "test"],
                cache_paths=["~/go/pkg/mod"],
            ),
        ]

    def _java_stages(self) -> list[GeneratedStage]:
        return [
            GeneratedStage(
                name="test",
                commands=["./gradlew test"],
                cache_paths=["~/.gradle/caches"],
            ),
            GeneratedStage(
                name="build",
                commands=["./gradlew build"],
                depends_on=["test"],
                cache_paths=["~/.gradle/caches"],
            ),
        ]

    def _default_stages(self) -> list[GeneratedStage]:
        return [
            GeneratedStage(name="build", commands=["echo 'Add build steps'"]),
            GeneratedStage(name="test", commands=["echo 'Add test steps'"]),
        ]

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, provider: str, language: str, stages: list[GeneratedStage]) -> str:
        if provider == "github":
            return self._render_github(stages)
        if provider == "gitlab":
            return self._render_gitlab(stages)
        if provider == "circleci":
            return self._render_circleci(stages)
        return ""

    def _render_github(self, stages: list[GeneratedStage]) -> str:
        lines = [
            "name: CI",
            "on:",
            "  push:",
            "    branches: [main]",
            "  pull_request:",
            "    branches: [main]",
            "",
            "jobs:",
        ]
        for s in stages:
            lines.append(f"  {s.name}:")
            lines.append("    runs-on: ubuntu-latest")
            lines.append("    steps:")
            lines.append("      - uses: actions/checkout@v4")
            if s.cache_paths:
                lines.append("      - uses: actions/cache@v4")
                lines.append("        with:")
                lines.append(f"          path: {s.cache_paths[0]}")
                lines.append(f"          key: ${{{{ runner.os }}}}-{s.name}")
            for cmd in s.commands:
                lines.append(f"      - run: {cmd}")
            if s.depends_on:
                lines.append(f"    needs: [{', '.join(s.depends_on)}]")
            lines.append("")
        return "\n".join(lines)

    def _render_gitlab(self, stages: list[GeneratedStage]) -> str:
        stage_names = [s.name for s in stages]
        lines = ["stages:", *[f"  - {n}" for n in stage_names], ""]
        for s in stages:
            lines.append(f"{s.name}:")
            lines.append(f"  stage: {s.name}")
            lines.append("  script:")
            for cmd in s.commands:
                lines.append(f"    - {cmd}")
            if s.cache_paths:
                lines.append("  cache:")
                lines.append("    paths:")
                for p in s.cache_paths:
                    lines.append(f"      - {p}")
            if s.depends_on:
                lines.append(f"  needs: [{', '.join(s.depends_on)}]")
            lines.append("")
        return "\n".join(lines)

    def _render_circleci(self, stages: list[GeneratedStage]) -> str:
        lines = ["version: 2.1", "", "jobs:"]
        for s in stages:
            lines.append(f"  {s.name}:")
            lines.append("    docker:")
            lines.append("      - image: cimg/base:current")
            lines.append("    steps:")
            lines.append("      - checkout")
            for cmd in s.commands:
                lines.append("      - run:")
                lines.append(f"          command: {cmd}")
            lines.append("")
        lines.extend(["workflows:", "  main:", "    jobs:"])
        for s in stages:
            if s.depends_on:
                lines.append(f"      - {s.name}:")
                lines.append(f"          requires: [{', '.join(s.depends_on)}]")
            else:
                lines.append(f"      - {s.name}")
        lines.append("")
        return "\n".join(lines)
