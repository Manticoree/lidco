"""PresetSharing — export, import, verify, and share presets."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict

from lidco.presets.library import Preset, PresetLibrary
from lidco.presets.template import SessionTemplate


def _checksum(data: str) -> str:
    """Compute MD5 hex digest of data string."""
    return hashlib.md5(data.encode()).hexdigest()


@dataclass(frozen=True)
class SharedPreset:
    """A preset packaged for sharing."""

    name: str
    data: str  # JSON
    author: str
    shared_at: float
    checksum: str


class PresetSharing:
    """Export/import presets with integrity verification."""

    def __init__(self, library: PresetLibrary) -> None:
        self._library = library
        self._shared: list[SharedPreset] = []

    def export_preset(self, name: str) -> SharedPreset:
        """Export a preset as a SharedPreset."""
        preset = self._library.get(name)
        if preset is None:
            raise KeyError(f"Preset '{name}' not found")
        data = json.dumps(asdict(preset.template), indent=2)
        shared = SharedPreset(
            name=preset.name,
            data=data,
            author=preset.author,
            shared_at=time.time(),
            checksum=_checksum(data),
        )
        self._shared.append(shared)
        return shared

    def import_preset(self, shared: SharedPreset, overwrite: bool = False) -> bool:
        """Import a SharedPreset into the library. Returns True on success."""
        if not self.verify(shared):
            return False
        if self.conflicts(shared) and not overwrite:
            return False
        template_data = json.loads(shared.data)
        template = SessionTemplate(**template_data)
        preset = Preset(
            name=shared.name,
            category="imported",
            template=template,
            author=shared.author,
        )
        self._library.add(preset)
        return True

    def verify(self, shared: SharedPreset) -> bool:
        """Verify the checksum of a SharedPreset."""
        return _checksum(shared.data) == shared.checksum

    def shared_presets(self) -> list[SharedPreset]:
        """Return all exported SharedPresets."""
        return list(self._shared)

    def conflicts(self, shared: SharedPreset) -> bool:
        """Return True if a preset with the same name already exists."""
        return self._library.get(shared.name) is not None

    def summary(self) -> dict:
        """Return a summary."""
        return {
            "shared_count": len(self._shared),
            "library_total": len(self._library.all_presets()),
        }
