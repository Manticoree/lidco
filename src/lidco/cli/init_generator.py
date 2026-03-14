"""InitGenerator — analyzes a project and generates a LIDCO.md template."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectProfile:
    language: str = "unknown"
    framework: str = ""
    test_runner: str = ""
    test_command: str = ""
    linters: list[str] = field(default_factory=list)
    build_commands: list[str] = field(default_factory=list)
    conventions: list[str] = field(default_factory=list)


_TEMPLATE = """\
# LIDCO.md — Project Instructions

> LIDCO reads this file on every session start.
> Edit freely to teach agents your project conventions.

## Project

{project_section}

## Commands

{commands_section}

## Conventions

{conventions_section}

## Testing

{testing_section}

## Safety

- Never commit secrets, API keys, or .env files
- Always run tests before committing
- Write tests for new functionality
"""


class InitGenerator:
    """Analyze a project directory and generate a LIDCO.md template."""

    def __init__(self, project_dir: Path) -> None:
        self._dir = project_dir.resolve()

    def analyze(self) -> ProjectProfile:
        profile = ProjectProfile()

        # Detect language and framework
        if (self._dir / "pyproject.toml").exists():
            profile.language = "Python"
            self._analyze_python(profile)
        elif (self._dir / "package.json").exists():
            profile.language = "Node.js / TypeScript"
            self._analyze_node(profile)
        elif (self._dir / "Cargo.toml").exists():
            profile.language = "Rust"
            self._analyze_rust(profile)
        elif (self._dir / "go.mod").exists():
            profile.language = "Go"
            self._analyze_go(profile)
        elif (self._dir / "pom.xml").exists() or (self._dir / "build.gradle").exists():
            profile.language = "Java/Kotlin"
            self._analyze_java(profile)

        # General conventions from README
        self._extract_readme_conventions(profile)

        return profile

    def generate(self, profile: ProjectProfile) -> str:
        project_lines = [f"**Language:** {profile.language}"]
        if profile.framework:
            project_lines.append(f"**Framework:** {profile.framework}")

        commands_lines: list[str] = []
        for cmd in profile.build_commands:
            commands_lines.append(f"- {cmd}")
        if profile.test_command:
            commands_lines.append(f"- Run tests: `{profile.test_command}`")
        if profile.linters:
            commands_lines.append(f"- Lint: `{' && '.join(profile.linters)}`")
        if not commands_lines:
            commands_lines.append("- (add your project commands here)")

        conventions_lines = profile.conventions or [
            "- Follow the existing code style",
            "- Keep functions small and focused",
            "- Prefer immutability — avoid mutating arguments",
            "- Use descriptive variable and function names",
        ]

        testing_lines: list[str] = []
        if profile.test_runner:
            testing_lines.append(f"- Test runner: **{profile.test_runner}**")
        if profile.test_command:
            testing_lines.append(f"- Command: `{profile.test_command}`")
        testing_lines.extend([
            "- Write tests for new functionality",
            "- Maintain existing test coverage",
        ])

        return _TEMPLATE.format(
            project_section="\n".join(project_lines),
            commands_section="\n".join(commands_lines),
            conventions_section="\n".join(
                c if isinstance(c, str) else f"- {c}"
                for c in conventions_lines
            ),
            testing_section="\n".join(testing_lines),
        )

    # ------------------------------------------------------------------
    # Language-specific analyzers
    # ------------------------------------------------------------------

    def _analyze_python(self, profile: ProjectProfile) -> None:
        pyproject = self._dir / "pyproject.toml"
        try:
            text = pyproject.read_text(encoding="utf-8")
        except OSError:
            text = ""

        # Framework detection
        for fw in ("django", "flask", "fastapi", "litestar", "starlette"):
            if fw in text.lower():
                profile.framework = fw.capitalize()
                break

        # Test runner
        if "pytest" in text:
            profile.test_runner = "pytest"
            # Try to find test command
            m = re.search(r'\[tool\.pytest.*?\].*?addopts\s*=\s*["\']([^"\']+)', text, re.DOTALL)
            extra = m.group(1).strip() if m else "-q"
            profile.test_command = f"python -m pytest {extra}".strip()
        elif "unittest" in text:
            profile.test_runner = "unittest"
            profile.test_command = "python -m unittest discover"

        # Linters
        if "ruff" in text:
            profile.linters.append("ruff check src/")
        if "mypy" in text:
            profile.linters.append("mypy src/")
        if "black" in text:
            profile.linters.append("black --check src/")

        # Build
        if "build" in text or "setuptools" in text:
            profile.build_commands.append("python -m build")

        # Python version
        m = re.search(r'python_requires\s*=\s*["\']([^"\']+)', text)
        if m:
            profile.conventions.append(f"- Python {m.group(1)}")

    def _analyze_node(self, profile: ProjectProfile) -> None:
        pkg = self._dir / "package.json"
        try:
            import json
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except Exception:
            return

        scripts = data.get("scripts", {})
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

        # Framework
        for fw in ("react", "vue", "angular", "next", "nuxt", "express", "fastify"):
            if fw in deps:
                profile.framework = fw.capitalize()
                break

        # Test runner
        for tr in ("jest", "vitest", "mocha", "jasmine"):
            if tr in deps:
                profile.test_runner = tr
                profile.test_command = scripts.get("test", f"npx {tr}")
                break

        # Linters
        if "eslint" in deps:
            profile.linters.append("npx eslint src/")
        if "prettier" in deps:
            profile.linters.append("npx prettier --check src/")

        # Build
        if "build" in scripts:
            profile.build_commands.append("npm run build")

        # Package manager
        if (self._dir / "pnpm-lock.yaml").exists():
            profile.conventions.append("- Use `pnpm` (not npm or yarn)")
        elif (self._dir / "yarn.lock").exists():
            profile.conventions.append("- Use `yarn` (not npm)")

    def _analyze_rust(self, profile: ProjectProfile) -> None:
        profile.test_runner = "cargo test"
        profile.test_command = "cargo test"
        profile.linters.append("cargo clippy")
        profile.build_commands.append("cargo build")

        cargo = self._dir / "Cargo.toml"
        try:
            text = cargo.read_text(encoding="utf-8")
            for fw in ("axum", "actix", "rocket", "warp", "tokio"):
                if fw in text:
                    profile.framework = fw.capitalize()
                    break
        except OSError:
            pass

    def _analyze_go(self, profile: ProjectProfile) -> None:
        profile.test_runner = "go test"
        profile.test_command = "go test ./..."
        profile.linters.append("golangci-lint run")
        profile.build_commands.append("go build ./...")

    def _analyze_java(self, profile: ProjectProfile) -> None:
        if (self._dir / "pom.xml").exists():
            profile.build_commands.append("mvn clean install")
            profile.test_command = "mvn test"
            profile.test_runner = "JUnit"
        else:
            profile.build_commands.append("./gradlew build")
            profile.test_command = "./gradlew test"
            profile.test_runner = "JUnit"

    def _extract_readme_conventions(self, profile: ProjectProfile) -> None:
        for name in ("README.md", "README.rst", "README.txt"):
            readme = self._dir / name
            if readme.exists():
                try:
                    lines = readme.read_text(encoding="utf-8", errors="ignore").splitlines()[:80]
                    for line in lines:
                        lower = line.lower().strip()
                        if any(kw in lower for kw in ("convention", "style", "guideline", "standard")):
                            clean = line.strip().lstrip("#").strip()
                            if clean and len(clean) < 120:
                                profile.conventions.append(f"- {clean}")
                    break
                except OSError:
                    pass
