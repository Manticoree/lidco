"""Plugin / extension API for LIDCO — Task 434.

Provides an abstract base class for plugins, a PluginContext for dependency
injection, and a PluginRegistry for lifecycle management.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Context injected into every plugin on load
# ---------------------------------------------------------------------------

@dataclass
class PluginContext:
    """Runtime context passed to a plugin's ``on_load`` method.

    Attributes:
        session: The active LIDCO session (or None in headless tests).
        commands: The CLI CommandRegistry (or None).
        tools: The ToolRegistry (or None).
        config: The LidcoConfig (or None).
    """

    session: Any = None
    commands: Any = None
    tools: Any = None
    config: Any = None


# ---------------------------------------------------------------------------
# Abstract plugin base class
# ---------------------------------------------------------------------------

class LidcoPlugin(ABC):
    """Abstract base class for LIDCO plugins.

    Subclass this and implement the abstract hooks you need.  Hooks that are
    not relevant to your plugin may be left with the default no-op
    implementation.

    Attributes:
        name: Unique plugin identifier (snake_case).
        version: SemVer string, e.g. ``"1.0.0"``.
        description: One-line human-readable description.
    """

    name: str = "unnamed_plugin"
    version: str = "0.0.0"
    description: str = ""

    async def on_load(self, context: PluginContext) -> None:
        """Called once when the plugin is loaded.  Perform setup here."""

    async def on_unload(self) -> None:
        """Called when the plugin is unloaded or the session ends."""

    async def on_message(self, message: str) -> str | None:
        """Called before each user message is processed.

        Return a replacement message string, or ``None`` to pass through
        unchanged.
        """
        return None

    async def on_tool_call(self, tool_name: str, args: dict) -> dict | None:
        """Called before each tool invocation.

        Return a replacement *args* dict, or ``None`` to use the original.
        """
        return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class PluginRegistry:
    """Manages the lifecycle of loaded plugins.

    Plugins are loaded from Python module files.  Each module must contain
    exactly one class that subclasses :class:`LidcoPlugin`.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, LidcoPlugin] = {}
        self._context: PluginContext | None = None

    def set_context(self, context: PluginContext) -> None:
        """Set the context that will be passed to new plugins on load."""
        self._context = context

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def load(self, path: str | Path) -> LidcoPlugin:
        """Load a plugin from a Python file at *path*.

        Raises:
            FileNotFoundError: If path does not exist.
            ValueError: If no LidcoPlugin subclass is found.
            RuntimeError: If a plugin with the same name is already loaded.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Plugin file not found: {p}")

        plugin_cls = _load_plugin_class(p)
        plugin = plugin_cls()

        if plugin.name in self._plugins:
            raise RuntimeError(f"Plugin '{plugin.name}' is already loaded.")

        ctx = self._context or PluginContext()
        await plugin.on_load(ctx)
        self._plugins[plugin.name] = plugin
        return plugin

    async def unload(self, name: str) -> None:
        """Unload the plugin with the given *name*.

        Raises:
            KeyError: If no plugin with that name is registered.
        """
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' is not loaded.")
        plugin = self._plugins.pop(name)
        await plugin.on_unload()

    def list_plugins(self) -> list[LidcoPlugin]:
        """Return all currently loaded plugins."""
        return list(self._plugins.values())

    def get(self, name: str) -> LidcoPlugin | None:
        """Return the plugin with *name*, or None."""
        return self._plugins.get(name)

    async def dispatch_message(self, message: str) -> str:
        """Run *message* through all plugins' ``on_message`` hooks.

        Each plugin may transform the message.  The (possibly transformed)
        message is passed to the next plugin.
        """
        current = message
        for plugin in self._plugins.values():
            result = await plugin.on_message(current)
            if result is not None:
                current = result
        return current

    async def dispatch_tool(self, tool_name: str, args: dict) -> dict:
        """Run *args* through all plugins' ``on_tool_call`` hooks."""
        current = dict(args)
        for plugin in self._plugins.values():
            result = await plugin.on_tool_call(tool_name, current)
            if result is not None:
                current = result
        return current


# ---------------------------------------------------------------------------
# Plugin loader: discovers plugins in ~/.lidco/plugins/ and .lidco/plugins/
# ---------------------------------------------------------------------------

class PluginLoader:
    """Discovers plugin files in standard plugin directories."""

    GLOBAL_DIR = Path.home() / ".lidco" / "plugins"
    LOCAL_DIR = Path(".lidco") / "plugins"

    def __init__(
        self,
        global_dir: Path | None = None,
        local_dir: Path | None = None,
    ) -> None:
        self._global_dir = global_dir or self.GLOBAL_DIR
        self._local_dir = local_dir or self.LOCAL_DIR

    def discover(self) -> list[Path]:
        """Return all ``.py`` plugin files found in plugin directories.

        Local plugins (project-level) override global ones by stem name.
        """
        found: dict[str, Path] = {}

        for directory in (self._global_dir, self._local_dir):
            if not directory.exists():
                continue
            for py_file in sorted(directory.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                found[py_file.stem] = py_file

        return list(found.values())

    async def load_all(self, registry: PluginRegistry) -> list[LidcoPlugin]:
        """Discover and load all plugins into *registry*.

        Plugins that fail to load are skipped with a warning.
        """
        import logging

        logger = logging.getLogger(__name__)
        loaded: list[LidcoPlugin] = []
        for path in self.discover():
            try:
                plugin = await registry.load(path)
                loaded.append(plugin)
            except Exception as exc:
                logger.warning("Failed to load plugin %s: %s", path, exc)
        return loaded


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_plugin_class(path: Path) -> type[LidcoPlugin]:
    """Import *path* as a module and return the first LidcoPlugin subclass."""
    module_name = f"_lidco_plugin_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load module spec from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj is LidcoPlugin:
            continue
        if issubclass(obj, LidcoPlugin):
            return obj

    raise ValueError(f"No LidcoPlugin subclass found in {path}")
