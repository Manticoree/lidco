"""Backward-compatibility shim for ``lidco.cli.commands``.

The implementation has moved to the ``lidco.cli.commands`` package
(``commands/registry.py``).  Python's import system gives package
directories precedence over same-named ``.py`` files, so this file is
*never* imported at runtime — the package's ``__init__.py`` is used
instead.

This file is kept so that tooling (editors, linters) that resolves
imports by file path rather than by the Python import machinery still
finds a valid module stub.
"""
# Re-export for any tool that reads this file directly.
from lidco.cli.commands.registry import CommandRegistry, SlashCommand  # noqa: F401

__all__ = ["CommandRegistry", "SlashCommand"]
