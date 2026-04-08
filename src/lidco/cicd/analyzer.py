"""
Pipeline Analyzer — parse CI pipeline configs, find bottlenecks,
suggest parallelization and cache opportunities.

Supports GitHub Actions, GitLab CI, and CircleCI config formats.
Pure stdlib (+ yaml if available).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

try:
    import yaml as _yaml  # type: ignore[import-untyped]
except ImportError:
    _yaml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class StageInfo:
    """Describes a single pipeline stage/job."""

    name: str
    steps: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    estimated_duration: float = 0.0  # seconds
    has_cache: bool = False
    parallelisable: bool = False


@dataclass(frozen=True)
class Bottleneck:
    """A detected bottleneck in the pipeline."""

    stage: str
    kind: str  # "sequential", "no-cache", "long-running", "redundant"
    description: str
    suggestion: str


@dataclass(frozen=True)
class PipelineAnalysis:
    """Full analysis result."""

    provider: str  # "github", "gitlab", "circleci", "unknown"
    total_stages: int
    stages: list[StageInfo]
    bottlenecks: list[Bottleneck]
    cache_opportunities: list[str]
    parallelization_suggestions: list[str]
    estimated_total_duration: float


class PipelineAnalyzer:
    """Analyze CI pipeline configuration files for bottlenecks."""

    def __init__(self, repo_path: str = ".") -> None:
        self._repo_path = repo_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, config_path: str | None = None) -> PipelineAnalysis:
        """Analyze the CI pipeline config.

        If *config_path* is ``None``, auto-detect from the repo.
        """
        if config_path is None:
            config_path = self._detect_config()

        if config_path is None:
            return PipelineAnalysis(
                provider="unknown",
                total_stages=0,
                stages=[],
                bottlenecks=[],
                cache_opportunities=[],
                parallelization_suggestions=[],
                estimated_total_duration=0.0,
            )

        raw = self._read_file(config_path)
        provider = self._detect_provider(config_path)
        data = self._parse_config(raw, config_path)

        stages = self._extract_stages(data, provider)
        bottlenecks = self._find_bottlenecks(stages)
        cache_opps = self._find_cache_opportunities(stages)
        par_suggestions = self._find_parallelization(stages)
        total_dur = sum(s.estimated_duration for s in stages)

        return PipelineAnalysis(
            provider=provider,
            total_stages=len(stages),
            stages=stages,
            bottlenecks=bottlenecks,
            cache_opportunities=cache_opps,
            parallelization_suggestions=par_suggestions,
            estimated_total_duration=total_dur,
        )

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------

    def _detect_config(self) -> str | None:
        candidates = [
            os.path.join(self._repo_path, ".github", "workflows"),
            os.path.join(self._repo_path, ".gitlab-ci.yml"),
            os.path.join(self._repo_path, ".circleci", "config.yml"),
        ]
        # GitHub Actions — pick first yaml in workflows dir
        wf_dir = candidates[0]
        if os.path.isdir(wf_dir):
            for fname in sorted(os.listdir(wf_dir)):
                if fname.endswith((".yml", ".yaml")):
                    return os.path.join(wf_dir, fname)
        for p in candidates[1:]:
            if os.path.isfile(p):
                return p
        return None

    @staticmethod
    def _detect_provider(config_path: str) -> str:
        if ".github" in config_path:
            return "github"
        if "gitlab" in os.path.basename(config_path):
            return "gitlab"
        if ".circleci" in config_path:
            return "circleci"
        return "unknown"

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _read_file(self, path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def _parse_config(self, raw: str, path: str) -> dict[str, Any]:
        if path.endswith(".json"):
            return json.loads(raw)  # type: ignore[no-any-return]
        if _yaml is not None:
            return _yaml.safe_load(raw) or {}  # type: ignore[no-any-return]
        # Minimal YAML-like fallback: just return empty
        return self._minimal_yaml_parse(raw)

    @staticmethod
    def _minimal_yaml_parse(raw: str) -> dict[str, Any]:
        """Very basic key extraction when PyYAML is unavailable."""
        result: dict[str, Any] = {}
        for line in raw.splitlines():
            m = re.match(r"^(\w[\w-]*):\s*(.*)", line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                result[key] = val if val else {}
        return result

    # ------------------------------------------------------------------
    # Stage extraction
    # ------------------------------------------------------------------

    def _extract_stages(self, data: dict[str, Any], provider: str) -> list[StageInfo]:
        if provider == "github":
            return self._extract_github(data)
        if provider == "gitlab":
            return self._extract_gitlab(data)
        if provider == "circleci":
            return self._extract_circleci(data)
        return []

    def _extract_github(self, data: dict[str, Any]) -> list[StageInfo]:
        jobs = data.get("jobs", {})
        stages: list[StageInfo] = []
        for name, cfg in jobs.items():
            if not isinstance(cfg, dict):
                continue
            steps = [
                s.get("name", s.get("run", "step"))
                for s in cfg.get("steps", [])
                if isinstance(s, dict)
            ]
            needs = cfg.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
            has_cache = any(
                isinstance(s, dict) and "cache" in str(s).lower()
                for s in cfg.get("steps", [])
            )
            stages.append(
                StageInfo(
                    name=name,
                    steps=steps,
                    depends_on=needs,
                    estimated_duration=len(steps) * 30.0,
                    has_cache=has_cache,
                    parallelisable=len(needs) == 0,
                )
            )
        return stages

    def _extract_gitlab(self, data: dict[str, Any]) -> list[StageInfo]:
        stage_order = data.get("stages", [])
        stages: list[StageInfo] = []
        for name, cfg in data.items():
            if name in ("stages", "variables", "default", "include", "image"):
                continue
            if not isinstance(cfg, dict):
                continue
            script = cfg.get("script", [])
            if isinstance(script, str):
                script = [script]
            stage_name = cfg.get("stage", "test")
            deps = cfg.get("needs", cfg.get("dependencies", []))
            if isinstance(deps, str):
                deps = [deps]
            has_cache = "cache" in cfg
            stages.append(
                StageInfo(
                    name=name,
                    steps=script,
                    depends_on=deps,
                    estimated_duration=len(script) * 30.0,
                    has_cache=has_cache,
                    parallelisable=len(deps) == 0,
                )
            )
        return stages

    def _extract_circleci(self, data: dict[str, Any]) -> list[StageInfo]:
        jobs = data.get("jobs", {})
        stages: list[StageInfo] = []
        for name, cfg in jobs.items():
            if not isinstance(cfg, dict):
                continue
            steps = []
            for s in cfg.get("steps", []):
                if isinstance(s, str):
                    steps.append(s)
                elif isinstance(s, dict):
                    steps.append(next(iter(s.keys()), "step"))
            has_cache = any(
                (isinstance(s, dict) and ("save_cache" in s or "restore_cache" in s))
                or s in ("save_cache", "restore_cache")
                for s in cfg.get("steps", [])
            )
            stages.append(
                StageInfo(
                    name=name,
                    steps=steps,
                    depends_on=[],
                    estimated_duration=len(steps) * 30.0,
                    has_cache=has_cache,
                    parallelisable=True,
                )
            )
        return stages

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def _find_bottlenecks(self, stages: list[StageInfo]) -> list[Bottleneck]:
        bottlenecks: list[Bottleneck] = []
        for s in stages:
            if not s.has_cache and len(s.steps) > 2:
                bottlenecks.append(
                    Bottleneck(
                        stage=s.name,
                        kind="no-cache",
                        description=f"Stage '{s.name}' has {len(s.steps)} steps but no caching",
                        suggestion=f"Add dependency/artifact caching to '{s.name}'",
                    )
                )
            if s.estimated_duration > 300:
                bottlenecks.append(
                    Bottleneck(
                        stage=s.name,
                        kind="long-running",
                        description=f"Stage '{s.name}' estimated at {s.estimated_duration:.0f}s",
                        suggestion=f"Split '{s.name}' into parallel sub-jobs",
                    )
                )
            if len(s.depends_on) > 0 and not s.parallelisable:
                # sequential dependency chain
                bottlenecks.append(
                    Bottleneck(
                        stage=s.name,
                        kind="sequential",
                        description=f"Stage '{s.name}' blocked by {s.depends_on}",
                        suggestion=f"Check if '{s.name}' can run in parallel with its dependencies",
                    )
                )
        return bottlenecks

    def _find_cache_opportunities(self, stages: list[StageInfo]) -> list[str]:
        opps: list[str] = []
        for s in stages:
            if not s.has_cache:
                for step in s.steps:
                    lower = step.lower() if isinstance(step, str) else ""
                    if any(kw in lower for kw in ("install", "npm", "pip", "yarn", "pnpm", "cargo")):
                        opps.append(f"Cache dependencies in '{s.name}' (step: {step})")
                        break
        return opps

    def _find_parallelization(self, stages: list[StageInfo]) -> list[str]:
        suggestions: list[str] = []
        independent = [s for s in stages if not s.depends_on]
        if len(independent) > 1:
            names = ", ".join(s.name for s in independent)
            suggestions.append(f"Run independent stages in parallel: {names}")
        return suggestions
