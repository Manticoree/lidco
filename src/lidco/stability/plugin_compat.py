"""
Q345 — API Contract Stability: Plugin API Compatibility.

Checks plugin/host API compatibility, tracks interface versions,
determines migration needs, and generates migration guides.
"""
from __future__ import annotations


class PluginApiCompatibility:
    """Manage compatibility between plugin APIs and the host API."""

    def __init__(self) -> None:
        self._interface_history: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------
    # check_compatibility
    # ------------------------------------------------------------------

    def check_compatibility(
        self, plugin_api: dict, host_api: dict
    ) -> dict:
        """Check whether a plugin API is compatible with the host API.

        Both dicts contain ``"version"`` (str) and ``"methods"`` (list[str]).

        Returns a dict with:
        - ``"compatible"`` (bool)
        - ``"missing_methods"`` (list[str]) — methods host requires but plugin lacks
        - ``"extra_methods"`` (list[str]) — methods plugin exposes beyond host
        - ``"version_ok"`` (bool)
        """
        plugin_methods = set(plugin_api.get("methods", []))
        host_methods = set(host_api.get("methods", []))

        missing = sorted(host_methods - plugin_methods)
        extra = sorted(plugin_methods - host_methods)

        version_ok = self._versions_compatible(
            plugin_api.get("version", "0.0.0"),
            host_api.get("version", "0.0.0"),
        )

        compatible = len(missing) == 0 and version_ok

        return {
            "compatible": compatible,
            "missing_methods": missing,
            "extra_methods": extra,
            "version_ok": version_ok,
        }

    def _versions_compatible(self, plugin_ver: str, host_ver: str) -> bool:
        """Major versions must match for compatibility."""
        plugin_major = self._major(plugin_ver)
        host_major = self._major(host_ver)
        return plugin_major == host_major

    def _major(self, version: str) -> int:
        try:
            return int(version.lstrip("v").split(".")[0])
        except (ValueError, IndexError):
            return 0

    # ------------------------------------------------------------------
    # track_interface_versions
    # ------------------------------------------------------------------

    def track_interface_versions(
        self, interfaces: list[dict]
    ) -> dict:
        """Track interface versions over time.

        Each interface dict has ``"name"``, ``"version"``, ``"methods"``.

        Returns a mapping of name -> ``{"current_version", "method_count",
        "history_length"}``.
        """
        for iface in interfaces:
            name = iface.get("name", "")
            if not name:
                continue
            if name not in self._interface_history:
                self._interface_history[name] = []
            self._interface_history[name].append(
                {
                    "version": iface.get("version", "0.0.0"),
                    "methods": list(iface.get("methods", [])),
                }
            )

        result: dict[str, dict] = {}
        for name, history in self._interface_history.items():
            latest = history[-1]
            result[name] = {
                "current_version": latest["version"],
                "method_count": len(latest["methods"]),
                "history_length": len(history),
            }
        return result

    # ------------------------------------------------------------------
    # check_migration_needed
    # ------------------------------------------------------------------

    def check_migration_needed(
        self, old_version: str, new_version: str
    ) -> dict:
        """Determine if a plugin migration is needed between versions.

        Returns ``{"needs_migration", "from_version", "to_version",
        "breaking"}``.
        """
        old_major = self._major(old_version)
        new_major = self._major(new_version)
        old_minor = self._minor(old_version)
        new_minor = self._minor(new_version)

        breaking = new_major > old_major
        needs_migration = new_major > old_major or new_minor > old_minor

        return {
            "needs_migration": needs_migration,
            "from_version": old_version,
            "to_version": new_version,
            "breaking": breaking,
        }

    def _minor(self, version: str) -> int:
        try:
            parts = version.lstrip("v").split(".")
            return int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            return 0

    # ------------------------------------------------------------------
    # generate_migration_guide
    # ------------------------------------------------------------------

    def generate_migration_guide(
        self, old_api: dict, new_api: dict
    ) -> str:
        """Generate a human-readable migration guide between two API versions.

        Both dicts contain ``"version"`` and ``"methods"``.
        """
        old_version = old_api.get("version", "?")
        new_version = new_api.get("version", "?")
        old_methods = set(old_api.get("methods", []))
        new_methods = set(new_api.get("methods", []))

        removed = sorted(old_methods - new_methods)
        added = sorted(new_methods - old_methods)
        retained = sorted(old_methods & new_methods)

        lines: list[str] = [
            f"# Migration Guide: {old_version} → {new_version}",
            "",
        ]

        if removed:
            lines.append("## Removed Methods")
            lines.append(
                "The following methods have been removed and must be replaced:"
            )
            for m in removed:
                lines.append(f"  - `{m}` — no longer available")
            lines.append("")

        if added:
            lines.append("## New Methods")
            lines.append(
                "The following methods are now available:"
            )
            for m in added:
                lines.append(f"  - `{m}` — newly introduced")
            lines.append("")

        if retained:
            lines.append("## Unchanged Methods")
            lines.append(
                "The following methods remain compatible:"
            )
            for m in retained:
                lines.append(f"  - `{m}`")
            lines.append("")

        if not removed and not added:
            lines.append(
                "No method changes detected. Update your version dependency."
            )

        return "\n".join(lines)
