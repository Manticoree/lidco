"""Formatter Registry — detect, configure, and run code formatters (stdlib only).

Supports Black, Ruff, Prettier, isort, autopep8, gofmt, rustfmt.
Detects which formatter is configured via pyproject.toml / .prettierrc /
setup.cfg, runs it via subprocess, and reports formatting issues.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class FormatterError(Exception):
    """Raised when formatter detection or execution fails."""


class FormatterKind(str, Enum):
    BLACK = "black"
    RUFF = "ruff"
    PRETTIER = "prettier"
    ISORT = "isort"
    AUTOPEP8 = "autopep8"
    GOFMT = "gofmt"
    RUSTFMT = "rustfmt"
    UNKNOWN = "unknown"


@dataclass
class FormatResult:
    """Result of a formatting run."""

    formatter: str
    file_path: str
    changed: bool
    output: str = ""
    error: str = ""
    success: bool = True

    def summary(self) -> str:
        status = "changed" if self.changed else "unchanged"
        ok = "OK" if self.success else "ERROR"
        return f"[{ok}] {self.formatter}: {self.file_path} — {status}"


@dataclass
class FormatterConfig:
    """Configuration for a single formatter."""

    kind: FormatterKind
    executable: str
    args: list[str] = field(default_factory=list)
    file_extensions: list[str] = field(default_factory=list)
    check_args: list[str] = field(default_factory=list)   # args for dry-run/check mode

    @property
    def name(self) -> str:
        return self.kind.value

    def supports(self, path: str) -> bool:
        if not self.file_extensions:
            return True
        suffix = Path(path).suffix.lower()
        return suffix in self.file_extensions


# ------------------------------------------------------------------ #
# Built-in formatter definitions                                       #
# ------------------------------------------------------------------ #

_BUILTIN_FORMATTERS: dict[FormatterKind, FormatterConfig] = {
    FormatterKind.BLACK: FormatterConfig(
        kind=FormatterKind.BLACK,
        executable="black",
        args=[],
        file_extensions=[".py"],
        check_args=["--check", "--diff"],
    ),
    FormatterKind.RUFF: FormatterConfig(
        kind=FormatterKind.RUFF,
        executable="ruff",
        args=["format"],
        file_extensions=[".py"],
        check_args=["format", "--check", "--diff"],
    ),
    FormatterKind.PRETTIER: FormatterConfig(
        kind=FormatterKind.PRETTIER,
        executable="prettier",
        args=["--write"],
        file_extensions=[".js", ".ts", ".jsx", ".tsx", ".json", ".css", ".html", ".md"],
        check_args=["--check"],
    ),
    FormatterKind.ISORT: FormatterConfig(
        kind=FormatterKind.ISORT,
        executable="isort",
        args=[],
        file_extensions=[".py"],
        check_args=["--check-only", "--diff"],
    ),
    FormatterKind.AUTOPEP8: FormatterConfig(
        kind=FormatterKind.AUTOPEP8,
        executable="autopep8",
        args=["--in-place"],
        file_extensions=[".py"],
        check_args=["--diff"],
    ),
    FormatterKind.GOFMT: FormatterConfig(
        kind=FormatterKind.GOFMT,
        executable="gofmt",
        args=["-w"],
        file_extensions=[".go"],
        check_args=["-l"],
    ),
    FormatterKind.RUSTFMT: FormatterConfig(
        kind=FormatterKind.RUSTFMT,
        executable="rustfmt",
        args=[],
        file_extensions=[".rs"],
        check_args=["--check"],
    ),
}


class FormatterRegistry:
    """Detect, register, and run code formatters.

    Usage::

        reg = FormatterRegistry()
        reg.detect()   # auto-detect from pyproject.toml / config files
        print(reg.list_available())

        result = reg.format_string("python", "x=1\\ny=2\\n")
        print(result.output)
    """

    def __init__(self) -> None:
        self._formatters: dict[str, FormatterConfig] = {}

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def register(self, config: FormatterConfig) -> None:
        self._formatters[config.name] = config

    def register_builtin(self, kind: FormatterKind) -> None:
        cfg = _BUILTIN_FORMATTERS.get(kind)
        if cfg is None:
            raise FormatterError(f"Unknown built-in formatter: {kind}")
        self._formatters[cfg.name] = cfg

    def unregister(self, name: str) -> bool:
        return self._formatters.pop(name, None) is not None

    def get(self, name: str) -> FormatterConfig | None:
        return self._formatters.get(name)

    def list_available(self) -> list[str]:
        return list(self._formatters.keys())

    def __len__(self) -> int:
        return len(self._formatters)

    # ------------------------------------------------------------------ #
    # Detection                                                            #
    # ------------------------------------------------------------------ #

    def detect(self, root: str = ".") -> list[str]:
        """Auto-detect formatters from config files in *root*."""
        detected: list[str] = []
        root_path = Path(root)

        # pyproject.toml
        pyproject = root_path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8", errors="replace")
            if "[tool.black]" in content:
                self.register_builtin(FormatterKind.BLACK)
                detected.append("black")
            if "[tool.ruff" in content:
                self.register_builtin(FormatterKind.RUFF)
                detected.append("ruff")
            if "[tool.isort]" in content:
                self.register_builtin(FormatterKind.ISORT)
                detected.append("isort")

        # .prettierrc / prettier.config.js
        for name in (".prettierrc", ".prettierrc.json", "prettier.config.js"):
            if (root_path / name).exists():
                self.register_builtin(FormatterKind.PRETTIER)
                detected.append("prettier")
                break

        # setup.cfg
        setup_cfg = root_path / "setup.cfg"
        if setup_cfg.exists():
            content = setup_cfg.read_text(encoding="utf-8", errors="replace")
            if "[isort]" in content:
                self.register_builtin(FormatterKind.ISORT)
                if "isort" not in detected:
                    detected.append("isort")

        return detected

    def is_available(self, name: str) -> bool:
        """Check if the formatter executable is installed."""
        cfg = self._formatters.get(name)
        if cfg is None:
            return False
        try:
            proc = subprocess.run(
                [cfg.executable, "--version"],
                capture_output=True, timeout=5,
            )
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # ------------------------------------------------------------------ #
    # Formatting                                                           #
    # ------------------------------------------------------------------ #

    def format_file(
        self,
        file_path: str,
        formatter_name: str | None = None,
        check_only: bool = False,
    ) -> FormatResult:
        """Format a file in-place (or check if check_only=True)."""
        path = Path(file_path)
        cfg = self._find_formatter(file_path, formatter_name)
        if cfg is None:
            return FormatResult(
                formatter=formatter_name or "auto",
                file_path=file_path,
                changed=False,
                error="No formatter found for this file type",
                success=False,
            )

        original = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        args = cfg.check_args if check_only else cfg.args
        cmd = [cfg.executable, *args, str(path)]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            new_content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
            changed = new_content != original
            return FormatResult(
                formatter=cfg.name,
                file_path=file_path,
                changed=changed,
                output=proc.stdout,
                error=proc.stderr,
                success=proc.returncode == 0,
            )
        except FileNotFoundError:
            return FormatResult(
                formatter=cfg.name,
                file_path=file_path,
                changed=False,
                error=f"Formatter not installed: {cfg.executable}",
                success=False,
            )

    def format_string(
        self,
        language: str,
        source: str,
        formatter_name: str | None = None,
    ) -> FormatResult:
        """Format a source string (via temp file) and return the result."""
        ext_map = {
            "python": ".py", "py": ".py",
            "javascript": ".js", "js": ".js",
            "typescript": ".ts", "ts": ".ts",
            "go": ".go", "rust": ".rs",
            "json": ".json", "markdown": ".md", "md": ".md",
        }
        ext = ext_map.get(language.lower(), f".{language}")

        with tempfile.NamedTemporaryFile(
            suffix=ext, mode="w", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(source)
            tmp_path = tmp.name

        try:
            result = self.format_file(tmp_path, formatter_name=formatter_name)
            if result.success and result.changed:
                result.output = Path(tmp_path).read_text(encoding="utf-8")
            elif result.success:
                result.output = source
            return result
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _find_formatter(
        self, file_path: str, name: str | None
    ) -> FormatterConfig | None:
        if name:
            return self._formatters.get(name)
        # Auto-select by file extension
        for cfg in self._formatters.values():
            if cfg.supports(file_path):
                return cfg
        return None

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def with_defaults(cls) -> "FormatterRegistry":
        """Registry with all built-in formatters registered."""
        reg = cls()
        for kind in _BUILTIN_FORMATTERS:
            reg.register_builtin(kind)
        return reg

    def summary(self) -> dict[str, Any]:
        return {
            "registered": list(self._formatters.keys()),
            "count": len(self._formatters),
        }
