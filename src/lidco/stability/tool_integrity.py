"""
Q345 — API Contract Stability: Tool Registry Integrity.

Verifies completeness, uniqueness, and permission correctness of the
LIDCO tool registry.
"""
from __future__ import annotations

_VALID_PERMISSIONS = frozenset(
    {
        "read",
        "write",
        "execute",
        "network",
        "filesystem",
        "shell",
        "database",
        "admin",
    }
)


class ToolRegistryIntegrity:
    """Verify integrity of a tool registry snapshot."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # check_completeness
    # ------------------------------------------------------------------

    def check_completeness(self, tools: list[dict]) -> dict:
        """Verify every tool has a run method and a description.

        Each tool dict has ``"name"``, ``"has_run"`` (bool),
        ``"has_description"`` (bool).

        Returns ``{"complete", "missing_run", "missing_description",
        "total"}``.
        """
        missing_run: list[str] = []
        missing_description: list[str] = []

        for tool in tools:
            name = tool.get("name", "<unnamed>")
            if not tool.get("has_run", False):
                missing_run.append(name)
            if not tool.get("has_description", False):
                missing_description.append(name)

        complete = not missing_run and not missing_description

        return {
            "complete": complete,
            "missing_run": sorted(missing_run),
            "missing_description": sorted(missing_description),
            "total": len(tools),
        }

    # ------------------------------------------------------------------
    # find_duplicate_names
    # ------------------------------------------------------------------

    def find_duplicate_names(self, tools: list[dict]) -> list[dict]:
        """Find tools with duplicate names.

        Returns a list of dicts with ``"name"``, ``"count"``, ``"indices"``.
        """
        name_indices: dict[str, list[int]] = {}

        for idx, tool in enumerate(tools):
            name = tool.get("name", "")
            name_indices.setdefault(name, []).append(idx)

        duplicates: list[dict] = []
        for name, indices in sorted(name_indices.items()):
            if len(indices) > 1:
                duplicates.append(
                    {
                        "name": name,
                        "count": len(indices),
                        "indices": indices,
                    }
                )

        return duplicates

    # ------------------------------------------------------------------
    # verify_permissions
    # ------------------------------------------------------------------

    def verify_permissions(self, tools: list[dict]) -> list[dict]:
        """Verify the permission matrix for each tool.

        Tools have ``"name"`` and ``"permissions"`` (list[str]).

        Returns a list of issue dicts with ``"tool"``, ``"permissions"``,
        ``"issues"`` (list[str]).
        """
        results: list[dict] = []

        for tool in tools:
            name = tool.get("name", "<unnamed>")
            permissions: list[str] = tool.get("permissions", [])
            issues: list[str] = []

            if not permissions:
                issues.append(
                    f"Tool '{name}' has no permissions declared."
                )

            for perm in permissions:
                if perm not in _VALID_PERMISSIONS:
                    issues.append(
                        f"Unknown permission '{perm}' on tool '{name}'."
                    )

            # Warn if admin is mixed with other permissions
            if "admin" in permissions and len(permissions) > 1:
                issues.append(
                    f"Tool '{name}' declares 'admin' together with other "
                    "permissions — 'admin' should be used alone."
                )

            if issues:
                results.append(
                    {
                        "tool": name,
                        "permissions": permissions,
                        "issues": issues,
                    }
                )

        return results

    # ------------------------------------------------------------------
    # generate_matrix
    # ------------------------------------------------------------------

    def generate_matrix(self, tools: list[dict]) -> dict:
        """Generate a permission matrix summary for the tool registry.

        Returns ``{"tools": list[str], "permissions": set[str],
        "matrix": dict[str, list[str]]}``.
        """
        tool_names: list[str] = []
        all_perms: set[str] = set()
        matrix: dict[str, list[str]] = {}

        for tool in tools:
            name = tool.get("name", "<unnamed>")
            perms: list[str] = sorted(tool.get("permissions", []))
            tool_names.append(name)
            all_perms.update(perms)
            matrix[name] = perms

        return {
            "tools": tool_names,
            "permissions": all_perms,
            "matrix": matrix,
        }
