"""Generate GitHub Actions workflows from project analysis."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobType(str, Enum):
    TEST = "test"
    LINT = "lint"
    BUILD = "build"
    DEPLOY = "deploy"
    SECURITY = "security"


@dataclass(frozen=True)
class MatrixEntry:
    key: str
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class CacheConfig:
    paths: tuple[str, ...] = ()
    key: str = ""


@dataclass(frozen=True)
class Job:
    name: str
    job_type: JobType
    steps: tuple[str, ...] = ()
    matrix: tuple[MatrixEntry, ...] = ()
    cache: CacheConfig | None = None
    needs: tuple[str, ...] = ()


_PROJECT_MARKERS: dict[str, str] = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "package.json": "node",
    "Cargo.toml": "rust",
    "go.mod": "go",
}


class ActionsGenerator:
    """Generate GitHub Actions workflow configurations."""

    def __init__(self) -> None:
        self._jobs: list[Job] = []

    def detect_project(self, files: list[str]) -> dict[str, Any]:
        """Detect project type from file list."""
        result: dict[str, Any] = {"type": "unknown", "files": tuple(files)}
        for f in files:
            for marker, ptype in _PROJECT_MARKERS.items():
                if f.endswith(marker):
                    return {**result, "type": ptype}
        return result

    def generate_test_job(
        self,
        project_type: str,
        python_versions: tuple[str, ...] = ("3.11", "3.12"),
    ) -> Job:
        """Generate a test job for the given project type."""
        steps: tuple[str, ...]
        matrix: tuple[MatrixEntry, ...] = ()
        cache: CacheConfig | None = None
        if project_type == "python":
            matrix = (MatrixEntry(key="python-version", values=python_versions),)
            cache = CacheConfig(paths=("~/.cache/pip",), key="pip-${{ hashFiles('**/pyproject.toml') }}")
            steps = ("actions/checkout@v4", "actions/setup-python@v5", "pip install -e '.[dev]'", "pytest -q")
        elif project_type == "node":
            steps = ("actions/checkout@v4", "actions/setup-node@v4", "npm ci", "npm test")
            cache = CacheConfig(paths=("node_modules",), key="node-${{ hashFiles('package-lock.json') }}")
        elif project_type == "rust":
            steps = ("actions/checkout@v4", "cargo test")
        elif project_type == "go":
            steps = ("actions/checkout@v4", "go test ./...")
        else:
            steps = ("actions/checkout@v4", "echo 'No test runner configured'")
        job = Job(name="test", job_type=JobType.TEST, steps=steps, matrix=matrix, cache=cache)
        self._jobs = [*self._jobs, job]
        return job

    def generate_lint_job(self, project_type: str) -> Job:
        """Generate a lint job."""
        steps: tuple[str, ...]
        if project_type == "python":
            steps = ("actions/checkout@v4", "pip install ruff", "ruff check .")
        elif project_type == "node":
            steps = ("actions/checkout@v4", "npm ci", "npm run lint")
        elif project_type == "rust":
            steps = ("actions/checkout@v4", "cargo clippy")
        else:
            steps = ("actions/checkout@v4", "echo 'No linter configured'")
        job = Job(name="lint", job_type=JobType.LINT, steps=steps)
        self._jobs = [*self._jobs, job]
        return job

    def generate_build_job(self, project_type: str) -> Job:
        """Generate a build job."""
        steps: tuple[str, ...]
        if project_type == "python":
            steps = ("actions/checkout@v4", "pip install build", "python -m build")
        elif project_type == "node":
            steps = ("actions/checkout@v4", "npm ci", "npm run build")
        elif project_type == "rust":
            steps = ("actions/checkout@v4", "cargo build --release")
        else:
            steps = ("actions/checkout@v4", "echo 'No build step configured'")
        job = Job(name="build", job_type=JobType.BUILD, steps=steps, needs=("test",))
        self._jobs = [*self._jobs, job]
        return job

    def generate_deploy_job(self, target: str = "vercel") -> Job:
        """Generate a deploy job."""
        steps = ("actions/checkout@v4", f"deploy to {target}")
        job = Job(name="deploy", job_type=JobType.DEPLOY, steps=steps, needs=("build",))
        self._jobs = [*self._jobs, job]
        return job

    def generate_security_job(self) -> Job:
        """Generate a security scanning job."""
        steps = ("actions/checkout@v4", "github/codeql-action/init@v3", "github/codeql-action/analyze@v3")
        job = Job(name="security", job_type=JobType.SECURITY, steps=steps)
        self._jobs = [*self._jobs, job]
        return job

    def to_yaml(self, jobs: list[Job]) -> str:
        """Generate YAML string for workflow (no pyyaml dependency)."""
        lines: list[str] = [
            "name: CI",
            "on:",
            "  push:",
            "    branches: [main]",
            "  pull_request:",
            "    branches: [main]",
            "jobs:",
        ]
        for job in jobs:
            lines.append(f"  {job.name}:")
            lines.append("    runs-on: ubuntu-latest")
            if job.matrix:
                lines.append("    strategy:")
                lines.append("      matrix:")
                for m in job.matrix:
                    vals = ", ".join(f'"{v}"' for v in m.values)
                    lines.append(f"        {m.key}: [{vals}]")
            if job.needs:
                needs_str = ", ".join(job.needs)
                lines.append(f"    needs: [{needs_str}]")
            if job.cache:
                lines.append(f"    # cache: key={job.cache.key}")
            lines.append("    steps:")
            for step in job.steps:
                if step.startswith("actions/") or step.startswith("github/"):
                    lines.append(f"      - uses: {step}")
                else:
                    lines.append(f"      - run: {step}")
        return "\n".join(lines) + "\n"

    def summary(self, jobs: list[Job]) -> str:
        """Return human-readable summary of jobs."""
        if not jobs:
            return "No jobs configured."
        parts = [f"Workflow: {len(jobs)} job(s)"]
        for job in jobs:
            deps = f" (needs: {', '.join(job.needs)})" if job.needs else ""
            parts.append(f"  - {job.name} [{job.job_type.value}]: {len(job.steps)} steps{deps}")
        return "\n".join(parts)
