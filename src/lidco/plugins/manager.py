"""Plugin manager - discovers, loads, and manages LIDCO plugins."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

import pluggy

from lidco.plugins.base import BasePlugin, LidcoHookSpec
from lidco.plugins.hooks import HookRunner

logger = logging.getLogger(__name__)


class PluginManager:
    """Discovers, loads, and manages LIDCO plugins.

    Uses pluggy under the hood to handle hook registration and calling.
    Plugins are Python classes that extend BasePlugin and decorate
    methods with @hookimpl.

    Example::

        pm = PluginManager()
        pm.load_from_directory(Path("./plugins"))
        pm.load_plugin(MyPlugin())

        # Use hooks
        params = await pm.hooks.run_pre_tool("file_read", {"path": "/tmp/x"})
    """

    def __init__(self) -> None:
        self._pm = pluggy.PluginManager("lidco")
        self._pm.add_hookspecs(LidcoHookSpec)
        self._hooks = HookRunner(self._pm)
        self._loaded_plugins: list[BasePlugin] = []

    def load_from_directory(self, directory: Path) -> int:
        """Load all .py plugin files from a directory.

        Each .py file is imported and scanned for classes that extend
        BasePlugin. Found plugin classes are instantiated and registered.

        Args:
            directory: Path to the directory containing plugin .py files.

        Returns:
            Number of plugins successfully loaded.
        """
        if not directory.is_dir():
            logger.warning("Plugin directory does not exist: %s", directory)
            return 0

        loaded = 0
        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                count = self._load_from_file(py_file)
                loaded += count
            except Exception:
                logger.exception("Failed to load plugin file: %s", py_file)

        logger.info("Loaded %d plugin(s) from %s", loaded, directory)
        return loaded

    def _load_from_file(self, file_path: Path) -> int:
        """Import a single .py file and register any BasePlugin subclasses.

        Args:
            file_path: Path to the .py file.

        Returns:
            Number of plugins loaded from this file.
        """
        module_name = f"lidco_plugin_{file_path.stem}"

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            logger.warning("Could not create module spec for %s", file_path)
            return 0

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise

        loaded = 0
        for attr_name in dir(module):
            attr = getattr(module, attr_name, None)
            if (
                isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
            ):
                try:
                    instance = attr()
                    self.load_plugin(instance)
                    loaded += 1
                    logger.info(
                        "Loaded plugin: %s v%s (%s)",
                        instance.name,
                        instance.version,
                        file_path.name,
                    )
                except Exception:
                    logger.exception(
                        "Failed to instantiate plugin class %s from %s",
                        attr_name,
                        file_path,
                    )

        return loaded

    def load_plugin(self, plugin: BasePlugin) -> None:
        """Register a single plugin instance.

        Args:
            plugin: An instance of a BasePlugin subclass.

        Raises:
            TypeError: If the plugin is not a BasePlugin instance.
            ValueError: If a plugin with the same name is already loaded.
        """
        if not isinstance(plugin, BasePlugin):
            raise TypeError(
                f"Expected BasePlugin instance, got {type(plugin).__name__}"
            )

        existing_names = {p.name for p in self._loaded_plugins}
        if plugin.name in existing_names:
            raise ValueError(
                f"Plugin '{plugin.name}' is already loaded. "
                "Unload it first or use a different name."
            )

        self._pm.register(plugin, name=plugin.name)
        self._loaded_plugins = [*self._loaded_plugins, plugin]

    def unload_plugin(self, name: str) -> bool:
        """Unregister a plugin by name.

        Args:
            name: The plugin name to unload.

        Returns:
            True if the plugin was found and unloaded, False otherwise.
        """
        for plugin in self._loaded_plugins:
            if plugin.name == name:
                try:
                    self._pm.unregister(plugin, name=name)
                except Exception:
                    logger.exception("Error unregistering plugin: %s", name)
                    return False

                self._loaded_plugins = [
                    p for p in self._loaded_plugins if p.name != name
                ]
                logger.info("Unloaded plugin: %s", name)
                return True

        return False

    def get_plugin(self, name: str) -> BasePlugin | None:
        """Get a loaded plugin by name.

        Args:
            name: The plugin name to look up.

        Returns:
            The plugin instance, or None if not found.
        """
        for plugin in self._loaded_plugins:
            if plugin.name == name:
                return plugin
        return None

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all loaded plugins with their metadata.

        Returns:
            List of dicts with 'name', 'version', and 'description' keys.
        """
        return [
            {
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
            }
            for plugin in self._loaded_plugins
        ]

    @property
    def hooks(self) -> HookRunner:
        """Access the hook runner for executing plugin hooks."""
        return self._hooks

    @property
    def plugin_count(self) -> int:
        """Number of currently loaded plugins."""
        return len(self._loaded_plugins)
