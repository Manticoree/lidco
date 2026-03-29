"""DeployProviderRegistry — provider detection, registration, config persistence (stdlib only)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class DeployProvider:
    """Describes a deployment target (e.g. Netlify, Railway)."""

    name: str
    detect_files: list[str] = field(default_factory=list)
    build_cmd: str = ""
    deploy_cmd: str = ""
    env_vars_needed: list[str] = field(default_factory=list)
    description: str = ""


class DeployProviderRegistry:
    """Registry of known deploy providers with auto-detection."""

    def __init__(self, path_exists_fn: Callable[[str], bool] | None = None) -> None:
        self._path_exists = path_exists_fn or os.path.exists
        self._providers: dict[str, DeployProvider] = {}
        self._register_builtins()

    # ------------------------------------------------------------------ #
    # Built-in providers                                                   #
    # ------------------------------------------------------------------ #

    def _register_builtins(self) -> None:
        builtins = [
            DeployProvider(
                name="netlify",
                detect_files=["netlify.toml", "netlify.json"],
                build_cmd="npm run build",
                deploy_cmd="netlify deploy --prod",
                env_vars_needed=["NETLIFY_AUTH_TOKEN", "NETLIFY_SITE_ID"],
                description="Netlify static/JAMstack hosting",
            ),
            DeployProvider(
                name="railway",
                detect_files=["railway.json", "railway.toml"],
                build_cmd="railway build",
                deploy_cmd="railway up",
                env_vars_needed=["RAILWAY_TOKEN"],
                description="Railway container hosting",
            ),
            DeployProvider(
                name="fly",
                detect_files=["fly.toml"],
                build_cmd="fly deploy --build-only",
                deploy_cmd="fly deploy",
                env_vars_needed=["FLY_API_TOKEN"],
                description="Fly.io edge hosting",
            ),
            DeployProvider(
                name="heroku",
                detect_files=["Procfile"],
                build_cmd="git push heroku main",
                deploy_cmd="git push heroku main",
                env_vars_needed=["HEROKU_API_KEY"],
                description="Heroku PaaS hosting",
            ),
        ]
        for p in builtins:
            self._providers = {**self._providers, p.name: p}

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def register(self, provider: DeployProvider) -> None:
        """Register or overwrite a provider (idempotent)."""
        self._providers = {**self._providers, provider.name: provider}

    def get(self, name: str) -> Optional[DeployProvider]:
        return self._providers.get(name)

    def list_all(self) -> list[DeployProvider]:
        return list(self._providers.values())

    def auto_detect(self, project_dir: str) -> Optional[DeployProvider]:
        """Check project_dir for detect_files of each provider. Return first match or None."""
        for provider in self._providers.values():
            for filename in provider.detect_files:
                # Use forward-slash joining for cross-platform path_exists_fn compat
                path = project_dir.rstrip("/") + "/" + filename
                if self._path_exists(path):
                    return provider
        return None

    def save_config(self, project_dir: str, provider_name: str, write_fn: Callable[[str, str], None] | None = None) -> None:
        """Persist provider choice to {project_dir}/.lidco/deploy.json."""
        config_dir = os.path.join(project_dir, ".lidco")
        config_path = os.path.join(config_dir, "deploy.json")
        payload = json.dumps({"provider": provider_name}, indent=2)

        if write_fn is not None:
            write_fn(config_path, payload)
            return

        os.makedirs(config_dir, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as fh:
            fh.write(payload)

    def load_config(self, project_dir: str, read_fn: Callable[[str], str] | None = None) -> Optional[str]:
        """Load provider name from .lidco/deploy.json. Return None if missing."""
        config_path = os.path.join(project_dir, ".lidco", "deploy.json")

        try:
            if read_fn is not None:
                raw = read_fn(config_path)
            else:
                with open(config_path, encoding="utf-8") as fh:
                    raw = fh.read()
        except (FileNotFoundError, OSError):
            return None

        if raw is None:
            return None

        try:
            data = json.loads(raw)
            return data.get("provider")
        except (json.JSONDecodeError, AttributeError, TypeError):
            return None
