"""Git Hooks v2 — HookManagerV2, HookLibrary, HookComposer, HookDashboard."""

from lidco.githooks.manager import HookManagerV2, HookResult, HookType
from lidco.githooks.library import HookLibrary, HookDefinition
from lidco.githooks.composer import HookComposer
from lidco.githooks.dashboard import HookDashboard

__all__ = [
    "HookManagerV2",
    "HookResult",
    "HookType",
    "HookLibrary",
    "HookDefinition",
    "HookComposer",
    "HookDashboard",
]
