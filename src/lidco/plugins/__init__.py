"""LIDCO plugin system powered by pluggy."""

from lidco.plugins.base import BasePlugin, LidcoHookSpec, hookimpl, hookspec
from lidco.plugins.hooks import HookRunner
from lidco.plugins.manager import PluginManager

__all__ = [
    "BasePlugin",
    "HookRunner",
    "LidcoHookSpec",
    "PluginManager",
    "hookimpl",
    "hookspec",
]
