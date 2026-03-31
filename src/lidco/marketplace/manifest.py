"""Plugin manifest schema for MCP Marketplace (Task 947)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TrustLevel(Enum):
    """Trust level assigned to a plugin."""

    VERIFIED = "verified"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"


class Capability(Enum):
    """Capabilities a plugin may require."""

    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    NETWORK = "network"
    EXECUTE = "execute"
    GIT = "git"
    DATABASE = "database"


@dataclass
class PluginManifest:
    """Describes a marketplace plugin."""

    name: str
    version: str
    description: str
    author: str
    trust_level: TrustLevel
    capabilities: list[Capability] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    homepage: str = ""
    checksum: str = ""
    category: str = ""
    min_lidco_version: str = ""

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginManifest:
        """Create a *PluginManifest* from a plain dictionary."""
        trust = data.get("trust_level", "unverified")
        if isinstance(trust, str):
            trust = TrustLevel(trust)

        caps_raw = data.get("capabilities", [])
        caps: list[Capability] = []
        for c in caps_raw:
            if isinstance(c, str):
                caps.append(Capability(c))
            else:
                caps.append(c)

        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            trust_level=trust,
            capabilities=caps,
            dependencies=list(data.get("dependencies", [])),
            homepage=data.get("homepage", ""),
            checksum=data.get("checksum", ""),
            category=data.get("category", ""),
            min_lidco_version=data.get("min_lidco_version", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "trust_level": self.trust_level.value,
            "capabilities": [c.value for c in self.capabilities],
            "dependencies": list(self.dependencies),
            "homepage": self.homepage,
            "checksum": self.checksum,
            "category": self.category,
            "min_lidco_version": self.min_lidco_version,
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    _SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+")

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty means valid)."""
        errors: list[str] = []
        if not self.name:
            errors.append("name is required")
        if not self.version:
            errors.append("version is required")
        elif not self._SEMVER_RE.match(self.version):
            errors.append("version must be semver (e.g. 1.0.0)")
        if not self.description:
            errors.append("description is required")
        if not self.author:
            errors.append("author is required")
        return errors
