"""Init wizard for project onboarding — task 1103."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.onboarding.detector import ProjectInfo, ProjectType


@dataclass(frozen=True)
class WizardStep:
    """A single wizard question."""

    name: str
    question: str
    default: str
    required: bool


@dataclass(frozen=True)
class WizardResult:
    """Result of running the init wizard."""

    steps_completed: tuple[str, ...]
    config: dict
    claude_md: str


# Default wizard steps per project type
_COMMON_STEPS: tuple[WizardStep, ...] = (
    WizardStep(
        name="project_name",
        question="What is your project name?",
        default="",
        required=True,
    ),
    WizardStep(
        name="description",
        question="Short project description:",
        default="",
        required=False,
    ),
    WizardStep(
        name="test_command",
        question="Test command (e.g. pytest, npm test):",
        default="",
        required=False,
    ),
    WizardStep(
        name="build_command",
        question="Build command:",
        default="",
        required=False,
    ),
)

_TYPE_DEFAULTS: dict[ProjectType, dict[str, str]] = {
    ProjectType.PYTHON: {"test_command": "pytest", "build_command": "python -m build"},
    ProjectType.NODE: {"test_command": "npm test", "build_command": "npm run build"},
    ProjectType.RUST: {"test_command": "cargo test", "build_command": "cargo build"},
    ProjectType.GO: {"test_command": "go test ./...", "build_command": "go build ./..."},
    ProjectType.JAVA: {"test_command": "mvn test", "build_command": "mvn package"},
    ProjectType.RUBY: {"test_command": "bundle exec rspec", "build_command": "bundle exec rake build"},
}


class InitWizard:
    """Interactive init wizard driven by project detection."""

    def __init__(self, project_info: ProjectInfo) -> None:
        self._project_info = project_info

    @property
    def project_info(self) -> ProjectInfo:
        return self._project_info

    def steps(self) -> tuple[WizardStep, ...]:
        """Return the wizard steps, with defaults filled from project type."""
        defaults = _TYPE_DEFAULTS.get(self._project_info.project_type, {})
        result: list[WizardStep] = []
        for step in _COMMON_STEPS:
            if step.name in defaults and not step.default:
                result.append(
                    WizardStep(
                        name=step.name,
                        question=step.question,
                        default=defaults[step.name],
                        required=step.required,
                    )
                )
            else:
                result.append(step)
        return tuple(result)

    def generate_config(self, answers: dict) -> dict:
        """Build a config dict from wizard answers and detected info."""
        config: dict = {
            "project_type": self._project_info.project_type.value,
            "is_monorepo": self._project_info.is_monorepo,
            "root_path": self._project_info.root_path,
        }
        if self._project_info.build_system:
            config["build_system"] = self._project_info.build_system
        if self._project_info.frameworks:
            config["frameworks"] = [fw.name for fw in self._project_info.frameworks]

        # Merge answers
        for key, value in answers.items():
            if value:
                config[key] = value

        return config

    def generate_claude_md(self, config: dict) -> str:
        """Generate a CLAUDE.md file content from config."""
        lines: list[str] = [
            f"# {config.get('project_name', 'Project')} — Claude Code Guidance",
            "",
        ]
        if config.get("description"):
            lines.append(config["description"])
            lines.append("")

        lines.append("## Project Info")
        lines.append("")
        lines.append(f"- **Type**: {config.get('project_type', 'unknown')}")
        if config.get("build_system"):
            lines.append(f"- **Build system**: {config['build_system']}")
        if config.get("is_monorepo"):
            lines.append("- **Monorepo**: yes")
        if config.get("frameworks"):
            lines.append(f"- **Frameworks**: {', '.join(config['frameworks'])}")
        lines.append("")

        if config.get("test_command"):
            lines.append("## Test Commands")
            lines.append("")
            lines.append(f"```bash")
            lines.append(config["test_command"])
            lines.append("```")
            lines.append("")

        if config.get("build_command"):
            lines.append("## Build Commands")
            lines.append("")
            lines.append("```bash")
            lines.append(config["build_command"])
            lines.append("```")
            lines.append("")

        return "\n".join(lines)

    def run(self, answers: dict) -> WizardResult:
        """Execute the wizard with the given answers and return results."""
        steps = self.steps()
        completed: list[str] = []
        resolved: dict = {}

        for step in steps:
            value = answers.get(step.name, step.default)
            if step.required and not value:
                continue
            resolved[step.name] = value
            completed.append(step.name)

        config = self.generate_config(resolved)
        claude_md = self.generate_claude_md(config)

        return WizardResult(
            steps_completed=tuple(completed),
            config=config,
            claude_md=claude_md,
        )
