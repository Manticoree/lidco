"""
Git Hooks Manager — husky/lefthook-style hook management.

Manages hooks in .git/hooks/ (or a custom hooks directory):
  - List installed hooks with enabled/disabled status
  - Install a new hook (with script content)
  - Remove a hook
  - Enable / disable a hook (by renaming to <name>.disabled)
  - Run a hook manually

Standard git hook names:
  pre-commit, prepare-commit-msg, commit-msg, post-commit,
  pre-push, pre-rebase, post-checkout, post-merge,
  pre-receive, update, post-receive, post-update,
  pre-applypatch, applypatch-msg, post-applypatch
"""

from __future__ import annotations

import os
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Standard hook names
# ---------------------------------------------------------------------------

STANDARD_HOOKS = (
    "pre-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "pre-push",
    "pre-rebase",
    "post-checkout",
    "post-merge",
    "pre-receive",
    "update",
    "post-receive",
    "post-update",
    "pre-applypatch",
    "applypatch-msg",
    "post-applypatch",
    "pre-auto-gc",
    "post-rewrite",
    "sendemail-validate",
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GitHook:
    name: str
    path: str
    enabled: bool
    script: str = ""       # file content
    is_standard: bool = True


@dataclass
class HookResult:
    hook_name: str
    success: bool
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""

    @property
    def output(self) -> str:
        return (self.stdout + self.stderr).strip()


# ---------------------------------------------------------------------------
# HooksManager
# ---------------------------------------------------------------------------

class HooksManager:
    """
    Manage git hooks in a repository.

    Parameters
    ----------
    repo_root : str | None
        Root of the git repository. Defaults to cwd.
    hooks_dir : str | None
        Override hooks directory. Defaults to <repo_root>/.git/hooks.
    """

    _DISABLED_SUFFIX = ".disabled"
    _SHEBANG = "#!/bin/sh"

    def __init__(
        self,
        repo_root: str | None = None,
        hooks_dir: str | None = None,
    ) -> None:
        self._repo = Path(repo_root) if repo_root else Path.cwd()
        if hooks_dir:
            self._hooks_dir = Path(hooks_dir)
        else:
            self._hooks_dir = self._repo / ".git" / "hooks"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def hooks_dir(self) -> Path:
        return self._hooks_dir

    def list(self) -> list[GitHook]:
        """Return all hooks (enabled and disabled) in the hooks directory."""
        if not self._hooks_dir.is_dir():
            return []

        hooks: dict[str, GitHook] = {}

        for path in sorted(self._hooks_dir.iterdir()):
            name = path.name
            if name.endswith(self._DISABLED_SUFFIX):
                base = name[: -len(self._DISABLED_SUFFIX)]
                enabled = False
            else:
                base = name
                enabled = True

            # Skip .sample files
            if base.endswith(".sample") or not path.is_file():
                continue

            try:
                script = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                script = ""

            hooks[base] = GitHook(
                name=base,
                path=str(path),
                enabled=enabled,
                script=script,
                is_standard=base in STANDARD_HOOKS,
            )

        return list(hooks.values())

    def get(self, name: str) -> GitHook | None:
        """Get a hook by name. Returns None if not installed."""
        for hook in self.list():
            if hook.name == name:
                return hook
        return None

    def install(
        self,
        name: str,
        script: str,
        overwrite: bool = False,
    ) -> GitHook:
        """
        Install a hook with the given script content.

        Automatically prepends a shebang line if missing.
        Sets executable permissions on the file.
        """
        self._hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path = self._hooks_dir / name

        if hook_path.exists() and not overwrite:
            raise FileExistsError(
                f"Hook '{name}' already exists. Use overwrite=True to replace."
            )

        content = script
        if not content.startswith("#!"):
            content = f"{self._SHEBANG}\n{content}"
        if not content.endswith("\n"):
            content += "\n"

        hook_path.write_text(content, encoding="utf-8")
        _make_executable(hook_path)

        return GitHook(
            name=name,
            path=str(hook_path),
            enabled=True,
            script=content,
            is_standard=name in STANDARD_HOOKS,
        )

    def remove(self, name: str) -> bool:
        """Remove a hook (enabled or disabled). Returns True if removed."""
        removed = False
        for suffix in ("", self._DISABLED_SUFFIX):
            path = self._hooks_dir / (name + suffix)
            if path.exists():
                path.unlink()
                removed = True
        return removed

    def enable(self, name: str) -> GitHook:
        """Enable a disabled hook by renaming <name>.disabled → <name>."""
        disabled_path = self._hooks_dir / (name + self._DISABLED_SUFFIX)
        enabled_path = self._hooks_dir / name

        if enabled_path.exists():
            hook = self.get(name)
            if hook:
                return hook
            raise FileExistsError(f"Hook '{name}' is already enabled")

        if not disabled_path.exists():
            raise FileNotFoundError(f"Hook '{name}' is not installed")

        disabled_path.rename(enabled_path)
        _make_executable(enabled_path)
        script = enabled_path.read_text(encoding="utf-8", errors="ignore")
        return GitHook(
            name=name,
            path=str(enabled_path),
            enabled=True,
            script=script,
            is_standard=name in STANDARD_HOOKS,
        )

    def disable(self, name: str) -> GitHook:
        """Disable a hook by renaming <name> → <name>.disabled."""
        enabled_path = self._hooks_dir / name
        disabled_path = self._hooks_dir / (name + self._DISABLED_SUFFIX)

        if not enabled_path.exists():
            if disabled_path.exists():
                raise ValueError(f"Hook '{name}' is already disabled")
            raise FileNotFoundError(f"Hook '{name}' is not installed")

        script = enabled_path.read_text(encoding="utf-8", errors="ignore")
        enabled_path.rename(disabled_path)
        return GitHook(
            name=name,
            path=str(disabled_path),
            enabled=False,
            script=script,
            is_standard=name in STANDARD_HOOKS,
        )

    def run(self, name: str, timeout: int = 30) -> HookResult:
        """Execute a hook manually and return its result."""
        hook = self.get(name)
        if hook is None:
            return HookResult(
                hook_name=name,
                success=False,
                returncode=-1,
                stderr=f"Hook '{name}' is not installed",
            )
        if not hook.enabled:
            return HookResult(
                hook_name=name,
                success=False,
                returncode=-1,
                stderr=f"Hook '{name}' is disabled",
            )
        try:
            proc = subprocess.run(
                [hook.path],
                capture_output=True,
                text=True,
                cwd=str(self._repo),
                timeout=timeout,
            )
            return HookResult(
                hook_name=name,
                success=(proc.returncode == 0),
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except subprocess.TimeoutExpired:
            return HookResult(
                hook_name=name,
                success=False,
                returncode=-1,
                stderr=f"Hook '{name}' timed out after {timeout}s",
            )
        except Exception as exc:
            return HookResult(
                hook_name=name,
                success=False,
                returncode=-1,
                stderr=str(exc),
            )

    def install_from_config(self, config: dict[str, str], overwrite: bool = False) -> list[GitHook]:
        """Batch install hooks from a {hook_name: script} dict."""
        installed = []
        for name, script in config.items():
            installed.append(self.install(name, script, overwrite=overwrite))
        return installed


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_executable(path: Path) -> None:
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
