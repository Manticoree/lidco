"""Project context detection and collection for LIDCO."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Directories to skip when building project structure tree
_SKIP_DIRS = frozenset({
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "coverage",
    ".coverage",
    "htmlcov",
    ".turbo",
    ".vercel",
    ".output",
    "vendor",
})

# File markers that indicate project type
_PROJECT_MARKERS: dict[str, str] = {
    "package.json": "node",
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "requirements.txt": "python",
    "Pipfile": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
    "mix.exs": "elixir",
    "pubspec.yaml": "dart",
}


@dataclass(frozen=True)
class ProjectType:
    """Detected project type information."""

    language: str = "unknown"
    framework: str = "unknown"
    package_manager: str = "unknown"
    build_tool: str = "unknown"


@dataclass(frozen=True)
class GitInfo:
    """Git repository information."""

    branch: str = ""
    remote: str = ""
    recent_commits: tuple[str, ...] = ()
    dirty_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectDependencies:
    """Parsed project dependencies."""

    production: dict[str, str] = field(default_factory=dict)
    development: dict[str, str] = field(default_factory=dict)


class ProjectContext:
    """Automatically detects and collects project context."""

    def __init__(self, project_dir: Path | str) -> None:
        self.project_dir = Path(project_dir).resolve()

    def detect_project_type(self) -> ProjectType:
        """Detect project type by presence of marker files.

        Returns a frozen ProjectType with language, framework,
        package_manager, and build_tool.
        """
        language = "unknown"
        framework = "unknown"
        package_manager = "unknown"
        build_tool = "unknown"

        for marker_file, lang in _PROJECT_MARKERS.items():
            if (self.project_dir / marker_file).exists():
                language = lang
                break

        if language == "node":
            language, framework, package_manager, build_tool = self._detect_node_details()
        elif language == "python":
            framework, package_manager, build_tool = self._detect_python_details()
        elif language == "rust":
            package_manager = "cargo"
            build_tool = "cargo"
        elif language == "go":
            package_manager = "go modules"
            build_tool = "go"
        elif language == "java":
            package_manager, build_tool = self._detect_java_details()

        return ProjectType(
            language=language,
            framework=framework,
            package_manager=package_manager,
            build_tool=build_tool,
        )

    def get_git_info(self) -> GitInfo:
        """Collect git repository information via subprocess.

        Returns a frozen GitInfo with branch, remote, recent commits,
        and dirty files. Returns defaults if git is unavailable.
        """
        branch = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        remote = self._run_git("remote", "get-url", "origin")
        commits_raw = self._run_git("log", "--oneline", "-3", "--no-decorate")
        dirty_raw = self._run_git("status", "--porcelain", "--short")

        recent_commits = tuple(
            line.strip() for line in commits_raw.splitlines() if line.strip()
        )
        dirty_files = tuple(
            line.strip() for line in dirty_raw.splitlines() if line.strip()
        )

        return GitInfo(
            branch=branch.strip(),
            remote=remote.strip(),
            recent_commits=recent_commits,
            dirty_files=dirty_files,
        )

    def get_structure(self, max_depth: int = 2, max_entries: int = 30) -> str:
        """Return a tree-like string of the project structure.

        Skips common non-essential directories like node_modules,
        .git, __pycache__, venv, dist, and build.
        Limited to *max_entries* lines to keep context compact.
        """
        lines: list[str] = [self.project_dir.name + "/"]
        self._walk_tree(self.project_dir, "", max_depth, 0, lines, max_entries)
        if len(lines) >= max_entries:
            lines.append(f"... ({len(lines) - max_entries} more entries omitted)")
        return "\n".join(lines)

    def get_dependencies(self) -> ProjectDependencies:
        """Parse project dependencies from manifest files.

        Supports package.json and pyproject.toml. Returns a frozen
        ProjectDependencies with production and development dicts.
        """
        package_json = self.project_dir / "package.json"
        if package_json.exists():
            return self._parse_node_dependencies(package_json)

        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.exists():
            return self._parse_python_dependencies(pyproject)

        requirements = self.project_dir / "requirements.txt"
        if requirements.exists():
            return self._parse_requirements_txt(requirements)

        return ProjectDependencies()

    def load_rules(self) -> str:
        """Load all rule files and project instructions.

        Loads .md files from .lidco/rules/ directory and LIDCO.md
        from the project root. Returns concatenated content.
        """
        parts: list[str] = []

        lidco_md = self.project_dir / "LIDCO.md"
        if lidco_md.exists():
            try:
                content = lidco_md.read_text(encoding="utf-8")
                parts.append(f"# Project Instructions (LIDCO.md)\n\n{content}")
            except OSError as exc:
                logger.warning("Cannot read %s: %s", lidco_md, exc)

        rules_dir = self.project_dir / ".lidco" / "rules"
        if rules_dir.is_dir():
            rule_files = sorted(rules_dir.glob("*.md"))
            for rule_file in rule_files:
                try:
                    content = rule_file.read_text(encoding="utf-8")
                    parts.append(f"# Rule: {rule_file.stem}\n\n{content}")
                except OSError:
                    continue

        return "\n\n---\n\n".join(parts)

    def build_context_string(self) -> str:
        """Combine all context sources into a formatted string for the system prompt."""
        sections: list[str] = []

        project_type = self.detect_project_type()
        sections.append(self._format_project_type(project_type))

        git_info = self.get_git_info()
        if git_info.branch:
            sections.append(self._format_git_info(git_info))

        structure = self.get_structure()
        sections.append(f"## Project Structure\n\n```\n{structure}\n```")

        deps = self.get_dependencies()
        if deps.production or deps.development:
            sections.append(self._format_dependencies(deps))

        rules = self.load_rules()
        if rules:
            sections.append(f"## Project Rules\n\n{rules}")

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_git(self, *args: str) -> str:
        """Run a git command and return stdout. Returns empty string on failure."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return ""
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return ""

    def _walk_tree(
        self,
        directory: Path,
        prefix: str,
        max_depth: int,
        current_depth: int,
        lines: list[str],
        max_entries: int = 50,
    ) -> None:
        """Recursively build tree lines for the project structure."""
        if current_depth >= max_depth:
            return

        try:
            entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        # Filter out skipped directories
        visible = [
            e for e in entries
            if not (e.is_dir() and e.name in _SKIP_DIRS)
            and not e.name.startswith(".")
        ]

        for i, entry in enumerate(visible):
            if len(lines) >= max_entries:
                return

            is_last = i == len(visible) - 1
            connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            extension = "    " if is_last else "\u2502   "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                self._walk_tree(entry, prefix + extension, max_depth, current_depth + 1, lines, max_entries)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

    def _detect_node_details(self) -> tuple[str, str, str, str]:
        """Detect Node.js framework, package manager, and build tool."""
        language = "javascript"
        framework = "unknown"
        package_manager = "npm"
        build_tool = "unknown"

        # Check for TypeScript
        if (self.project_dir / "tsconfig.json").exists():
            language = "typescript"

        # Check package manager
        if (self.project_dir / "pnpm-lock.yaml").exists():
            package_manager = "pnpm"
        elif (self.project_dir / "yarn.lock").exists():
            package_manager = "yarn"
        elif (self.project_dir / "bun.lockb").exists():
            package_manager = "bun"

        # Parse package.json for framework detection
        pkg_data = self._read_json(self.project_dir / "package.json")
        all_deps = {
            **pkg_data.get("dependencies", {}),
            **pkg_data.get("devDependencies", {}),
        }

        framework_markers = {
            "next": "next.js",
            "nuxt": "nuxt",
            "react": "react",
            "vue": "vue",
            "svelte": "svelte",
            "@angular/core": "angular",
            "express": "express",
            "fastify": "fastify",
            "hono": "hono",
            "astro": "astro",
            "remix": "remix",
            "gatsby": "gatsby",
        }

        for dep_name, fw_name in framework_markers.items():
            if dep_name in all_deps:
                framework = fw_name
                break

        # Detect build tool
        build_tool_markers = {
            "vite": "vite",
            "webpack": "webpack",
            "esbuild": "esbuild",
            "rollup": "rollup",
            "turbo": "turbo",
            "tsup": "tsup",
        }

        for dep_name, tool_name in build_tool_markers.items():
            if dep_name in all_deps:
                build_tool = tool_name
                break

        return language, framework, package_manager, build_tool

    def _detect_python_details(self) -> tuple[str, str, str]:
        """Detect Python framework, package manager, and build tool."""
        framework = "unknown"
        package_manager = "pip"
        build_tool = "unknown"

        if (self.project_dir / "Pipfile").exists():
            package_manager = "pipenv"
        elif (self.project_dir / "poetry.lock").exists():
            package_manager = "poetry"
        elif (self.project_dir / "uv.lock").exists():
            package_manager = "uv"
        elif (self.project_dir / "pdm.lock").exists():
            package_manager = "pdm"

        pyproject = self.project_dir / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                build_tool = self._detect_python_build_tool(content)
                framework = self._detect_python_framework(content)
            except OSError as exc:
                logger.debug("Cannot read %s: %s", pyproject, exc)

        if framework == "unknown":
            requirements = self.project_dir / "requirements.txt"
            if requirements.exists():
                try:
                    content = requirements.read_text(encoding="utf-8").lower()
                    framework = self._match_python_framework(content)
                except OSError as exc:
                    logger.debug("Cannot read %s: %s", requirements, exc)

        return framework, package_manager, build_tool

    def _detect_python_build_tool(self, pyproject_content: str) -> str:
        """Detect Python build tool from pyproject.toml content."""
        content_lower = pyproject_content.lower()
        if "hatchling" in content_lower:
            return "hatch"
        if "poetry" in content_lower:
            return "poetry"
        if "setuptools" in content_lower:
            return "setuptools"
        if "flit" in content_lower:
            return "flit"
        if "maturin" in content_lower:
            return "maturin"
        if "pdm" in content_lower:
            return "pdm"
        return "unknown"

    def _detect_python_framework(self, pyproject_content: str) -> str:
        """Detect Python framework from pyproject.toml content."""
        return self._match_python_framework(pyproject_content.lower())

    def _match_python_framework(self, content: str) -> str:
        """Match Python framework from lowercased dependency content."""
        framework_markers = {
            "django": "django",
            "fastapi": "fastapi",
            "flask": "flask",
            "starlette": "starlette",
            "litestar": "litestar",
            "sanic": "sanic",
            "tornado": "tornado",
            "aiohttp": "aiohttp",
            "streamlit": "streamlit",
            "gradio": "gradio",
        }
        for marker, fw_name in framework_markers.items():
            if marker in content:
                return fw_name
        return "unknown"

    def _detect_java_details(self) -> tuple[str, str]:
        """Detect Java package manager and build tool."""
        if (self.project_dir / "pom.xml").exists():
            return "maven", "maven"
        if (self.project_dir / "build.gradle.kts").exists():
            return "gradle", "gradle"
        if (self.project_dir / "build.gradle").exists():
            return "gradle", "gradle"
        return "unknown", "unknown"

    def _read_json(self, path: Path) -> dict[str, Any]:
        """Read and parse a JSON file. Returns empty dict on failure."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _parse_node_dependencies(self, package_json: Path) -> ProjectDependencies:
        """Parse dependencies from package.json."""
        data = self._read_json(package_json)
        return ProjectDependencies(
            production=dict(data.get("dependencies", {})),
            development=dict(data.get("devDependencies", {})),
        )

    def _parse_python_dependencies(self, pyproject: Path) -> ProjectDependencies:
        """Parse dependencies from pyproject.toml."""
        try:
            content = pyproject.read_text(encoding="utf-8")
        except OSError:
            return ProjectDependencies()

        production: dict[str, str] = {}
        development: dict[str, str] = {}

        # Simple TOML parsing for dependencies array
        in_deps = False
        in_dev_deps = False
        for line in content.splitlines():
            stripped = line.strip()

            if stripped == "[project]":
                in_dev_deps = False
                continue
            if stripped.startswith("dependencies") and "=" in stripped and "[" in stripped:
                in_deps = True
                in_dev_deps = False
                continue
            if "optional-dependencies" in stripped or "dev-dependencies" in stripped:
                in_dev_deps = True
                in_deps = False
                continue
            if stripped.startswith("[") and not stripped.startswith("[["):
                in_deps = False
                in_dev_deps = False
                continue

            if stripped == "]":
                in_deps = False
                in_dev_deps = False
                continue

            if (in_deps or in_dev_deps) and stripped.startswith('"'):
                dep = stripped.strip('",').strip()
                name = dep.split(">=")[0].split("<=")[0].split("==")[0].split(">")[0].split("<")[0].split("~=")[0].split("!=")[0].strip()
                version = dep[len(name):].strip() if len(dep) > len(name) else "*"
                if not version:
                    version = "*"
                target = development if in_dev_deps else production
                target[name] = version

        return ProjectDependencies(production=production, development=development)

    def _parse_requirements_txt(self, requirements: Path) -> ProjectDependencies:
        """Parse dependencies from requirements.txt."""
        try:
            content = requirements.read_text(encoding="utf-8")
        except OSError:
            return ProjectDependencies()

        production: dict[str, str] = {}
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("-"):
                continue
            parts = stripped.split("==")
            if len(parts) == 2:
                production[parts[0].strip()] = parts[1].strip()
            else:
                name = stripped.split(">=")[0].split("<=")[0].split(">")[0].split("<")[0].split("~=")[0].split("!=")[0].strip()
                version = stripped[len(name):].strip() or "*"
                production[name] = version

        return ProjectDependencies(production=production)

    @staticmethod
    def _format_project_type(pt: ProjectType) -> str:
        """Format ProjectType as a markdown section."""
        return (
            "## Project Type\n\n"
            f"- **Language:** {pt.language}\n"
            f"- **Framework:** {pt.framework}\n"
            f"- **Package Manager:** {pt.package_manager}\n"
            f"- **Build Tool:** {pt.build_tool}"
        )

    @staticmethod
    def _format_git_info(gi: GitInfo) -> str:
        """Format GitInfo as a markdown section."""
        lines = [
            "## Git Info\n",
            f"- **Branch:** {gi.branch}",
        ]
        if gi.remote:
            lines.append(f"- **Remote:** {gi.remote}")
        if gi.dirty_files:
            lines.append(f"- **Dirty Files:** {len(gi.dirty_files)}")
            for f in gi.dirty_files[:5]:
                lines.append(f"  - `{f}`")
            if len(gi.dirty_files) > 5:
                lines.append(f"  - ... and {len(gi.dirty_files) - 5} more")
        return "\n".join(lines)

    @staticmethod
    def _format_dependencies(
        deps: ProjectDependencies,
        max_prod: int = 15,
        max_dev: int = 5,
    ) -> str:
        """Format ProjectDependencies as a compact markdown section."""
        lines = ["## Dependencies\n"]
        if deps.production:
            lines.append(f"**Production:** {len(deps.production)} packages")
        if deps.development:
            lines.append(f"**Development:** {len(deps.development)} packages")
        return "\n".join(lines)
