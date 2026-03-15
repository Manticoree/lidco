"""Command registry package for lidco CLI.

This package exposes the same public API as the original ``commands.py``
module so that all existing imports remain unchanged::

    from lidco.cli.commands import CommandRegistry, SlashCommand
"""

from lidco.cli.commands.registry import CommandRegistry, SlashCommand

__all__ = ["CommandRegistry", "SlashCommand"]
