"""Shared configuration resolution across workspace and package levels."""

from __future__ import annotations

import json
import os
from typing import Any


class SharedConfigResolver:
    """Merge workspace-level and package-level .lidco/config.json."""

    CONFIG_DIR = ".lidco"
    CONFIG_FILE = "config.json"

    def resolve(self, workspace_root: str, package_path: str) -> dict[str, Any]:
        """Load and merge configs.  Package values override workspace values."""
        workspace_root = os.path.abspath(workspace_root)
        package_path = os.path.abspath(package_path)

        ws_config = self._load_config(workspace_root)
        pkg_config = self._load_config(package_path)

        merged = self._deep_merge(ws_config, pkg_config)

        # Resolve relative paths against their origin
        merged = self._resolve_paths(merged, workspace_root, package_path, pkg_config)

        return merged

    # -- helpers -------------------------------------------------------------

    def _load_config(self, base_dir: str) -> dict[str, Any]:
        config_path = os.path.join(base_dir, self.CONFIG_DIR, self.CONFIG_FILE)
        if not os.path.isfile(config_path):
            return {}
        try:
            with open(config_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                return {}
            return data
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge *override* into *base*, returning a new dict."""
        result = dict(base)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = SharedConfigResolver._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _resolve_paths(
        config: dict[str, Any],
        ws_root: str,
        pkg_root: str,
        pkg_overrides: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve string values that look like relative paths.

        Values coming from the package config are resolved relative to
        *pkg_root*; values from the workspace config relative to *ws_root*.
        Only top-level string values containing path separators are resolved.
        """
        result = dict(config)
        for key, value in result.items():
            if not isinstance(value, str):
                continue
            if "/" in value or os.sep in value:
                if not os.path.isabs(value):
                    base = pkg_root if key in pkg_overrides else ws_root
                    result[key] = os.path.normpath(os.path.join(base, value))
        return result
