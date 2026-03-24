"""DeploymentScaffolder — detect project stack and generate deployment files."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


@dataclass
class ProjectProfile:
    language: str  # "python", "node", "go", "rust", "unknown"
    framework: str  # "fastapi", "flask", "django", "express", "nextjs", "gin", "none"
    package_manager: str  # "pip", "poetry", "npm", "yarn", "pnpm", "cargo", "go", "none"
    entry_point: str  # e.g. "main.py", "src/index.js", "main.go"
    port: int  # default 8000 for python, 3000 for node, 8080 for go/rust
    has_tests: bool  # True if test dir or pytest/jest config found
    has_db: bool  # True if database-related deps detected


@dataclass
class DeploymentBundle:
    files: dict[str, str]  # {relative_path: content}
    profile: ProjectProfile
    description: str  # human-readable summary of what was generated


_DB_MARKERS = {
    "sqlalchemy",
    "psycopg2",
    "psycopg2-binary",
    "asyncpg",
    "prisma",
    "mongoose",
    "gorm",
    "typeorm",
    "sequelize",
    "django.db",
    "peewee",
}

_PYTHON_FRAMEWORKS = {"fastapi", "flask", "django"}
_NODE_FRAMEWORKS = {"express", "next", "nextjs"}


class DeploymentScaffolder:
    """Scan a project directory and generate deployment scaffolding."""

    def __init__(
        self,
        project_dir: Path,
        llm_fn: Callable | None = None,
    ) -> None:
        self.project_dir = project_dir
        self.llm_fn = llm_fn

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_project(self) -> ProjectProfile:
        """Scan marker files to detect language, framework, entry point."""
        p = self.project_dir

        # --- Python ---
        has_requirements = (p / "requirements.txt").is_file()
        has_pyproject = (p / "pyproject.toml").is_file()
        if has_requirements or has_pyproject:
            return self._detect_python(p, has_requirements, has_pyproject)

        # --- Node ---
        if (p / "package.json").is_file():
            return self._detect_node(p)

        # --- Go ---
        if (p / "go.mod").is_file():
            return self._detect_go(p)

        # --- Rust ---
        if (p / "Cargo.toml").is_file():
            return self._detect_rust(p)

        return ProjectProfile(
            language="unknown",
            framework="none",
            package_manager="none",
            entry_point="",
            port=8080,
            has_tests=False,
            has_db=False,
        )

    # ------------------------------------------------------------------
    # Language-specific detectors
    # ------------------------------------------------------------------

    def _detect_python(
        self, p: Path, has_req: bool, has_pyproject: bool
    ) -> ProjectProfile:
        deps_text = ""
        if has_req:
            deps_text = (p / "requirements.txt").read_text(errors="replace")
        if has_pyproject:
            deps_text += "\n" + (p / "pyproject.toml").read_text(errors="replace")

        deps_lower = deps_text.lower()
        framework = "none"
        for fw in ("fastapi", "flask", "django"):
            if fw in deps_lower:
                framework = fw
                break

        pkg_manager = "poetry" if has_pyproject and "poetry" in deps_lower else "pip"
        entry = self._find_python_entry(p)
        port = 8000
        has_tests = self._python_has_tests(p)
        has_db = self._check_db(deps_lower)

        return ProjectProfile(
            language="python",
            framework=framework,
            package_manager=pkg_manager,
            entry_point=entry,
            port=port,
            has_tests=has_tests,
            has_db=has_db,
        )

    def _detect_node(self, p: Path) -> ProjectProfile:
        raw = (p / "package.json").read_text(errors="replace")
        try:
            pkg = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            pkg = {}

        all_deps: dict = {}
        for key in ("dependencies", "devDependencies"):
            all_deps.update(pkg.get(key, {}))

        deps_lower = " ".join(all_deps.keys()).lower()
        framework = "none"
        if "next" in all_deps:
            framework = "nextjs"
        elif "express" in all_deps:
            framework = "express"

        pkg_manager = "npm"
        if (p / "yarn.lock").is_file():
            pkg_manager = "yarn"
        elif (p / "pnpm-lock.yaml").is_file():
            pkg_manager = "pnpm"

        entry = pkg.get("main", "src/index.js")
        has_tests = (
            (p / "jest.config.js").is_file()
            or (p / "jest.config.ts").is_file()
            or "jest" in all_deps
            or "vitest" in all_deps
        )
        has_db = self._check_db(deps_lower)

        return ProjectProfile(
            language="node",
            framework=framework,
            package_manager=pkg_manager,
            entry_point=entry,
            port=3000,
            has_tests=has_tests,
            has_db=has_db,
        )

    def _detect_go(self, p: Path) -> ProjectProfile:
        mod_text = (p / "go.mod").read_text(errors="replace").lower()
        framework = "gin" if "gin" in mod_text else "none"
        has_db = self._check_db(mod_text)
        has_tests = any(p.glob("*_test.go"))

        return ProjectProfile(
            language="go",
            framework=framework,
            package_manager="go",
            entry_point="main.go",
            port=8080,
            has_tests=has_tests,
            has_db=has_db,
        )

    def _detect_rust(self, p: Path) -> ProjectProfile:
        cargo_text = (p / "Cargo.toml").read_text(errors="replace").lower()
        has_db = self._check_db(cargo_text)
        has_tests = (p / "tests").is_dir()

        return ProjectProfile(
            language="rust",
            framework="none",
            package_manager="cargo",
            entry_point="src/main.rs",
            port=8080,
            has_tests=has_tests,
            has_db=has_db,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_python_entry(p: Path) -> str:
        for candidate in ("main.py", "app.py", "src/main.py"):
            if (p / candidate).is_file():
                return candidate
        return "main.py"

    @staticmethod
    def _python_has_tests(p: Path) -> bool:
        return (
            (p / "tests").is_dir()
            or (p / "test").is_dir()
            or (p / "pytest.ini").is_file()
            or (p / "setup.cfg").is_file()
        )

    @staticmethod
    def _check_db(deps_text: str) -> bool:
        for marker in _DB_MARKERS:
            if marker in deps_text:
                return True
        return False

    # ------------------------------------------------------------------
    # Bundle generation
    # ------------------------------------------------------------------

    def generate(self, profile: ProjectProfile | None = None) -> DeploymentBundle:
        """Auto-detect if profile is None, then generate all deployment files."""
        if profile is None:
            profile = self.detect_project()

        files: dict[str, str] = {}
        files["Dockerfile"] = self.generate_dockerfile(profile)
        files[".github/workflows/ci.yml"] = self.generate_github_actions(profile)
        files["fly.toml"] = self.generate_fly_toml(profile)
        files[".env.example"] = self.generate_env_example(profile)

        desc_parts = [
            f"Deployment scaffold for {profile.language}",
        ]
        if profile.framework != "none":
            desc_parts[0] += f"/{profile.framework}"
        desc_parts.append(f"Generated {len(files)} files: {', '.join(sorted(files))}")

        return DeploymentBundle(
            files=files,
            profile=profile,
            description=". ".join(desc_parts),
        )

    # ------------------------------------------------------------------
    # Individual generators
    # ------------------------------------------------------------------

    def generate_dockerfile(self, profile: ProjectProfile) -> str:
        """Generate appropriate Dockerfile based on language/framework."""
        lang = profile.language
        if lang == "python":
            return self._dockerfile_python(profile)
        if lang == "node":
            return self._dockerfile_node(profile)
        if lang == "go":
            return self._dockerfile_go(profile)
        if lang == "rust":
            return self._dockerfile_rust(profile)
        return self._dockerfile_generic(profile)

    def generate_github_actions(self, profile: ProjectProfile) -> str:
        """Generate .github/workflows/ci.yml."""
        lang = profile.language
        if lang == "python":
            return self._ci_python(profile)
        if lang == "node":
            return self._ci_node(profile)
        if lang == "go":
            return self._ci_go(profile)
        if lang == "rust":
            return self._ci_rust(profile)
        return self._ci_generic(profile)

    def generate_fly_toml(self, profile: ProjectProfile) -> str:
        """Generate fly.toml deployment config."""
        app_name = self.project_dir.name.lower().replace(" ", "-")
        app_name = re.sub(r"[^a-z0-9\-]", "", app_name) or "my-app"

        lines = [
            f'app = "{app_name}"',
            'primary_region = "iad"',
            "",
            "[build]",
            "",
            "[http_service]",
            f"  internal_port = {profile.port}",
            "  force_https = true",
            "  auto_stop_machines = true",
            "  auto_start_machines = true",
            "",
        ]
        if profile.has_db:
            lines.extend([
                "[env]",
                '  DATABASE_URL = "postgres://..."',
                "",
            ])
        return "\n".join(lines)

    def generate_env_example(self, profile: ProjectProfile) -> str:
        """Generate .env.example with common variables."""
        lines = [
            "# Application",
            f"PORT={profile.port}",
            "NODE_ENV=production" if profile.language == "node" else "ENV=production",
            "LOG_LEVEL=info",
        ]
        if profile.has_db:
            lines.extend([
                "",
                "# Database",
                "DATABASE_URL=postgres://user:password@localhost:5432/dbname",
            ])
        lines.extend([
            "",
            "# Secrets",
            "SECRET_KEY=change-me",
        ])
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Dockerfile templates
    # ------------------------------------------------------------------

    @staticmethod
    def _dockerfile_python(profile: ProjectProfile) -> str:
        install_cmd = "pip install --no-cache-dir -r requirements.txt"
        if profile.package_manager == "poetry":
            install_cmd = (
                "pip install poetry && poetry config virtualenvs.create false "
                "&& poetry install --no-interaction --no-ansi"
            )
        cmd = f'CMD ["python", "{profile.entry_point}"]'
        if profile.framework == "fastapi":
            module = profile.entry_point.replace(".py", "").replace("/", ".")
            cmd = (
                f'CMD ["uvicorn", "{module}:app", '
                f'"--host", "0.0.0.0", "--port", "{profile.port}"]'
            )
        elif profile.framework == "flask":
            cmd = (
                f'CMD ["flask", "run", "--host", "0.0.0.0", '
                f'"--port", "{profile.port}"]'
            )
        elif profile.framework == "django":
            cmd = (
                f'CMD ["gunicorn", "--bind", "0.0.0.0:{profile.port}", '
                f'"config.wsgi:application"]'
            )

        copy_deps = "COPY requirements.txt ."
        if profile.package_manager == "poetry":
            copy_deps = "COPY pyproject.toml poetry.lock* ./"

        return "\n".join([
            "FROM python:3.11-slim",
            "WORKDIR /app",
            copy_deps,
            f"RUN {install_cmd}",
            "COPY . .",
            f"EXPOSE {profile.port}",
            cmd,
            "",
        ])

    @staticmethod
    def _dockerfile_node(profile: ProjectProfile) -> str:
        pkg_mgr = profile.package_manager
        if pkg_mgr == "yarn":
            copy_line = "COPY package.json yarn.lock* ./"
            install = "RUN yarn install --production --frozen-lockfile"
        elif pkg_mgr == "pnpm":
            copy_line = "COPY package.json pnpm-lock.yaml* ./"
            install = "RUN corepack enable && pnpm install --prod --frozen-lockfile"
        else:
            copy_line = "COPY package*.json ./"
            install = "RUN npm ci --only=production"

        return "\n".join([
            "FROM node:18-slim",
            "WORKDIR /app",
            copy_line,
            install,
            "COPY . .",
            f"EXPOSE {profile.port}",
            f'CMD ["node", "{profile.entry_point}"]',
            "",
        ])

    @staticmethod
    def _dockerfile_go(profile: ProjectProfile) -> str:
        return "\n".join([
            "FROM golang:1.21-alpine AS builder",
            "WORKDIR /app",
            "COPY go.mod go.sum* ./",
            "RUN go mod download",
            "COPY . .",
            "RUN CGO_ENABLED=0 go build -o /app/server .",
            "",
            "FROM alpine:3.18",
            "WORKDIR /app",
            "COPY --from=builder /app/server .",
            f"EXPOSE {profile.port}",
            'CMD ["./server"]',
            "",
        ])

    @staticmethod
    def _dockerfile_rust(profile: ProjectProfile) -> str:
        return "\n".join([
            "FROM rust:1.73-slim AS builder",
            "WORKDIR /app",
            "COPY Cargo.toml Cargo.lock* ./",
            "COPY src/ src/",
            "RUN cargo build --release",
            "",
            "FROM debian:bookworm-slim",
            "WORKDIR /app",
            "COPY --from=builder /app/target/release/app .",
            f"EXPOSE {profile.port}",
            'CMD ["./app"]',
            "",
        ])

    @staticmethod
    def _dockerfile_generic(profile: ProjectProfile) -> str:
        return "\n".join([
            "FROM ubuntu:22.04",
            "WORKDIR /app",
            "COPY . .",
            f"EXPOSE {profile.port}",
            'CMD ["echo", "Configure your start command"]',
            "",
        ])

    # ------------------------------------------------------------------
    # GitHub Actions templates
    # ------------------------------------------------------------------

    @staticmethod
    def _ci_python(profile: ProjectProfile) -> str:
        test_step = "      - run: pytest" if profile.has_tests else ""
        install = "pip install -r requirements.txt"
        if profile.package_manager == "poetry":
            install = "pip install poetry && poetry install"

        lines = [
            "name: CI",
            "on: [push, pull_request]",
            "jobs:",
            "  test:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - uses: actions/checkout@v4",
            "      - name: Set up Python",
            "        uses: actions/setup-python@v5",
            "        with:",
            '          python-version: "3.11"',
            f"      - run: {install}",
        ]
        if test_step:
            lines.append(test_step)
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _ci_node(profile: ProjectProfile) -> str:
        pkg = profile.package_manager
        if pkg == "yarn":
            install = "yarn install"
            test = "yarn test"
        elif pkg == "pnpm":
            install = "corepack enable && pnpm install"
            test = "pnpm test"
        else:
            install = "npm ci"
            test = "npm test"

        lines = [
            "name: CI",
            "on: [push, pull_request]",
            "jobs:",
            "  test:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - uses: actions/checkout@v4",
            "      - name: Set up Node",
            "        uses: actions/setup-node@v4",
            "        with:",
            '          node-version: "18"',
            f"      - run: {install}",
        ]
        if profile.has_tests:
            lines.append(f"      - run: {test}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _ci_go(profile: ProjectProfile) -> str:
        lines = [
            "name: CI",
            "on: [push, pull_request]",
            "jobs:",
            "  test:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - uses: actions/checkout@v4",
            "      - name: Set up Go",
            "        uses: actions/setup-go@v5",
            "        with:",
            '          go-version: "1.21"',
            "      - run: go build ./...",
        ]
        if profile.has_tests:
            lines.append("      - run: go test ./...")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _ci_rust(profile: ProjectProfile) -> str:
        lines = [
            "name: CI",
            "on: [push, pull_request]",
            "jobs:",
            "  test:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - uses: actions/checkout@v4",
            "      - name: Set up Rust",
            "        uses: dtolnay/rust-toolchain@stable",
            "      - run: cargo build",
        ]
        if profile.has_tests:
            lines.append("      - run: cargo test")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _ci_generic(profile: ProjectProfile) -> str:
        return "\n".join([
            "name: CI",
            "on: [push, pull_request]",
            "jobs:",
            "  build:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - uses: actions/checkout@v4",
            '      - run: echo "Configure your build steps"',
            "",
        ])
