"""PluginRegistry — stdlib-only plugin discovery and registration."""
from __future__ import annotations

import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PluginMetadata:
    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""


class PluginNotFoundError(KeyError):
    """Raised when a plugin name is not found in the registry."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Plugin {name!r} not found in registry")
        self.plugin_name = name


@dataclass
class _PluginEntry:
    plugin_class: type
    metadata: PluginMetadata


class PluginRegistry:
    """
    Lightweight plugin registry using stdlib only.

    Plugins are Python classes registered by name.  Discovery via
    :meth:`load_all` scans a directory for classes with a ``plugin_name``
    class attribute.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, _PluginEntry] = {}

    # ----------------------------------------------------------------- register

    def register(
        self,
        name: str,
        plugin_class: type,
        metadata: PluginMetadata | None = None,
    ) -> None:
        """Register *plugin_class* under *name*."""
        if metadata is None:
            metadata = PluginMetadata(name=name)
        self._plugins = {
            **self._plugins,
            name: _PluginEntry(plugin_class=plugin_class, metadata=metadata),
        }

    def unregister(self, name: str) -> bool:
        """Unregister by name.  Return True if existed."""
        if name not in self._plugins:
            return False
        self._plugins = {k: v for k, v in self._plugins.items() if k != name}
        return True

    # ------------------------------------------------------------------- lookup

    def get(self, name: str) -> type:
        """Return the plugin class.  Raises :exc:`PluginNotFoundError` if missing."""
        entry = self._plugins.get(name)
        if entry is None:
            raise PluginNotFoundError(name)
        return entry.plugin_class

    def get_metadata(self, name: str) -> PluginMetadata:
        """Return plugin metadata.  Raises :exc:`PluginNotFoundError` if missing."""
        entry = self._plugins.get(name)
        if entry is None:
            raise PluginNotFoundError(name)
        return entry.metadata

    def list(self) -> list[str]:
        """Return sorted list of registered plugin names."""
        return sorted(self._plugins.keys())

    def list_with_metadata(self) -> list[tuple[str, PluginMetadata]]:
        """Return sorted ``(name, metadata)`` tuples."""
        return [(n, self._plugins[n].metadata) for n in self.list()]

    # ----------------------------------------------------------------- discover

    def load_all(self, package_path: str | Path) -> list[str]:
        """
        Discover plugins in *package_path*.

        Scans non-recursively for ``.py`` files (ignoring ``__init__.py``).
        For each file, loads the module and registers any class with a
        ``plugin_name`` class attribute.

        Returns the list of newly registered plugin names.
        """
        path = Path(package_path)
        registered: list[str] = []

        for py_file in sorted(path.glob("*.py")):
            if py_file.stem.startswith("__"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                continue

            for _, cls in inspect.getmembers(module, inspect.isclass):
                plugin_name = getattr(cls, "plugin_name", None)
                if not plugin_name or not isinstance(plugin_name, str):
                    continue
                metadata = PluginMetadata(
                    name=plugin_name,
                    version=getattr(cls, "plugin_version", "0.0.0"),
                    description=getattr(cls, "plugin_description", ""),
                    author=getattr(cls, "plugin_author", ""),
                )
                self.register(plugin_name, cls, metadata)
                registered.append(plugin_name)

        return registered

    # ----------------------------------------------------------------- helpers

    def clear(self) -> None:
        self._plugins = {}

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, name: object) -> bool:
        return name in self._plugins
