"""Full environment diagnostic report."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import platform
import sys


@dataclass(frozen=True)
class EnvSection:
    """A titled section of key-value pairs."""

    title: str
    items: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class EnvReport:
    """Complete environment report with multiple sections."""

    sections: tuple[EnvSection, ...] = ()
    generated_at: str = ""


class EnvReporter:
    """Collect and format environment diagnostics."""

    def __init__(self) -> None:
        pass

    def collect_python_info(self) -> EnvSection:
        """Python version, executable, venv, site-packages."""
        vi = sys.version_info
        version = f"{vi.major}.{vi.minor}.{vi.micro}"
        venv = os.environ.get("VIRTUAL_ENV", "(none)")
        site_packages = next(
            (p for p in sys.path if "site-packages" in p),
            "(not found)",
        )
        return EnvSection(
            title="Python",
            items=(
                ("version", version),
                ("executable", sys.executable),
                ("virtualenv", venv),
                ("site-packages", site_packages),
            ),
        )

    def collect_os_info(self) -> EnvSection:
        """Platform, hostname, architecture, PATH count."""
        path_entries = os.environ.get("PATH", "").split(os.pathsep)
        return EnvSection(
            title="OS",
            items=(
                ("platform", platform.platform()),
                ("hostname", platform.node()),
                ("arch", platform.machine()),
                ("PATH entries", str(len(path_entries))),
            ),
        )

    def collect_config_files(self) -> EnvSection:
        """Check for common config files."""
        targets = (".lidco/", "CLAUDE.md", "pyproject.toml", ".env")
        items: list[tuple[str, str]] = []
        for name in targets:
            exists = os.path.exists(name)
            items.append((name, "found" if exists else "missing"))
        return EnvSection(title="Config files", items=tuple(items))

    def collect_env_vars(self) -> EnvSection:
        """List relevant ANTHROPIC_*, OPENAI_*, LIDCO_* env vars (masked)."""
        prefixes = ("ANTHROPIC_", "OPENAI_", "LIDCO_")
        items: list[tuple[str, str]] = []
        for key, value in sorted(os.environ.items()):
            if any(key.startswith(p) for p in prefixes):
                masked = value[:4] + "..." if len(value) > 4 else value
                items.append((key, masked))
        if not items:
            items.append(("(none)", "no relevant env vars found"))
        return EnvSection(title="Environment variables", items=tuple(items))

    def generate(self) -> EnvReport:
        """Collect all sections into a report."""
        return EnvReport(
            sections=(
                self.collect_python_info(),
                self.collect_os_info(),
                self.collect_config_files(),
                self.collect_env_vars(),
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def format_report(self, report: EnvReport) -> str:
        """Format report as multi-section text."""
        lines: list[str] = [f"Environment Report (generated {report.generated_at})", ""]
        for section in report.sections:
            lines.append(f"== {section.title} ==")
            for k, v in section.items:
                lines.append(f"  {k}: {v}")
            lines.append("")
        return "\n".join(lines)

    def summary(self) -> str:
        """Short one-line summary."""
        report = self.generate()
        return self.format_report(report)
